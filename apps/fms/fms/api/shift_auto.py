import frappe
from frappe.utils import now_datetime, add_days
from fms.utils.accounts import get_site_preferences


def open_next_shift(closed_shift_name):
    """
    Called after shift close if auto_open_next_shift is enabled.
    Carries forward closing readings as opening readings of the new shift.
    """
    closed = frappe.get_doc("Shift", closed_shift_name)
    prefs = get_site_preferences(closed.company)
    if not prefs.auto_open_next_shift:
        return None

    shifts_per_day = int(prefs.shifts_per_day or 3)
    next_num = (int(closed.shift_number) % shifts_per_day) + 1
    next_date = (
        closed.shift_date if next_num > 1
        else add_days(closed.shift_date, 1)
    )

    # Prevent duplicate
    existing = frappe.db.get_value("Shift", {
        "company": closed.company,
        "branch": closed.branch,
        "shift_date": next_date,
        "shift_number": str(next_num),
        "status": ["in", ["Draft", "Open", "Readings Captured"]],
    }, "name")
    if existing:
        return existing

    new_shift = frappe.new_doc("Shift")
    new_shift.company = closed.company
    new_shift.branch = closed.branch
    new_shift.shift_date = next_date
    new_shift.shift_number = str(next_num)
    new_shift.supervisor = closed.supervisor
    new_shift.previous_shift = closed.name
    new_shift.insert(ignore_permissions=True)

    _carry_forward_meter_readings(closed, new_shift)
    _carry_forward_dip_readings(closed, new_shift)

    return new_shift.name


def _carry_forward_meter_readings(closed_shift, new_shift):
    closing_readings = frappe.get_all(
        "Meter Reading",
        {"shift": closed_shift.name, "reading_position": "Shift Close", "docstatus": 1},
        ["pump", "nozzle_number", "meter_type", "totalizer_value", "company"],
    )
    for r in closing_readings:
        mr = frappe.new_doc("Meter Reading")
        mr.update({
            "shift":            new_shift.name,
            "pump":             r.pump,
            "nozzle_number":    r.nozzle_number,
            "meter_type":       r.meter_type,
            "totalizer_value":  r.totalizer_value,
            "reading_position": "Carry Forward",
            "read_by":          closed_shift.supervisor,
            "reading_datetime": now_datetime(),
            "company":          r.company,
        })
        mr.insert(ignore_permissions=True)
        mr.submit()


def _carry_forward_dip_readings(closed_shift, new_shift):
    closing_dips = frappe.get_all(
        "Tank Dip Reading",
        {"shift": closed_shift.name, "reading_type": "Shift Close", "docstatus": 1},
        ["tank", "dip_height_mm", "water_level_mm", "volume_observed_l",
         "calibration_chart", "company"],
    )
    for d in closing_dips:
        dip = frappe.new_doc("Tank Dip Reading")
        dip.update({
            "shift":            new_shift.name,
            "tank":             d.tank,
            "reading_type":     "Shift Open",
            "reading_source":   "Carry Forward",
            "dip_height_mm":    d.dip_height_mm,
            "water_level_mm":   d.water_level_mm,
            "volume_observed_l": d.volume_observed_l,
            "calibration_chart": d.calibration_chart,
            "recorded_by":      closed_shift.supervisor,
            "company":          d.company,
            "reading_datetime": now_datetime(),
        })
        dip.insert(ignore_permissions=True)
        dip.submit()
