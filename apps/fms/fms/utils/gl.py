import frappe
from frappe.utils import now_datetime
from fms.utils.accounts import (
    get_site_preferences, get_fuel_inventory_account, get_wetstock_variance_account
)


def post_shift_variances(shift_reconciliation_name):
    """
    Post VARIANCES ONLY at shift close.
    Revenue/COGS are already posted by POS Invoice on_submit — do NOT re-post.
    """
    sr = frappe.get_doc("Shift Reconciliation", shift_reconciliation_name)
    shift = frappe.get_doc("Shift", sr.shift)
    prefs = get_site_preferences(shift.company)

    entries = []

    for row in sr.cashier_summary:
        variance = row.cash_variance or 0
        if abs(variance) < 0.01:
            continue
        entry = {
            "account": prefs.cash_over_account,
            "cost_center": frappe.db.get_value("Company", shift.company, "cost_center"),
            "party_type": "Employee",
            "party": row.cashier,
        }
        if variance < 0:
            entry["debit_in_account_currency"] = abs(variance)
        else:
            entry["credit_in_account_currency"] = variance
        entries.append(entry)

    safe_drops = frappe.get_all(
        "Cash Event",
        {"shift": sr.shift, "event_type": "Safe Drop", "docstatus": 1},
        ["amount", "name"],
    )
    for sd in safe_drops:
        entries += [
            {"account": prefs.safe_main_account,
             "debit_in_account_currency": sd.amount,
             "remarks": f"Safe Drop {sd.name}"},
            {"account": prefs.till_active_account,
             "credit_in_account_currency": sd.amount,
             "remarks": f"Safe Drop {sd.name}"},
        ]

    for row in sr.tank_wetstock_summary:
        variance_l = row.variance_l or 0
        if abs(variance_l) < 1.0:
            continue
        value = abs(variance_l) * (row.wac_rate or 0)
        fuel_grade = frappe.db.get_value("Warehouse", row.tank, "fms_fuel_grade")
        fuel_acct  = get_fuel_inventory_account(row.tank, shift.company)
        var_acct   = get_wetstock_variance_account(fuel_grade, shift.company)
        if variance_l < 0:
            entries += [
                {"account": var_acct,   "debit_in_account_currency": value},
                {"account": fuel_acct,  "credit_in_account_currency": value},
            ]
        else:
            entries += [
                {"account": fuel_acct,  "debit_in_account_currency": value},
                {"account": var_acct,   "credit_in_account_currency": value},
            ]

    for row in getattr(sr, "pdq_settlement_recon", []):
        variance = row.card_variance_kes or 0
        if abs(variance) <= (prefs.pdq_variance_warn_kes or 50):
            continue
        if variance < 0:
            entries += [
                {"account": prefs.card_variance_account,
                 "debit_in_account_currency": abs(variance)},
                {"account": prefs.pdq_clearing_account,
                 "credit_in_account_currency": abs(variance)},
            ]

    if not entries:
        frappe.msgprint("No material variances to post.")
        return None

    total_dr = sum(e.get("debit_in_account_currency", 0) for e in entries)
    total_cr = sum(e.get("credit_in_account_currency", 0) for e in entries)
    if abs(total_dr - total_cr) > 0.05:
        frappe.throw(f"GL imbalance: DR {total_dr:.2f} ≠ CR {total_cr:.2f}")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = shift.shift_date
    je.company = shift.company
    je.user_remark = f"Shift Close Variances — {shift.name}"
    je.cheque_no = shift.name
    for e in entries:
        je.append("accounts", e)
    je.submit()

    frappe.db.set_value("Shift Reconciliation", shift_reconciliation_name, {
        "gl_journal": je.name,
        "status": "GL Posted",
    })
    frappe.db.set_value("Shift", sr.shift, {
        "status": "Closed",
        "closing_at": now_datetime(),
        "gl_journal": je.name,
    })
    return je.name
