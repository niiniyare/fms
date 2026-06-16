import frappe
from fms.utils.accounts import get_site_preferences


def compute_tank_wetstock(shift_name, tank_name):
    shift = frappe.get_doc("Shift", shift_name)
    prefs = get_site_preferences(shift.company)

    opening_l = frappe.db.get_value("Tank Dip Reading", {
        "shift": shift_name, "tank": tank_name,
        "reading_type": "Shift Open", "docstatus": 1,
    }, "volume_observed_l") or 0

    closing_l = frappe.db.get_value("Tank Dip Reading", {
        "shift": shift_name, "tank": tank_name,
        "reading_type": "Shift Close", "docstatus": 1,
    }, "volume_observed_l") or 0

    deliveries_l = frappe.db.sql("""
        SELECT COALESCE(SUM(pri.qty), 0)
        FROM `tabPurchase Receipt Item` pri
        JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        WHERE pr.fms_linked_shift = %s AND pri.warehouse = %s AND pr.docstatus = 1
    """, (shift_name, tank_name))[0][0]

    rtt_l = frappe.db.sql("""
        SELECT COALESCE(SUM(rtt_volume_l), 0)
        FROM `tabMeter Reading`
        WHERE shift = %s AND reading_position IN ('Shift Open', 'Carry Forward')
        AND meter_type = 'Electronic Volume' AND docstatus = 1
        AND pump IN (SELECT name FROM `tabPump` WHERE tank = %s)
    """, (shift_name, tank_name))[0][0]

    ev_sold_l = frappe.db.sql("""
        SELECT COALESCE(SUM(mvr.elec_vol_sold), 0)
        FROM `tabMeter Validation Result` mvr
        JOIN `tabPump` p ON p.name = mvr.pump
        WHERE mvr.shift = %s AND p.tank = %s
    """, (shift_name, tank_name))[0][0]

    theoretical_l = opening_l + deliveries_l - rtt_l - ev_sold_l
    variance_l    = theoretical_l - closing_l
    base_volume   = opening_l + deliveries_l
    variance_pct  = (abs(variance_l) / base_volume * 100) if base_volume > 0 else 0

    wac = frappe.db.get_value("Bin", {"warehouse": tank_name}, "valuation_rate") or 0

    if variance_l < 0:
        status = (
            "Critical" if variance_pct > prefs.wetstock_fail_pct else
            "Elevated" if variance_pct > prefs.wetstock_warn_pct else "Normal"
        )
    else:
        status = "Gain" if variance_pct > prefs.wetstock_warn_pct else "Normal"

    return {
        "opening_dip_l":        opening_l,
        "deliveries_l":         deliveries_l,
        "rtt_volumes_l":        rtt_l,
        "elec_vol_sold_l":      ev_sold_l,
        "theoretical_closing_l": theoretical_l,
        "actual_closing_dip_l": closing_l,
        "variance_l":           variance_l,
        "variance_pct":         variance_pct,
        "wac_rate":             wac,
        "variance_kes":         abs(variance_l) * wac,
        "variance_status":      status,
    }
