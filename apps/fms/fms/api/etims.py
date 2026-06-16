import frappe


def submit_invoice(invoice):
    """Async eTIMS submission — fire-and-forget, enqueued by POS Invoice on_submit."""
    doc = frappe.get_doc("POS Invoice", invoice)
    if doc.get("fms_etims_number"):
        return
    try:
        from fms.utils.accounts import get_site_preferences
        prefs = get_site_preferences(doc.company)
        etims_url = prefs.get("etims_api_url") if prefs else None
        if not etims_url:
            return  # eTIMS not configured — skip silently
        import requests
        payload = _build_payload(doc)
        resp = requests.post(etims_url, json=payload, timeout=30)
        if resp.ok:
            etims_num = resp.json().get("invoiceNumber")
            frappe.db.set_value("POS Invoice", invoice, "fms_etims_number", etims_num)
        else:
            frappe.log_error(resp.text, f"eTIMS error for {invoice}")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"eTIMS exception: {invoice}")


def _build_payload(doc):
    return {
        "invoiceNumber": doc.name,
        "date": str(doc.posting_date),
        "customer": doc.customer,
        "total": doc.grand_total,
    }
