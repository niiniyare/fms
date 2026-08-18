"""
FMS E2E Seed Script — Anika Global Limited / Shell Maanzoni Service Station
Run via:  make odoo-shell < scripts/seed_e2e.py
Database: fms_e2e  (created separately with Kenya locale)
"""
import logging
_logger = logging.getLogger(__name__)

env = self.env   # available in odoo-bin shell context

# ─────────────────────────────────────────────────────────────────────────────
# 1. COMPANY — Kenya locale, KES
# ─────────────────────────────────────────────────────────────────────────────
company = (
    env['res.company'].search([('name', '=', 'Anika Global Limited')], limit=1)
    or env['res.company'].search([], order='id asc', limit=1)
)
kenya = env.ref('base.ke')
kes = env['res.currency'].search([('name', '=', 'KES')], limit=1)
if not kes:
    kes = env['res.currency'].create({'name': 'KES', 'symbol': 'KSh', 'rounding': 0.01})

try:
    company.write({
        'name': 'Anika Global Limited',
        'country_id': kenya.id,
        'currency_id': kes.id,
        'street': 'Maanzoni Road',
        'city': 'Machakos',
        'phone': '+254700000000',
        'email': 'info@anikaglobal.co.ke',
        'vat': 'P051234567K',
    })
except Exception:
    env.cr.rollback()
    # Name already set — update other fields only
    company.write({
        'country_id': kenya.id,
        'currency_id': kes.id,
        'street': 'Maanzoni Road',
        'city': 'Machakos',
        'phone': '+254700000000',
        'email': 'info@anikaglobal.co.ke',
        'vat': 'P051234567K',
    })
env.cr.commit()
print(f"✓ Company set: {company.name} | {kes.name}")

# ─────────────────────────────────────────────────────────────────────────────
# 2. CHART OF ACCOUNTS — from QBO export
# ─────────────────────────────────────────────────────────────────────────────
AccountAccount = env['account.account']

def get_or_create_account(code, name, account_type, notes=''):
    acc = AccountAccount.search([('code', '=', code), ('company_ids', 'in', [company.id])], limit=1)
    if not acc:
        acc = AccountAccount.create({
            'code': code,
            'name': name,
            'account_type': account_type,
            'company_ids': [(4, company.id)],
        })
        print(f"  + {code} {name}")
    return acc

print("\n── Creating Chart of Accounts ──────────────────────────")

# ── ASSETS ────────────────────────────────────────────────────────────────────
get_or_create_account('101000', 'Cash in the Safe',          'asset_cash')
get_or_create_account('101001', 'Cash and Cash Equivalents', 'asset_cash')
get_or_create_account('102000', 'KCB Account',               'asset_cash')
get_or_create_account('102001', 'Equity Visa',               'asset_cash')
get_or_create_account('102002', 'KCB Visa',                  'asset_cash')
get_or_create_account('102003', 'Lipa Na Mpesa',             'asset_cash')
get_or_create_account('102004', 'Shell Card Account',        'asset_cash')
get_or_create_account('110000', 'Accounts Receivable (A/R)', 'asset_receivable')
get_or_create_account('120000', 'Inventory',                 'asset_current')
get_or_create_account('120001', 'Inventory Asset',           'asset_current')
get_or_create_account('121000', 'Undeposited Funds',         'asset_current')
get_or_create_account('130000', 'Prepaid Expenses',          'asset_prepayments')
get_or_create_account('140000', 'Employee Cash Advances',    'asset_current')
get_or_create_account('141000', 'Allowance for Bad Debt',    'asset_current')
# 191600 owned by fms module (fms_company_defaults.xml) — skip here
get_or_create_account('150000', 'Property, Plant & Equipment', 'asset_fixed')
get_or_create_account('151000', 'Accumulated Depreciation on PP&E', 'asset_fixed')
get_or_create_account('160000', 'Long-Term Investments',     'asset_non_current')
get_or_create_account('161000', 'Goodwill',                  'asset_non_current')
get_or_create_account('162000', 'Intangibles',               'asset_non_current')
get_or_create_account('163000', 'Deferred Tax Assets',       'asset_non_current')
get_or_create_account('164000', 'Assets Held for Sale',      'asset_non_current')

# ── LIABILITIES ───────────────────────────────────────────────────────────────
get_or_create_account('201000', 'Accounts Payable (A/P)',    'liability_payable')
get_or_create_account('210000', 'Income Tax Payable',        'liability_current')
get_or_create_account('211000', 'Payroll Liabilities',       'liability_current')
get_or_create_account('212000', 'Accrued Liabilities',       'liability_current')
get_or_create_account('213000', 'Dividends Payable',         'liability_current')
get_or_create_account('214000', 'Short-term Debt',           'liability_current')
get_or_create_account('215000', 'Inventory Offset',          'liability_current')
get_or_create_account('216000', 'Payroll Clearing',          'liability_current')
get_or_create_account('220000', 'Long-term Debt',            'liability_non_current')
get_or_create_account('221000', 'Accrued Non-Current Liabilities', 'liability_non_current')

