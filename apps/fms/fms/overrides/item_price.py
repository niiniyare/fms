import frappe
from frappe import _


def validate(doc, method=None):
    epra_max = doc.get("fms_epra_max_price") or 0
    if epra_max and doc.price_list_rate > epra_max:
        if not doc.get("fms_approved_by"):
            frappe.throw(
                _(f"Price {doc.price_list_rate} exceeds EPRA cap {epra_max}. "
                  "Set 'Approved By' (FMS Manager) to override.")
            )
