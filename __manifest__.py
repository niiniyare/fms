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
        
        # Data
        "data/fms_site_preferences.xml",
        "data/fms_company_defaults.xml",
        
        # Views — list/menus first so menu_fms_root exists before pump views reference it
        "views/fms_shift_list_views.xml",
        "views/fms_pump_views.xml",
        "views/fms_site_preferences_views.xml",
        "views/fms_shift_views.xml",
        "views/fms_shift_meter_views.xml",
        "views/fms_shift_dip_views.xml",
        
        # Reports
        "reports/fms_shift_report.xml",
        "reports/fms_meter_movement_report.xml",
    ],
    "demo": [
        "demo/fms_demo_data.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "assets": {
        "web.assets_backend": [
            "fms/static/src/css/fms_responsive.css",
        ],
    },
}