# ── EQUITY ────────────────────────────────────────────────────────────────────
get_or_create_account('301000', 'Share Capital',             'equity')
get_or_create_account('302000', 'Retained Earnings',         'equity')
get_or_create_account('303000', 'Opening Balance Equity',    'equity')
get_or_create_account('304000', 'Dividend Disbursed',        'equity')
get_or_create_account('999999', 'Undistributed Profit/Loss', 'equity_unaffected')

# ── INCOME ────────────────────────────────────────────────────────────────────
get_or_create_account('400000', 'Sales of Product Income',   'income')
get_or_create_account('400001', 'Sales of Diesel Income',    'income')
get_or_create_account('400002', 'Sales of Unleaded Income',  'income')
get_or_create_account('400003', 'Sales of V-Power Income',   'income')
get_or_create_account('400004', 'Sales of LPG Income',       'income')
get_or_create_account('400005', 'Sales of Lubricants Income','income')
get_or_create_account('400006', 'Sales of Spare Parts Income','income')
get_or_create_account('401000', 'Car Wash Income',           'income')
get_or_create_account('401001', 'Rent Monthly Income',       'income')
get_or_create_account('401002', 'Services Income',           'income')
get_or_create_account('402000', 'Revenue - General',         'income')
get_or_create_account('403000', 'Discounts Given',           'income')
get_or_create_account('404000', 'VP Promo Credit Note',      'income')
get_or_create_account('410000', 'Dividend Income',           'income_other')
get_or_create_account('411000', 'Interest Income',           'income_other')
get_or_create_account('412000', 'Other Operating Income',    'income_other')

# ── COST OF GOODS SOLD ────────────────────────────────────────────────────────
get_or_create_account('500000', 'Cost of Sales',             'expense_direct_cost')
get_or_create_account('500001', 'Diesel Cost of Sales',      'expense_direct_cost')
get_or_create_account('500002', 'Unleaded Cost of Sales',    'expense_direct_cost')
get_or_create_account('500003', 'V-Power Cost of Sales',     'expense_direct_cost')
get_or_create_account('500004', 'LPG Cost of Sales',         'expense_direct_cost')
# 591000 owned by fms module (fms_company_defaults.xml) — skip here
get_or_create_account('510000', 'Inventory Shrinkage',       'expense_direct_cost')
get_or_create_account('511000', 'Tank Loss',                 'expense_direct_cost')
get_or_create_account('512000', 'Car Wash Purchases',        'expense_direct_cost')
get_or_create_account('513000', 'VP Compensation',           'expense_direct_cost')
get_or_create_account('514000', 'Freight and Delivery - COS','expense_direct_cost')

# ── EXPENSES ──────────────────────────────────────────────────────────────────
get_or_create_account('600000', 'Payroll Expenses',          'expense')
get_or_create_account('600001', 'Housing Levy',              'expense')
get_or_create_account('600002', 'NITA Levy',                 'expense')
get_or_create_account('600003', 'NSSF Employer Contribution','expense')
get_or_create_account('601000', 'Bank Charges',              'expense')
get_or_create_account('601001', 'Bank Commissions',          'expense')
get_or_create_account('602000', 'Generator Expenses',        'expense')
get_or_create_account('603000', 'Electric & Lighting Cost',  'expense')
get_or_create_account('603001', 'KPLC',                      'expense')
get_or_create_account('604000', 'Water Cost',                'expense')
get_or_create_account('604001', 'Plumbing Costs',            'expense')
get_or_create_account('605000', 'Security Guard Expenses',   'expense')
get_or_create_account('606000', 'Cleaning & Sanitation',     'expense')
get_or_create_account('607000', 'Repairs & Maintenance',     'expense')
get_or_create_account('608000', 'Office Expenses',           'expense')
get_or_create_account('609000', 'Stationery & Printing',     'expense')
get_or_create_account('610000', 'Motor Vehicle Running Cost','expense')
get_or_create_account('611000', 'Travel Expenses - G&A',     'expense')
get_or_create_account('612000', 'Meals & Entertainment',     'expense')
get_or_create_account('613000', 'Internet Expense',          'expense')
get_or_create_account('614000', 'Software Licences',         'expense')
get_or_create_account('615000', 'Equipment Rental',          'expense')
get_or_create_account('616000', 'Legal & Professional Fees', 'expense')
get_or_create_account('616001', 'Accounting Fees',           'expense')
get_or_create_account('617000', 'Insurance - General',       'expense')
get_or_create_account('617001', 'Insurance - Liability',     'expense')
get_or_create_account('618000', 'Income Tax Expense',        'expense')
get_or_create_account('619000', 'Dues & Subscriptions',      'expense')
get_or_create_account('620000', 'Forecourt Expenses',        'expense')
get_or_create_account('620001', 'Forecourt Throughput Charge','expense')
get_or_create_account('621000', 'Own Use Petroleum',         'expense')
get_or_create_account('622000', 'Director Drawings',         'expense')
get_or_create_account('623000', 'Sales Discount - Fuels',    'expense')
get_or_create_account('624000', 'Bad Debts',                 'expense')
get_or_create_account('625000', 'Amortisation Expense',      'expense')
get_or_create_account('626000', 'Interest Expense',          'expense')
get_or_create_account('627000', 'Advertising Expenses',      'expense')
get_or_create_account('628000', 'Wage Expenses',             'expense')
get_or_create_account('629000', 'Staff Meal Cost',           'expense')
get_or_create_account('630000', 'Zakat',                     'expense')
get_or_create_account('631000', 'Permit & License Fees',     'expense')
get_or_create_account('700000', 'Fire Safety Costs',         'expense')
get_or_create_account('700001', 'Garden Maintenance Cost',   'expense')
get_or_create_account('700002', 'Reconciliation Discrepancies','expense')
get_or_create_account('700003', 'Other Expense',             'expense')

