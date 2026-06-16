import frappe
from frappe import _


def validate(doc, method=None):
    if not _has_fuel_item(doc):
        return
    if not doc.get("fms_pump_attendant"):
        frappe.throw(_("Pump Attendant is required for fuel invoices."))
    if doc.get("fms_pump"):
        is_active = frappe.db.get_value("Pump", doc.fms_pump, "is_active")
        if not is_active:
            frappe.throw(_(f"Pump {doc.fms_pump} is locked. Contact supervisor."))


def before_submit(doc, method=None):
    if not doc.get("fms_shift"):
        shift = _get_open_shift(doc.company)
        if not shift:
            frappe.throw(_("No open shift found for this company. Open a shift before submitting."))
        doc.fms_shift = shift
    shift_status = frappe.db.get_value("Shift", doc.fms_shift, "status")
    if shift_status == "Closing":
        frappe.throw(_("Shift is closing. No new POS Invoices are allowed."))


def on_submit(doc, method=None):
    _link_cashier_session(doc)
    if _has_fuel_item(doc):
        frappe.enqueue(
            "fms.api.etims.submit_invoice",
            invoice=doc.name,
            queue="long",
            is_async=True,
        )


def on_cancel(doc, method=None):
    frappe.db.set_value("POS Invoice", doc.name, {"fms_shift": None, "fms_cashier_session": None})


def _has_fuel_item(doc):
    for item in doc.items:
        if frappe.db.get_value("Item", item.item_code, "fms_is_fuel"):
            return True
    return False


def _get_open_shift(company):
    return frappe.db.get_value(
        "Shift",
        {"company": company, "status": ["in", ["Open", "Readings Captured"]]},
        "name",
    )


def _link_cashier_session(doc):
    if doc.get("fms_cashier_session"):
        return
    session = frappe.db.get_value(
        "Cashier Session",
        {"shift": doc.fms_shift, "cashier": frappe.db.get_value(
            "Employee", {"user_id": frappe.session.user}, "name"
        ), "status": "Open"},
        "name",
    )
    if session:
        frappe.db.set_value("POS Invoice", doc.name, "fms_cashier_session", session)
