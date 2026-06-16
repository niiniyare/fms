import frappe
from frappe.model.document import Document


class FuelDeliveryDip(Document):
    def compute_variance(self):
        """Called after both Delivery Before and After dip readings are submitted."""
        before = frappe.db.get_value("Tank Dip Reading", {
            "fuel_delivery_dip": self.name,
            "reading_type": "Delivery Before",
            "docstatus": 1,
        }, ["volume_observed_l", "reading_datetime"], as_dict=True)

        after = frappe.db.get_value("Tank Dip Reading", {
            "fuel_delivery_dip": self.name,
            "reading_type": "Delivery After",
            "docstatus": 1,
        }, ["volume_observed_l", "reading_datetime"], as_dict=True)

        if not (before and after):
            return

        sales_during = frappe.db.sql("""
            SELECT COALESCE(SUM(pi.total_qty), 0)
            FROM `tabPOS Invoice` pi
            JOIN `tabPOS Invoice Item` pii ON pii.parent = pi.name
            WHERE pi.fms_shift = %s
            AND pii.warehouse = %s
            AND pi.posting_date BETWEEN %s AND %s
            AND pi.docstatus = 1
        """, (self.shift, self.tank, before.reading_datetime, after.reading_datetime))[0][0]

        dip_measured = (after.volume_observed_l - before.volume_observed_l) + (sales_during or 0)
        variance_l = self.docket_volume_l - dip_measured
        variance_pct = (variance_l / self.docket_volume_l * 100) if self.docket_volume_l else 0

        self.dip_measured_l = dip_measured
        self.variance_l = variance_l
        self.variance_pct = variance_pct
        self.before_at = before.reading_datetime
        self.after_at = after.reading_datetime
        self.save(ignore_permissions=True)
