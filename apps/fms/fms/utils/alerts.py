import frappe


def create_alert(shift, message, alert_type="General", severity="Warning"):
    try:
        alert = frappe.new_doc("Forecourt Alert")
        alert.shift = shift
        alert.message = message
        alert.alert_type = alert_type
        alert.severity = severity
        alert.status = "Open"
        alert.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Failed to create alert: {message}")
