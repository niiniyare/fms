import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CashierSession(Document):
    def before_save(self):
        if not self.till_gl_account and self.cashier:
            self.till_gl_account = frappe.db.get_value(
                "Employee", self.cashier, "fms_till_gl_account"
            )
        if not self.float_issued_at and self.float_amount:
            self.float_issued_at = now_datetime()
        if not self.company and self.shift:
            self.company = frappe.db.get_value("Shift", self.shift, "company")