env.cr.commit()
print("✓ Chart of accounts complete")

# ─────────────────────────────────────────────────────────────────────────────
# 3. PRODUCT CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Creating Product Categories ─────────────────────────")
ProductCategory = env['product.category']

def get_or_create_cat(name, parent_name=None):
    cat = ProductCategory.search([('name', '=', name)], limit=1)
    if not cat:
        vals = {'name': name}
        if parent_name:
            parent = ProductCategory.search([('name', '=', parent_name)], limit=1)
            if parent:
                vals['parent_id'] = parent.id
        cat = ProductCategory.create(vals)
        print(f"  + Category: {name}")
    return cat

cat_all      = get_or_create_cat('All')
cat_fuel     = get_or_create_cat('Fuel',         'All')
cat_lube     = get_or_create_cat('Lubricants',   'All')
cat_lube_eng = get_or_create_cat('Engine Oils',  'Lubricants')
cat_lube_trn = get_or_create_cat('Transmission Oils', 'Lubricants')
cat_lube_grs = get_or_create_cat('Greases',      'Lubricants')
cat_lube_car = get_or_create_cat('Car Care',     'Lubricants')
cat_lpg      = get_or_create_cat('LPG',          'All')
cat_filters  = get_or_create_cat('Filters',      'All')
cat_filt_oil = get_or_create_cat('Oil Filters',  'Filters')
cat_filt_air = get_or_create_cat('Air Filters',  'Filters')
cat_filt_fue = get_or_create_cat('Fuel Filters', 'Filters')
cat_filt_cab = get_or_create_cat('Cabin Filters','Filters')
cat_acc      = get_or_create_cat('Accessories',  'All')
cat_acc_bul  = get_or_create_cat('Bulbs',        'Accessories')
cat_acc_spa  = get_or_create_cat('Spark Plugs',  'Accessories')
cat_spare    = get_or_create_cat('Spare Parts',  'All')
cat_brake    = get_or_create_cat('Brake Parts',  'Spare Parts')
cat_carwash  = get_or_create_cat('Car Wash',     'All')

env.cr.commit()
print("✓ Categories done")

# ─────────────────────────────────────────────────────────────────────────────
# 4. UNITS OF MEASURE
# ─────────────────────────────────────────────────────────────────────────────
UoM = env['uom.uom']
uom_l   = UoM.search([('name', '=', 'L')], limit=1)       # Litres
uom_kg  = UoM.search([('name', '=', 'kg')], limit=1)      # Kilograms
uom_u   = UoM.search([('name', '=', 'Units')], limit=1)   # Units
if not uom_l:
    uom_l = UoM.search([('name', 'ilike', 'litr')], limit=1)
if not uom_u:
    uom_u = UoM.search([('name', 'ilike', 'unit')], limit=1)
if not uom_u:
    uom_u = UoM.search([], limit=1)

# ─────────────────────────────────────────────────────────────────────────────
# 5. PRODUCTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Creating Products ───────────────────────────────────")
Product = env['product.product']
ProductTemplate = env['product.template']
StockQuant = env['stock.quant']
stock_loc = env.ref('stock.stock_location_stock')

