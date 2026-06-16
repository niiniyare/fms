import frappe
from frappe import _


def validate(doc, method=None):
    if not doc.get("fms_docket_number"):
        return
    variance_pct = doc.get("fms_delivery_variance_pct") or 0
    if abs(variance_pct) > 0.50 and not doc.get("fms_variance_approved_by"):
        frappe.throw(
            _(f"Delivery variance {variance_pct:.2f}% exceeds 0.50%. "
              "FMS Manager must set 'Variance Approved By' to proceed.")
        )


def before_submit(doc, method=None):
    validate(doc)


def on_submit(doc, method=None):
    pass
