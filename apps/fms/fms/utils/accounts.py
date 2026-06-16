import frappe


def get_site_preferences(company):
    try:
        return frappe.get_cached_doc("Forecourt Site Preferences", company)
    except frappe.DoesNotExistError:
        frappe.throw(
            f"Forecourt Site Preferences not configured for company: {company}. "
            "Please set it up under FMS > Forecourt Site Preferences."
        )


def get_site_pos_profile(company):
    prefs = get_site_preferences(company)
    if not prefs.pos_profile:
        frappe.throw(f"POS Profile not set in Forecourt Site Preferences for {company}.")
    return prefs.pos_profile


def get_fuel_inventory_account(tank_warehouse, company):
    fuel_grade = frappe.db.get_value("Warehouse", tank_warehouse, "fms_fuel_grade")
    if fuel_grade:
        acct = frappe.db.get_value("Item", fuel_grade, "fms_inventory_account")
        if acct:
            return acct
    acct = frappe.db.get_value("Company", company, "default_inventory_account")
    return acct or frappe.throw(f"No inventory account for tank {tank_warehouse}")


def get_wetstock_variance_account(fuel_grade, company):
    if fuel_grade:
        acct = frappe.db.get_value("Item", fuel_grade, "fms_wetstock_variance_account")
        if acct:
            return acct
    prefs = get_site_preferences(company)
    return prefs.wetstock_variance_account or frappe.throw(
        f"Wetstock variance account not set in Forecourt Site Preferences for {company}."
    )