def make_product(name, categ, cost, price, qty, uom=None, fms_fuel=False, fms_is_attendant=False, notes=''):
    """Create product template + set opening stock."""
    if uom is None:
        uom = uom_u
    tmpl = ProductTemplate.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not tmpl:
        tmpl = ProductTemplate.search([('name', '=', name)], limit=1)
    if tmpl:
        prod = tmpl.product_variant_ids[:1]
        # Always update price and fms_is_fuel even when product already exists
        tmpl.write({'list_price': price, 'standard_price': cost})
        if fms_fuel and prod:
            prod.write({'fms_is_fuel': True})
        return prod

    tmpl = ProductTemplate.create({
        'name': name,
        'categ_id': categ.id,
        'standard_price': cost,
        'list_price': price,
        'uom_id': uom.id if uom else False,
        'uom_po_id': uom.id if uom else False,
        'type': 'consu',
        'company_id': company.id,
    })
    prod = tmpl.product_variant_ids[:1]
    if fms_fuel and prod:
        prod.write({'fms_is_fuel': True})

    # Opening stock
    if qty and qty > 0 and prod and stock_loc:
        try:
            quant = StockQuant.search([
                ('product_id', '=', prod.id),
                ('location_id', '=', stock_loc.id),
            ], limit=1)
            if quant:
                quant.inventory_quantity = qty
                quant.action_apply_inventory()
            else:
                StockQuant._update_available_quantity(prod, stock_loc, qty)
        except Exception as e:
            print(f"    ! Stock warning for {name}: {e}")
    print(f"  + {name} | cost={cost} | price={price} | qty={qty}")
    return prod

# ── FUEL PRODUCTS ─────────────────────────────────────────────────────────────
print("\n  [FUEL]")
# Selling prices set to pump prices (approximate; update from site preferences)
make_product('V-Power',        cat_fuel, 177.33, 203.00, 4441.46, uom_l, fms_fuel=True)
make_product('Unleaded Extra', cat_fuel, 168.09, 190.00, 15466.33, uom_l, fms_fuel=True)
make_product('Diesel Extra',   cat_fuel, 158.59, 181.00, 25794.90, uom_l, fms_fuel=True)

# ── LPG ───────────────────────────────────────────────────────────────────────
print("\n  [LPG]")
make_product('Gas Load 6KG',        cat_lpg, 1210.00, 1500.00, 7.0)
make_product('Gas Load 13KG',       cat_lpg, 2770.00, 3200.00, 12.0)
make_product('Empty Cylinder 6KG',  cat_lpg, 1800.00, 2200.00, 8.0)
make_product('Empty Cylinder 13KG', cat_lpg, 3400.00, 4200.00, 18.0)

# ── ENGINE OILS ───────────────────────────────────────────────────────────────
print("\n  [ENGINE OILS]")
# T suffix: T1=1L, T1/2=0.5L, T4=4L, T5=5L  — cost is per pack/piece from PDF
# Selling price from RRP in Excel where available
engine_oils = [
    # name,                          cost,    price,   qty
    ('Advance 2T SX 0.5L',          207.41,  265.00,  38.0),   # T1/2
    ('Advance 4T AX3 1L',           369.95,  500.00,   5.0),   # T1 (AX5≈AX3 price)
    ('Advance 4T AX5 1L',           389.70,  500.00,   2.0),
    ('Helix HX3 40 1L',             369.95,  470.00,  21.0),
    ('Helix HX3 40 0.5L',           195.30,  250.00,  46.0),
    ('Helix HX5 15W40 1L',          458.80,  590.00,  15.0),
    ('Helix HX5 15W40 0.5L',        247.63,  320.00,  42.0),
    ('Helix HX5 15W40 4L',         1772.40, 2280.00,  36.0),
    ('Helix HX7 10W40 1L',          682.51,  885.00,  28.0),
    ('Helix HX8 5W40 1L',           790.55, 1025.00,  52.0),
    ('Helix HX8 5W40 4L',          2997.56, 3895.00,  27.0),
    ('Helix Ultra 5W40 1L',         917.80, 1190.00,  19.0),
    ('Rimula R1 CD 40 1L',          389.93,  500.00,   4.0),
    ('Rimula R1 CD 40 5L',         1773.70, 2300.00,  12.0),
    ('Rimula R3 Turbo 1L',          438.52,  570.00,   8.0),
    ('Rimula R4X 15W40 1L',         535.03,  690.00,  39.0),
    ('Rimula R4X 15W40 5L',        2651.55, 3450.00,   3.0),
    ('Rimula R6 LM 10W40 CJ4 4L', 2523.20, 3280.00,   1.0),
]
for name, cost, price, qty in engine_oils:
    make_product(name, cat_lube_eng, cost, price, qty)

