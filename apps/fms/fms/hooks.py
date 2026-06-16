app_name = "fms"
app_title = "Forecourt Management System"
app_publisher = "Anika Global Limited"
app_description = "Forecourt Management System for petrol stations"
app_email = "admin@anikaglobal.co.ke"
app_license = "mit"
required_apps = ["frappe", "erpnext"]

doc_events = {
    "POS Invoice": {
        "validate":      "fms.overrides.pos_invoice.validate",
        "before_submit": "fms.overrides.pos_invoice.before_submit",
        "on_submit":     "fms.overrides.pos_invoice.on_submit",
        "on_cancel":     "fms.overrides.pos_invoice.on_cancel",
    },
    "Sales Invoice": {
        "before_submit": "fms.overrides.sales_invoice.before_submit",
        "on_submit":     "fms.overrides.sales_invoice.on_submit",
        "on_cancel":     "fms.overrides.sales_invoice.on_cancel",
    },
    "Purchase Receipt": {
        "validate":      "fms.overrides.purchase_receipt.validate",
        "before_submit": "fms.overrides.purchase_receipt.before_submit",
        "on_submit":     "fms.overrides.purchase_receipt.on_submit",
    },
    "Item Price": {
        "validate": "fms.overrides.item_price.validate",
    },
}

scheduler_events = {
    "cron": {
        "0 * * * *":    ["fms.tasks.check_stale_shifts"],
        "0 6 * * *":    ["fms.tasks.send_daily_summary"],
        "0 23 * * *":   ["fms.tasks.check_pdq_settlement_due"],
        "*/30 * * * *": ["fms.tasks.retry_pts_buffer"],
    },
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Forecourt Management System"]]},
    {"dt": "Role", "filters": [["name", "in", [
        "FMS Manager", "FMS Supervisor", "FMS Cashier",
        "FMS Attendant", "FMS Auditor", "FMS HQ",
    ]]]},
]
