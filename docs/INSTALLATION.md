# FMS Installation Guide

Complete setup instructions for installing FMS on Odoo 18.

## Prerequisites

- Odoo 18 Community Edition (installed & running)
- PostgreSQL database
- Python 3.9+
- Odoo development dependencies

## Installation Steps

### 1. Clone / Copy FMS Module

```bash
# Copy FMS to your Odoo addons directory
cp -r fms /path/to/odoo/addons/

# Or clone if from git
git clone https://github.com/yourusername/fms.git /path/to/odoo/addons/fms
```

### 2. Install Python Dependencies (Optional)

```bash
pip install pytest pytest-cov
```

### 3. Start Odoo Server

```bash
cd /path/to/odoo
python odoo-bin -d test_fms
```

### 4. Create Test Database (if needed)

```bash
# Odoo will create database automatically on first start
# Or use Odoo web UI: Settings → Create Database
```

### 5. Install FMS Module

1. Go to: **Settings → Apps**
2. Click **Update Apps List**
3. Search: "FMS"
4. Click on "FMS (Forecourt Management System)"
5. Click **Install**

### 6. Post-Installation Setup

#### A. Create Master Data

**Fuel Products:**
- Settings → Products → Products
- Create each fuel product:
  - Name: Unleaded Extra, V-Power, Diesel Extra, etc.
  - Fuel: Yes (check box)
  - COGS Account: Set
  - Revenue Account: Set

**Pumps:**
- FMS → Settings → Pumps
- Create one pump per physical pump:
  - Name: UX5, UX6, DX5, etc.
  - Order: Sequential (1, 2, 3...)
  - Active: Yes

**Nozzles:**
- FMS → Settings → Nozzles
- Create one nozzle per pump/product combo:
  - Pump: Select
  - Nozzle Letter: A, B, C (or 1, 2, 3)
  - Product: Select (e.g., V-Power)
  - Order: Sequential

**Fuel Tanks:**
- Inventory → Locations
- Modify stock location for each tank:
  - Name: T1-VPower, T2-Unleaded, T3-Diesel, etc.
  - Is Fuel Tank: Yes (check box)
  - Fuel Product: Select
  - Tank Capacity (Liters): Enter

**GL Accounts:**
- Accounting → Chart of Accounts
- Ensure these exist (or create):
  - Fuel Revenue (Income)
  - Fuel COGS (Expense)
  - FC Cash (Asset)
  - Employee Advance (Asset)
  - Miscellaneous Expense

#### B. Assign Users

**Attendants:**
- Settings → Users & Companies
- For each attendant user:
  - Groups → Add: Fuel Station Attendant

**Supervisors:**
- For each supervisor:
  - Groups → Add: Fuel Station Supervisor

**Accountants:**
- For each accountant:
  - Groups → Add: Fuel Station Accountant

#### C. Configure Site Preferences

- FMS → Settings → Site Preferences
- Set:
  - Acceptable Variance %: 0.50 (default)
  - FC Cash Account: Select
  - Employee Overage Account: Select
  - Miscounted Expense Account: Select

### 7. Test Installation

#### Create Test Shift

1. FMS → Shifts → Create
2. Fill:
   - Shift Date: Today
   - Shift Label: 1_day
   - Supervisor: Select
3. Click **Save**
4. Click **Open Shift**
5. Verify opening values auto-populated
6. Click **Save**

#### Verify No Errors

1. Check Odoo logs (no Python errors)
2. Check browser console (F12: no JS errors)
3. Form should load without errors

#### Run Tests (Optional)

```bash
cd /path/to/fms
pytest tests/ -v
```

Expected: All tests passing

---

## Troubleshooting

### Module Installation Fails

**Error:** "Module FMS depends on missing modules"

**Solution:**
- Ensure Odoo core modules installed:
  - base, stock, account, point_of_sale, hr
- Try: Settings → Apps → Update Apps List
- Retry install

### Master Data Not Showing

**Error:** "No pumps found" when opening shift

**Solution:**
1. Check if pumps created: FMS → Settings → Pumps
2. Verify "Active" is checked
3. Verify nozzles created: FMS → Settings → Nozzles
4. Refresh page (F5)

### Shift Form Not Rendering

**Error:** Shift form shows blank or errors

**Solution:**
1. Check browser console (F12) for JS errors
2. Check Odoo logs for Python errors
3. Try different browser
4. Clear cache (Ctrl+Shift+Delete)
5. Restart Odoo server

### Tests Fail on Install

**Error:** Pytest errors during `python -m pytest`

**Solution:**
1. Install pytest: `pip install pytest`
2. Ensure Odoo installed in environment: `pip install odoo`
3. Run from FMS root: `pytest tests/ -v`

---

## Upgrade / Update

### Update FMS Module

```bash
# From Odoo web UI:
Settings → Apps → Search "FMS"
If "Upgrade" button available, click it

# Or from command line:
python odoo-bin -d database_name -u fms
```

### Migrate Data from Phase 1 to Phase 2

*(When Phase 2 released)*

Run migration script:
```bash
python scripts/migrate_phase2.py
```

---

## Uninstall

### Remove FMS Module

1. Go to: **Settings → Apps**
2. Search: "FMS"
3. Click on module
4. Click **Uninstall**

### (Optional) Delete Module Files

```bash
rm -rf /path/to/odoo/addons/fms
```

---

## Support

- **Spec Reference:** docs/FMS_Complete_Specification_Technical_Guide.md
- **Operations:** docs/RUNBOOK.md
- **Development:** scripts/dev-guide.py

---

**Last Updated:** 2026-08-04  
**Version:** 1.0 (Phase 1 MVP)
**Odoo Version:** 18.0 Community Edition
