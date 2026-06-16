import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.model.document import Document


class Shift(Document):
    def before_save(self):
        _validate_transition(self)
        if self.status == "Open" and not self.opening_at:
            _lock_rates(self)
            self.opening_at = now_datetime()
        if self.status == "Disputed":
            if not self.dispute_reason:
                frappe.throw(_("Dispute reason is required."))
            if not frappe.has_role("FMS Manager"):
                frappe.throw(_("Only FMS Manager can set shift to Disputed."))
            self.disputed_by = frappe.session.user


def _validate_transition(doc):
    if doc.status not in ("Open", "Readings Captured", "Closing"):
        return
    existing = frappe.db.get_value(
        "Shift",
        {
            "company": doc.company,
            "branch": doc.branch,
            "status": ["in", ["Open", "Readings Captured", "Closing"]],
            "name": ["!=", doc.name],
        },
        "name",
    )
    if existing:
        frappe.throw(_(f"Shift {existing} is already active for this station."))


def _lock_rates(doc):
    from fms.utils.accounts import get_site_preferences
    try:
        prefs = get_site_preferences(doc.company)
        pos_profile = prefs.pos_profile
    except Exception:
        pos_profile = None

    price_list = None
    if pos_profile:
        price_list = frappe.db.get_value("POS Profile", pos_profile, "selling_price_list")

    fuel_items = frappe.get_all("Item", {"fms_is_fuel": 1}, ["name", "item_name"])
    doc.fuel_rates = []
    for item in fuel_items:
        filters = {"item_code": item.name, "selling": 1}
        if price_list:
            filters["price_list"] = price_list
        rate = frappe.db.get_value("Item Price", filters, "price_list_rate") or 0
        doc.append("fuel_rates", {
            "fuel_grade":      item.name,
            "fuel_grade_name": item.item_name,
            "rate_per_litre":  rate,
            "price_list":      price_list,
        })
