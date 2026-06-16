import frappe


def compute_expected_cash(cashier_session_name):
    cs = frappe.get_doc("Cashier Session", cashier_session_name)
    shift = cs.shift
    cashier_user = frappe.db.get_value("Employee", cs.cashier, "user_id")

    total_sales = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabPOS Invoice`
        WHERE fms_shift = %s AND fms_cashier_session = %s AND docstatus = 1
    """, (shift, cashier_session_name))[0][0]

    total_invoices = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Invoice`
        WHERE fms_shift = %s AND owner = %s AND docstatus = 1
    """, (shift, cashier_user))[0][0]

    def _mode_total(mode):
        return frappe.db.sql("""
            SELECT COALESCE(SUM(sip.amount), 0)
            FROM `tabSales Invoice Payment` sip
            JOIN `tabPOS Invoice` pi ON pi.name = sip.parent
            WHERE pi.fms_cashier_session = %s AND pi.docstatus = 1
            AND sip.mode_of_payment = %s
        """, (cashier_session_name, mode))[0][0]

    total_mpesa = _mode_total("MPesa")
    total_visa  = _mode_total("VISA")
    total_pdq   = _mode_total("PDQ")

    total_receipts = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) FROM `tabCash Event`
        WHERE cashier_session = %s AND event_type = 'Float In' AND docstatus = 1
    """, (cashier_session_name,))[0][0]

    total_out = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) FROM `tabCash Event`
        WHERE cashier_session = %s
        AND event_type IN ('Cash Pickup', 'Safe Drop', 'Payout') AND docstatus = 1
    """, (cashier_session_name,))[0][0]

    expected = (total_sales - total_invoices - total_mpesa - total_visa - total_pdq
                + total_receipts - total_out)

    frappe.db.set_value("Cashier Session", cashier_session_name, {
        "expected_cash":  expected,
        "cash_variance":  (cs.actual_cash_close or 0) - expected,
    })
    return expected
