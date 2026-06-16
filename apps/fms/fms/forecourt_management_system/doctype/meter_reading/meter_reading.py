import frappe
from frappe import _
from frappe.model.document import Document


class MeterReading(Document):
    def before_submit(self):
        # If this meter reading document is an amendment of an existing one,
        # ensure the original document has already been cancelled before submitting.
        if self.amendment_of:
            orig_status = frappe.db.get_value("Meter Reading", self.amendment_of, "docstatus")
            if orig_status != 2:
                frappe.throw(_("Cancel the original Meter Reading before submitting the amendment."))

    def on_submit(self):
        # When a meter reading is submitted, validate whether the shift readings
        # are complete for the current reading position.
        if self.reading_position in ("Shift Open", "Carry Forward"):
            _check_readings_complete(self.shift, "Shift Open", "Open")
        elif self.reading_position == "Shift Close":
            _check_readings_complete(self.shift, "Shift Close", "Readings Captured")


def _check_readings_complete(shift_name, position, required_status):
    # Load the shift document to confirm the current shift status.
    shift = frappe.get_doc("Shift", shift_name)
    if shift.status != required_status:
        # Do not proceed with validation unless the shift is in the expected state.
        return

    # Find all active pumps and active pump nozzles for the current company.
    required = frappe.db.sql(
        """
        SELECT p.name AS pump, pn.nozzle_number
        FROM `tabPump` p
        JOIN `tabPump Nozzle` pn ON pn.parent = p.name
        WHERE p.company = %s AND p.is_active = 1 AND pn.is_active = 1
    """,
        shift.company,
        as_dict=True,
    )

    # At shift open, both "Shift Open" and "Carry Forward" meter readings count.
    # At shift close, only "Shift Close" readings are relevant.
    position_filter = ["Shift Open", "Carry Forward"] if position == "Shift Open" else ["Shift Close"]

    for r in required:
        # Count confirmed meter readings for each pump/nozzle combination in this shift.
        count = frappe.db.count(
            "Meter Reading",
            {
                "shift": shift_name,
                "pump": r.pump,
                "nozzle_number": r.nozzle_number,
                "reading_position": ["in", position_filter],
                "docstatus": 1,
            },
        )
        if count < 3:
            # If any required nozzle has fewer than three submitted readings,
            # the shift is not yet complete.
            return

    if position == "Shift Open":
        # Once all required open readings are present, update the shift state.
        frappe.db.set_value("Shift", shift_name, "status", "Readings Captured")