# ── TRANSMISSION OILS ─────────────────────────────────────────────────────────
print("\n  [TRANSMISSION OILS]")
trans_oils = [
    ('Battery Acid 1L',              120.00,  225.00,   3.0),
    ('Brake Fluid DOT 4 0.5L',       427.75,  550.00,  53.0),
    ('Brake Fluid DOT 4 200ML',       235.43,  310.00,  25.0),
    ('Special Coolant 5L',          2433.95, 3150.00,   8.0),
    ('Spirax S2 G 140 4L',          1879.16, 2440.00,   4.0),
    ('Spirax S2 G 90 4L',           1900.32, 2470.00,   8.0),
    ('Spirax S2 ATF D2 1L',          500.63,  650.00,  14.0),
    ('Spirax S2 ATF D2 4L',         1956.24, 2540.00,   8.0),
    ('Spirax S2 ATF D2 0.5L',        262.67,  340.00,  31.0),
    ('Spirax S5 ATF X 1L',          1187.40, 1545.00,   6.0),
    ('Shell Premium Long-Life AF Coolant 1L', 517.87, 675.00, 14.0),
]
for name, cost, price, qty in trans_oils:
    make_product(name, cat_lube_trn, cost, price, qty)

# ── GREASES ───────────────────────────────────────────────────────────────────
print("\n  [GREASES]")
make_product('Greasing Runs 1KG', cat_lube_grs, 469.81, 610.00, 13.84)

# ── CAR CARE PRODUCTS ─────────────────────────────────────────────────────────
print("\n  [CAR CARE]")
car_care = [
    ('My Tone Grace',              258.62,  340.00, 10.0),
    ('De-Rust Lubricating Spray',  215.52,  280.00,  3.0),
    ('Carburetor & Choke Cleaner', 215.52,  280.00,  6.0),
    ('Sparko Epoxy',               112.07,  150.00, 13.0),
    ('Silicon Grey 35GMS',          86.21,  115.00, 11.0),
    ('Silicon Grey 85.2GMS',        155.17, 210.00,  2.0),
]
for name, cost, price, qty in car_care:
    make_product(name, cat_lube_car, cost, price, qty)

# ── OIL FILTERS ───────────────────────────────────────────────────────────────
print("\n  [OIL FILTERS]")
oil_filters = [
    ('Oil Filter 15208-65F00',         155.17,  215.00, 16.0),
    ('Oil Filter 8-97148270-1',        689.65,  900.00,  1.0),
    ('Oil Filter 90915-10001',         155.17,  215.00,  3.0),
    ('Oil Filter 04152-37010',         215.52,  280.00, 25.0),
    ('Oil Filter 04152-31080/31060',   258.62,  340.00,  6.0),
    ('Oil Filter MITSU MD135737',      155.17,  215.00, 12.0),
    ('Oil Filter PH8A',                258.62,  340.00,  2.0),
    ('Oil Filter 90915-03002/20001',   172.41,  225.00,  6.0),
    ('Oil Filter 15208-AA100',         215.52,  280.00,  4.0),
    ('Oil Filter 90915-10004/03004',   155.17,  215.00,  6.0),
    ('Oil Filter 8-97309927-0',        387.93,  505.00,  3.0),
    ('Oil Filter DMAX 8-98165071-0',   431.03,  560.00,  2.0),
    ('Oil Filter MDO69782',            344.83,  450.00,  3.0),
    ('Oil Filter ORIG 90915-10004',    517.24,  675.00,  2.0),
    ('Oil Filter ORG 04152-37010',     431.03,  560.00,  1.0),
    ('Oil Filter ORG 04152-38010',     431.03,  560.00,  4.0),
    ('Oil Filter ORG 15208-AA100',     517.24,  675.00,  1.0),
    ('Oil Filter 04152-31060',         431.03,  560.00,  3.0),
    ('Oil Filter NISSAN 15208-122W',   241.38,  315.00,  2.0),
    ('Oil Filter MITSUBISHI 1-878100-75-1', 301.72, 395.00, 3.0),
    ('Oil Filter ISUZU FSR 1-87810372-1',  344.83, 450.00, 3.0),
    ('Oil Filter 04152-38020',         180.00,  235.00,  5.0),
]
for name, cost, price, qty in oil_filters:
    make_product(name, cat_filt_oil, cost, price, qty)

