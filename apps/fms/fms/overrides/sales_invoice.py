import frappe


def before_submit(doc, method=None):
    if not doc.get("fms_shift"):
        shift = frappe.db.get_value(
            "Shift",
            {"company": doc.company, "status": ["in", ["Open", "Readings Captured"]]},
            "name",
        )
        if shift:
            doc.fms_shift = shift


def on_submit(doc, method=None):
    pass


def on_cancel(doc, method=None):
    frappe.db.set_value("Sales Invoice", doc.name, "fms_shift", None)
