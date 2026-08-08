{
    "name": "FMS (Forecourt Management System)",
    "version": "18.0.1.0.0",
    "category": "Inventory",
    "summary": "Fuel station shift management with automatic reconciliation",
    "description": """
FMS (Forecourt Management System) for Odoo 18

A lightweight, operational fuel station management module that solves
shift-based fuel reconciliation. Key features:

1. Shift Orchestration
   - Unified shift form (open/close workflow)
   - Opening/closing readings (meters & dips)
   - Attendant cash reconciliation

2. Automatic Reconciliation
   - Meter volume vs. tank dips
   - Reported vs. accounted sales
   - Automatic residual allocation (lumped non-fuel reallocation)

3. Hard Gates (Non-Negotiable Validation)
   - FC Cash must equal zero (exactly)
   - All attendants must clear
   - Stock variance within meniscus (±0.5% default)

4. GL Integration
   - Automatic journal posting (sales, residuals, variance)
   - Stock inventory adjustments
   - Immutable audit logs

5. Security
   - Role-based groups (attendant, supervisor, accountant)
   - Row-level security (company scoping)
   - Immutable log protection

Reference: Complete specification in FMS_Complete_Specification_Technical_Guide.md
""",
    "author": "Anika Global Limited",
    "depends": [
        "base",
        "mail",
        "account",
        "stock",
        "point_of_sale",
        "hr",
    ],
    "data": [
        # Security
        "security/fms_groups.xml",
        "security/ir_model_access.xml",
        "security/ir_rule.xml",
        
        # Data / sequences
        "data/fms_sequences.xml",
        "data/fms_site_preferences.xml",
        "data/fms_company_defaults.xml",

        # Menu structure first — all view files and menus depend on root/section menus
        "views/fms_menu_structure.xml",
        # Views — actions defined before anything that references them
        "views/fms_shift_list_views.xml",
        "views/fms_pump_views.xml",
        "views/fms_site_preferences_views.xml",
        "views/fms_shift_views.xml",
        "views/fms_shift_meter_views.xml",
        "views/fms_shift_dip_views.xml",
        "views/fms_price_period_views.xml",
        "views/fms_incident_views.xml",
        "views/fms_report_views.xml",
        "views/fms_report_views2.xml",
        "views/fms_setup_check_views.xml",
        # These two must load last — they reference actions from all files above
        "views/fms_overview_views.xml",
        "views/fms_menus.xml",

        # Reports
        "reports/fms_shift_report.xml",
        "reports/fms_daily_station_report.xml",
        "reports/fms_attendant_shift_statement.xml",
        "reports/fms_meter_movement_report.xml",

        # Cron / scheduled actions
        "data/fms_stock_alert_cron.xml",
    ],
    "demo": [
        "demo/fms_demo_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_backend": [
            "fms/static/src/css/fms_responsive.css",
        ],
    },
}