# ── AIR FILTERS (key items only — full list is 60+ SKUs) ─────────────────────
print("\n  [AIR FILTERS]")
air_filters = [
    ('Air Cleaner 17801-22020',    258.62,  340.00,  6.0),
    ('Air Cleaner 17801-35020',    344.83,  450.00,  1.0),
    ('Air Cleaner 17801-30040',    431.03,  560.00,  4.0),
    ('Air Cleaner 17801-31110',    215.52,  280.00,  5.0),
    ('Air Cleaner 17801-31120',    344.83,  450.00,  8.0),
    ('Air Cleaner 17801-30060 7L', 301.72,  395.00,  4.0),
    ('Air Cleaner OH20/17801-20040',344.83, 450.00,  6.0),
    ('Air Cleaner 16546-VO100',    258.62,  340.00,  3.0),
    ('Air Cleaner 17801-23030',    258.62,  340.00,  1.0),
    ('Air Cleaner 17801-OC010',    603.45,  785.00,  6.0),
    ('Air Cleaner 17801-61030',    387.93,  505.00,  3.0),
    ('Air Cleaner 2KD 17801-67040',387.93,  505.00,  3.0),
    ('Air Cleaner 16546-ED060',    258.62,  340.00,  2.0),
    ('Air Cleaner 16546-JD20B',    301.72,  395.00,  4.0),
    ('Air Cleaner 17801-21050',    258.62,  340.00,  2.0),
    ('Air Filter 17801-74020',     258.62,  340.00,  6.0),
    ('Cabin Filter 87139-06050',   387.93,  505.00, 24.0),
    ('Air Cleaner 17801-11090',    258.62,  340.00,  5.0),
    ('Air Cleaner DMAX 8-98140265-0', 560.34, 730.00, 3.0),
    ('Air Cleaner PAJ MR404847',   431.03,  560.00,  1.0),
    ('Air Cleaner MITSU GALANT MR266849', 301.72, 395.00, 5.0),
    ('Air Cleaner MR993226',       431.03,  560.00,  6.0),
    ('Air Filter SUBARU 16546-AA090', 387.93, 505.00, 4.0),
    ('Air Cleaner MITSUBISHI ME033717', 1403.51, 1825.00, 1.0),
    ('Air Cleaner ISUZU 1-14215-077-0', 1206.90, 1570.00, 1.0),
]
for name, cost, price, qty in air_filters:
    make_product(name, cat_filt_air, cost, price, qty)

# ── FUEL FILTERS ──────────────────────────────────────────────────────────────
print("\n  [FUEL FILTERS]")
fuel_filters = [
    ('Fuel Filter 23390-OL041/OL010', 344.83, 450.00, 4.0),
    ('Fuel Filter 23303-64010',       258.62, 340.00, 1.0),
    ('Fuel Filter 59E00',             172.41, 225.00, 1.0),
    ('Fuel Filter 16403-Z7000',       172.41, 225.00, 2.0),
    ('Fuel Filter 8-94414796-3',      129.31, 170.00, 4.0),
    ('Fuel Filter D-MAX 8-972886947-0',215.52, 280.00, 2.0),
    ('Fuel Filter 7L OGR 23390-0L041',431.03, 560.00, 1.0),
    ('Fuel Filter 6FGF-5018',         862.07,1120.00, 1.0),
    ('Fuel Filter 1-13240-194-0',     301.72, 395.00, 4.0),
    ('Fuel Filter 9-885131111/SF1004',  86.21, 115.00, 3.0),
    ('Fuel Filter REVO 23390-OL070',  474.14, 620.00, 1.0),
    ('Fuel Filter MB 220900',         301.72, 395.00, 2.0),
    ('Fuel Filter 04234-68010',       560.35, 730.00, 1.0),
    ('Fuel Filter 23390-51070',       344.83, 450.00,10.0),
    ('Fuel Filter ORG 23390-51070',   517.24, 675.00, 5.0),
]
for name, cost, price, qty in fuel_filters:
    make_product(name, cat_filt_fue, cost, price, qty)

# ── CABIN FILTERS ─────────────────────────────────────────────────────────────
print("\n  [CABIN FILTERS]")
cabin_filters = [
    ('Cabin Filter 87139-47010', 387.93, 505.00, 7.0),
    ('Cabin Filter 87139-12010', 215.52, 280.00, 6.0),
    ('Oil Filter 04152-31090',   387.93, 505.00, 3.0),
]
for name, cost, price, qty in cabin_filters:
    make_product(name, cat_filt_cab, cost, price, qty)

# ── BULBS & HEAD LAMPS ────────────────────────────────────────────────────────
print("\n  [ACCESSORIES - BULBS]")
bulbs = [
    ('Klaxcar Bulbs Single/Double 12V', 43.10,  60.00, 10.0),
    ('Klaxcar Bulbs Single/Double 24V', 43.10,  60.00, 19.0),
    ('Koito Halogen Lamp 24V',         258.62, 340.00,  1.0),
    ('Klaxcar H4 Halogen Bulb 12/24V', 301.72, 395.00,  4.0),
    ('Klaxcar Parking Bulbs 12/24V',    43.10,  60.00, 17.0),
    ('Capless Bulbs',                  129.31, 170.00,  9.0),
]
for name, cost, price, qty in bulbs:
    make_product(name, cat_acc_bul, cost, price, qty)

