import frappe
from frappe.model.document import Document


class CashEvent(Document):
    def before_save(self):
        if not self.company and self.shift:
            self.company = frappe.db.get_value("Shift", self.shift, "company")
