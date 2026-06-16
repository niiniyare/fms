import frappe
from frappe.utils import now_datetime
from fms.utils.meter import run_meter_validation
from fms.utils.cash import compute_expected_cash
from fms.utils.wetstock import compute_tank_wetstock
from fms.utils.accounts import get_site_preferences


@frappe.whitelist()
def trigger_meter_validation(shift_name):
    run_meter_validation(shift_name)
    frappe.msgprint(f"Meter validation complete for {shift_name}.")


@frappe.whitelist()
def compute_reconciliation(shift_name):
    """
    Build/update the Shift Reconciliation for a shift.
    Idempotent: updates existing record if present.
    """
    shift = frappe.get_doc("Shift", shift_name)
    prefs = get_site_preferences(shift.company)

    # Find or create reconciliation
    existing = frappe.db.get_value("Shift Reconciliation", {"shift": shift_name}, "name")
    if existing:
        sr = frappe.get_doc("Shift Reconciliation", existing)
    else:
        sr = frappe.new_doc("Shift Reconciliation")
        sr.shift = shift_name
        sr.company = shift.company

    # 1. Cashier summary
    sessions = frappe.get_all(
        "Cashier Session",
        {"shift": shift_name, "status": "Closed"},
        ["name", "cashier", "float_amount", "actual_cash_close"],
    )
    sr.cashier_summary = []
    for s in sessions:
        expected = compute_expected_cash(s.name)
        variance = (s.actual_cash_close or 0) - expected
        abs_v = abs(variance)
        status = (
            "Fail"    if abs_v > (prefs.cash_variance_fail_kes or 200) else
            "Warning" if abs_v > (prefs.cash_variance_warn_kes or 50) else "Pass"
        )
        cs_doc = frappe.get_doc("Cashier Session", s.name)
        sr.append("cashier_summary", {
            "cashier":         s.cashier,
            "cashier_session": s.name,
            "float_amount":    s.float_amount or 0,
            "expected_cash":   expected,
            "actual_cash":     s.actual_cash_close or 0,
            "cash_variance":   variance,
            "variance_status": status,
        })

    # 2. Tank wetstock summary
    tanks = frappe.get_all(
        "Warehouse",
        {"fms_is_fuel_tank": 1, "company": shift.company},
        ["name", "fms_fuel_grade"],
    )
    sr.tank_wetstock_summary = []
    for tank in tanks:
        ws = compute_tank_wetstock(shift_name, tank.name)
        sr.append("tank_wetstock_summary", {
            "tank":                tank.name,
            "fuel_grade":          tank.fms_fuel_grade,
            "opening_dip_l":       ws["opening_dip_l"],
            "deliveries_l":        ws["deliveries_l"],
            "rtt_volumes_l":       ws["rtt_volumes_l"],
            "elec_vol_sold_l":     ws["elec_vol_sold_l"],
            "theoretical_closing_l": ws["theoretical_closing_l"],
            "actual_closing_dip_l":  ws["actual_closing_dip_l"],
            "variance_l":          ws["variance_l"],
            "variance_pct":        ws["variance_pct"],
            "wac_rate":            ws["wac_rate"],
            "variance_kes":        ws["variance_kes"],
            "variance_status":     ws["variance_status"],
        })

    # 3. Nozzle MVR summary
    mvrs = frappe.get_all(
        "Meter Validation Result",
        {"shift": shift_name},
        ["pump", "nozzle_number", "elec_vol_sold", "elec_cash_sold", "man_mech_sold",
         "check_a_result", "check_b_result", "check_e_result", "overall_result", "pump_locked"],
    )
    sr.nozzle_mvr_summary = []
    for m in mvrs:
        sr.append("nozzle_mvr_summary", {
            "pump":           m.pump,
            "nozzle_number":  m.nozzle_number,
            "elec_vol_sold":  m.elec_vol_sold,
            "elec_cash_sold": m.elec_cash_sold,
            "man_mech_sold":  m.man_mech_sold,
            "check_a_result": m.check_a_result,
            "check_b_result": m.check_b_result,
            "check_e_result": m.check_e_result,
            "overall_result": m.overall_result,
            "pump_locked":    m.pump_locked,
        })

    # 4. PDQ settlement recon (Phase 5 — stub)
    sr.pdq_settlement_recon = []

    sr.save(ignore_permissions=True)

    # Link reconciliation back to shift
    frappe.db.set_value("Shift", shift_name, "shift_reconciliation", sr.name)

    return sr.name


@frappe.whitelist()
def approve_and_post_gl(shift_reconciliation_name):
    from fms.utils.gl import post_shift_variances
    sr = frappe.get_doc("Shift Reconciliation", shift_reconciliation_name)
    if sr.status == "GL Posted":
        frappe.throw("GL already posted for this reconciliation.")
    sr.status = "Approved"
    sr.save(ignore_permissions=True)
    je_name = post_shift_variances(shift_reconciliation_name)
    return je_name


@frappe.whitelist()
def get_open_shift(company):
    return frappe.db.get_value(
        "Shift",
        {"company": company, "status": ["in", ["Open", "Readings Captured"]]},
        ["name", "shift_date", "shift_number", "supervisor"],
        as_dict=True,
    )