# ── SPARK PLUGS ───────────────────────────────────────────────────────────────
print("\n  [ACCESSORIES - SPARK PLUGS]")
spark_plugs = [
    ('Spark Plug Denso K16TR11',         215.52,  280.00, 16.0),
    ('Spark Plug K16UR-11',              215.52,  280.00,  9.0),
    ('Spark Plug Nissan ORIG 22401-8H516',560.34, 730.00, 14.0),
    ('Spark Plug Denso SK20R11',         689.66,  900.00, 10.0),
    ('Spark Plug Denso FK20HBR11',       948.28, 1235.00,  4.0),
    ('Spark Plug Denso SK20BGR11',       948.28, 1235.00,  6.0),
    ('Spark Plug Denso SC20HR11',        948.28, 1235.00,  8.0),
    ('Spark Plug NGK BKR5EGP',          689.66,  900.00,  4.0),
    ('Spark Plug IZFR6K-11',            948.28, 1235.00, 10.0),
    ('Spark Plug FK20HR11',             689.66,  900.00, 10.0),
    ('Spark Plug FXE20HR11',            948.28, 1235.00, 12.0),
    ('Spark Plug FXE20HE11',            948.28, 1235.00,  6.0),
]
for name, cost, price, qty in spark_plugs:
    make_product(name, cat_acc_spa, cost, price, qty)

# ── PATCHES & GAITERS ─────────────────────────────────────────────────────────
print("\n  [ACCESSORIES - PATCHES]")
patches_cat = get_or_create_cat('Patches & Gaiters', 'Accessories')
patches = [
    ('Tubeless Patch',   10.34,  15.00, 59.0),
    ('Tube Patch No.1',  18.68,  25.00,  4.0),
    ('Tube Patch No.3',  34.48,  45.00, 30.0),
    ('Tube Patch No.5',  94.83, 125.00,  8.0),
    ('Tubeless Nozzle',  17.24,  25.00, 20.0),
    ('Insulating Tape',  34.48,  45.00,  3.0),
]
for name, cost, price, qty in patches:
    make_product(name, patches_cat, cost, price, qty)

# ── BRAKE PARTS ───────────────────────────────────────────────────────────────
print("\n  [SPARE PARTS - BRAKE PARTS]")
brake_parts = [
    ('Brake Pad Virgo KD2735',          1077.59, 1400.00, 1.0),
    ('Brake Pad Prado Rear KD2281',      818.97, 1065.00, 2.0),
    ('Brake Pad Mark X Rear KD2506',    1336.21, 1740.00, 2.0),
    ('Brake Pad Nissan Murano KD1726',  1465.52, 1905.00, 1.0),
    ('Brake Pad Nissan Murano KD1739',  1465.52, 1905.00, 1.0),
    ('Brake Pad Honda CRV KD1508',      1250.00, 1625.00, 1.0),
    ('Brake Pad Honda CRV KD1702',       862.07, 1120.00, 1.0),
    ('Brake Pad Mitsubishi KD1544',     1465.52, 1905.00, 2.0),
    ('Brake Pad Honda CRV Front AP100', 1250.00, 1625.00, 1.0),
]
for name, cost, price, qty in brake_parts:
    make_product(name, cat_brake, cost, price, qty)

# ── ASSORTED SPARES ───────────────────────────────────────────────────────────
print("\n  [SPARE PARTS - ASSORTED]")
assorted_cat = get_or_create_cat('Assorted Spares', 'Spare Parts')
make_product('Radiator Caps Assorted', assorted_cat, 258.62, 340.00, 19.0)
make_product('Wipers Assorted',        assorted_cat, 175.49, 230.00, 58.0)

# ── CAR WASH ──────────────────────────────────────────────────────────────────
print("\n  [CAR WASH]")
make_product('Car Wash - Standard', cat_carwash, 0.0, 500.00, 0.0)
make_product('Car Wash - SUV',      cat_carwash, 0.0, 700.00, 0.0)

env.cr.commit()
print("\n✓ All products created")

# ─────────────────────────────────────────────────────────────────────────────
# 6. FMS SITE PREFERENCES — wire accounts
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Wiring FMS Site Preferences ─────────────────────────")
site_prefs = env['fms.site.preferences'].search([('company_id', '=', company.id)], limit=1)
if not site_prefs:
    site_prefs = env['fms.site.preferences'].create({'company_id': company.id})

clearing_acc = AccountAccount.search([('code', '=', '191600'), ('company_ids', 'in', [company.id])], limit=1)
if clearing_acc:
    site_prefs.write({'clearing_account_id': clearing_acc.id})
    print(f"  ✓ Clearing account: {clearing_acc.code} {clearing_acc.name}")

env.cr.commit()

# Wire fuel products with GL accounts
fuel_rev_acc  = AccountAccount.search([('code', '=', '400000'), ('company_ids', 'in', [company.id])], limit=1)
fuel_cogs_acc = AccountAccount.search([('code', '=', '591000'), ('company_ids', 'in', [company.id])], limit=1)

