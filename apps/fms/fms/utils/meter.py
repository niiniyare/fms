import frappe
from frappe.utils import now_datetime
from fms.utils.accounts import get_site_preferences
from fms.utils.alerts import create_alert


def run_meter_validation(shift_name):
    """
    Idempotent: safe to run multiple times; upserts Meter Validation Result per nozzle.
    """
    shift = frappe.get_doc("Shift", shift_name)
    prefs = get_site_preferences(shift.company)

    active_nozzles = frappe.db.sql("""
        SELECT p.name AS pump, p.fuel_grade, pn.nozzle_number
        FROM `tabPump` p
        JOIN `tabPump Nozzle` pn ON pn.parent = p.name
        WHERE p.company = %s AND p.is_active = 1 AND pn.is_active = 1
    """, shift.company, as_dict=True)

    for nozzle in active_nozzles:
        readings = _get_readings(shift_name, nozzle.pump, nozzle.nozzle_number)
        if not readings["complete"]:
            continue

        ev_sold = readings["close_ev"] - readings["open_ev"]
        ec_sold = readings["close_ec"] - readings["open_ec"]
        mm_sold = readings["close_mm"] - readings["open_mm"]
        rate = _get_shift_rate(shift, nozzle.fuel_grade)

        check_a_val = abs(ec_sold - (ev_sold * rate))
        check_a_res = (
            "Pass" if check_a_val <= 5 else
            "Warning" if check_a_val <= 20 else "Fail"
        )

        if ev_sold == 0:
            check_b_pct, check_b_res = 0.0, "Pass"
        else:
            check_b_pct = abs(ev_sold - mm_sold) / ev_sold * 100
            check_b_res = (
                "Pass"     if check_b_pct <= 0.30 else
                "Warning"  if check_b_pct <= 0.50 else
                "Fail"     if check_b_pct <= 1.00 else "Critical"
            )

        pos_total = frappe.db.sql("""
            SELECT COALESCE(SUM(grand_total), 0)
            FROM `tabPOS Invoice`
            WHERE fms_shift = %s AND fms_pump = %s
            AND fms_nozzle_number = %s AND docstatus = 1
        """, (shift_name, nozzle.pump, nozzle.nozzle_number))[0][0]

        check_e_var = abs(ec_sold - pos_total)
        check_e_res = (
            "Pass" if check_e_var <= 10 else
            "Warning" if check_e_var <= 50 else "Fail"
        )

        all_results = [check_a_res, check_b_res, check_e_res]
        overall = (
            "Critical" if "Critical" in all_results else
            "Fail"     if "Fail"     in all_results else
            "Warning"  if "Warning"  in all_results else "Pass"
        )

        pump_locked = False
        if check_b_res == "Critical":
            frappe.db.set_value("Pump", nozzle.pump, "is_active", 0)
            pump_locked = True
            create_alert(
                shift_name,
                f"Pump {nozzle.pump} locked: Check B Critical ({check_b_pct:.2f}%)",
                "Check B Critical",
                "Critical",
            )

        existing = frappe.db.get_value(
            "Meter Validation Result",
            {"shift": shift_name, "pump": nozzle.pump, "nozzle_number": nozzle.nozzle_number},
            "name",
        )
        mvr = frappe.get_doc("Meter Validation Result", existing) if existing \
              else frappe.new_doc("Meter Validation Result")

        if not existing:
            mvr.shift = shift_name
            mvr.pump = nozzle.pump
            mvr.nozzle_number = nozzle.nozzle_number

        mvr.update({
            "computed_at": now_datetime(),
            "opening_elec_vol":  readings["open_ev"],
            "closing_elec_vol":  readings["close_ev"],
            "elec_vol_sold":     ev_sold,
            "opening_elec_cash": readings["open_ec"],
            "closing_elec_cash": readings["close_ec"],
            "elec_cash_sold":    ec_sold,
            "opening_man_mech":  readings["open_mm"],
            "closing_man_mech":  readings["close_mm"],
            "man_mech_sold":     mm_sold,
            "shift_rate":        rate,
            "check_a_value":     check_a_val,
            "check_a_result":    check_a_res,
            "check_b_pct":       check_b_pct,
            "check_b_result":    check_b_res,
            "check_e_pos_total": pos_total,
            "check_e_variance":  check_e_var,
            "check_e_result":    check_e_res,
            "overall_result":    overall,
            "pump_locked":       pump_locked,
        })
        mvr.save(ignore_permissions=True)


def _get_readings(shift_name, pump, nozzle_number):
    """Return opening and closing totalizer values for all 3 meter types."""
    result = {
        "open_ev": 0, "close_ev": 0,
        "open_ec": 0, "close_ec": 0,
        "open_mm": 0, "close_mm": 0,
        "complete": False,
    }
    rows = frappe.db.sql("""
        SELECT meter_type, reading_position, totalizer_value
        FROM `tabMeter Reading`
        WHERE shift = %s AND pump = %s AND nozzle_number = %s
        AND reading_position IN ('Shift Open', 'Shift Close', 'Carry Forward')
        AND docstatus = 1
        ORDER BY creation ASC
    """, (shift_name, pump, nozzle_number), as_dict=True)

    type_map = {
        "Electronic Volume": ("ev", "open_ev", "close_ev"),
        "Electronic Cash":   ("ec", "open_ec", "close_ec"),
        "Manual Mechanical": ("mm", "open_mm", "close_mm"),
    }

    open_set = set()
    close_set = set()

    for r in rows:
        if r.meter_type not in type_map:
            continue
        _, open_key, close_key = type_map[r.meter_type]
        short = type_map[r.meter_type][0]
        if r.reading_position in ("Shift Open", "Carry Forward"):
            result[open_key] = r.totalizer_value
            open_set.add(short)
        elif r.reading_position == "Shift Close":
            result[close_key] = r.totalizer_value
            close_set.add(short)

    all_types = {"ev", "ec", "mm"}
    result["complete"] = (open_set >= all_types) and (close_set >= all_types)
    return result


def _get_shift_rate(shift, fuel_grade):
    for row in shift.fuel_rates:
        if row.fuel_grade == fuel_grade:
            return row.rate_per_litre
    return 0
