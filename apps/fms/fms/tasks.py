import frappe
from frappe.utils import now_datetime


def check_stale_shifts():
    from fms.utils.alerts import create_alert
    for company in frappe.get_all("Company", pluck="name"):
        try:
            prefs = frappe.get_cached_doc("Forecourt Site Preferences", company)
        except frappe.DoesNotExistError:
            continue
        threshold = prefs.stale_shift_hours or 10
        stale = frappe.db.sql("""
            SELECT name FROM `tabShift`
            WHERE company = %s AND status IN ('Open', 'Readings Captured')
            AND TIMESTAMPDIFF(HOUR, opening_at, NOW()) > %s
        """, (company, threshold), as_dict=True)
        for s in stale:
            create_alert(s.name, f"Shift {s.name} open > {threshold} h", "Stale Shift")


def send_daily_summary():
    pass  # Phase 6


def check_pdq_settlement_due():
    pass  # Phase 5


def retry_pts_buffer():
    pass  # Phase 8