# Wire GL accounts on ALL fuel products (fms_is_fuel=True) including nozzle-linked ones
all_fuel_prods = env['product.product'].search([('fms_is_fuel', '=', True)])
# Also pick up any products linked to nozzles that may not be flagged yet
nozzle_prods = env['fms.pump.nozzle'].search([]).mapped('product_id')
for np in nozzle_prods.filtered(lambda p: not p.fms_is_fuel):
    np.write({'fms_is_fuel': True})
    print(f"  ✓ fms_is_fuel=True on nozzle product: {np.name}")
all_fuel_prods |= nozzle_prods.filtered(lambda p: p.fms_is_fuel)

if fuel_rev_acc and fuel_cogs_acc:
    for prod in all_fuel_prods:
        prod.write({
            'fms_revenue_account_id': fuel_rev_acc.id,
            'fms_cogs_account_id': fuel_cogs_acc.id,
        })
    print(f"  ✓ GL wired on {len(all_fuel_prods)} fuel product(s)")

env.cr.commit()

# ─────────────────────────────────────────────────────────────────────────────
# 7. PUMPS, NOZZLES, FUEL TANKS
# ─────────────────────────────────────────────────────────────────────────────
print("\n── Pumps, Nozzles & Fuel Tanks ──────────────────────")
StorLoc = env['stock.location']

fuel_prods = env['product.product'].search([('fms_is_fuel', '=', True)])
diesel_prod = fuel_prods.filtered(lambda p: 'Diesel' in p.name and 'Extra' in p.name)[:1]
unleaded_prod = fuel_prods.filtered(lambda p: 'Unleaded' in p.name)[:1]
vpower_prod = fuel_prods.filtered(lambda p: 'V-Power' in p.name)[:1]

parent_loc = StorLoc.search([('usage', '=', 'internal'), ('company_id', '=', company.id)], limit=1)
if not parent_loc:
    parent_loc = StorLoc.search([('usage', '=', 'internal')], limit=1)

tanks = StorLoc.search([('fms_is_fuel_tank', '=', True)])
if not tanks:
    for prod, tname in [(diesel_prod, 'Tank 1 Diesel'), (unleaded_prod, 'Tank 2 Unleaded'), (vpower_prod, 'Tank 3 V-Power')]:
        if prod:
            StorLoc.create({'name': tname, 'usage': 'internal', 'company_id': company.id,
                            'fms_is_fuel_tank': True, 'fms_fuel_product_id': prod.id,
                            'location_id': parent_loc.id})
    tanks = StorLoc.search([('fms_is_fuel_tank', '=', True)])
    print(f"  ✓ Created {len(tanks)} fuel tanks")
else:
    print(f"  ✓ Tanks exist: {tanks.mapped('name')}")

Pump = env['fms.pump']
if not Pump.search([]):
    p1 = Pump.create({'name': 'Pump 1', 'code': 'P1'})
    p2 = Pump.create({'name': 'Pump 2', 'code': 'P2'})
    Noz = env['fms.pump.nozzle']
    for pump, prods in [(p1, [diesel_prod, unleaded_prod]), (p2, [diesel_prod, vpower_prod])]:
        for i, prod in enumerate(prods):
            letter = chr(65 + i)  # A, B
            if prod:
                Noz.create({'pump_id': pump.id, 'name': f'{pump.code}-{letter}',
                            'letter': letter, 'product_id': prod.id})
    print(f"  ✓ Created 2 pumps, 4 nozzles")
else:
    print(f"  ✓ Pumps exist: {Pump.search([]).mapped('name')}")

env.cr.commit()

# ─────────────────────────────────────────────────────────────────────────────
# 8. ATTENDANTS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[8] Attendants ...")
Employee = env['hr.employee']
ATTENDANTS = [
    ('Ali Hassan',    'ali.hassan'),
    ('Fatuma Omar',   'fatuma.omar'),
    ('Kibe Mwangi',   'kibe.mwangi'),
    ('Grace Njeri',   'grace.njeri'),
]
for full_name, _ in ATTENDANTS:
    existing = Employee.search([('name', '=', full_name)], limit=1)
    if not existing:
        Employee.create({
            'name': full_name,
            'fms_is_attendant': True,
            'company_id': company.id,
        })
        print(f"  ✓ Created attendant: {full_name}")
    else:
        if not existing.fms_is_attendant:
            existing.fms_is_attendant = True
        print(f"  · Attendant exists: {full_name}")

env.cr.commit()

# ─────────────────────────────────────────────────────────────────────────────
# 9. SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
total_products = env['product.template'].search_count([('company_id', '=', company.id)])
total_accounts = AccountAccount.search_count([('company_ids', 'in', [company.id])])

print(f"""
╔══════════════════════════════════════════════════╗
║  FMS E2E Seed Complete                          ║
╠══════════════════════════════════════════════════╣
║  Company : {company.name:<36} ║
║  Currency: {kes.name:<36} ║
║  Accounts: {total_accounts:<36} ║
║  Products: {total_products:<36} ║
╚══════════════════════════════════════════════════╝
""")
