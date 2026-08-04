#!/bin/bash
set -e

# ═════════════════════════════════════════════════════════════════════
# FMS (Forecourt Management System) Project Structure Setup
# ═════════════════════════════════════════════════════════════════════
# 
# This script organizes FMS files into a proper Odoo module structure
# Usage: bash setup-fms-project.sh [PROJECT_ROOT]
#
# Creates:
#   fms/
#   ├── __init__.py
#   ├── __manifest__.py
#   ├── models/
#   ├── views/
#   ├── security/
#   ├── tests/
#   ├── reports/
#   ├── scripts/
#   ├── docs/
#   ├── static/
#   └── .gitignore

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get project root (default: current directory)
PROJECT_ROOT="${1:-.}"

echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}FMS Project Structure Setup${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}\n"

echo -e "${YELLOW}Project Root: ${PROJECT_ROOT}${NC}\n"

# Check if required files exist
echo -e "${YELLOW}Checking for required files...${NC}"
required_files=("dev-guide.py" "CLAUDE.md" "tasks.yaml" "fms-development.skill" "FMS_DEVELOPMENT_SYSTEM_README.md" "FMS_Complete_Specification_Technical_Guide.md")

for file in "${required_files[@]}"; do
    if [ ! -f "$PROJECT_ROOT/$file" ]; then
        echo -e "${RED}✗ Missing: $file${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Found: $file${NC}"
    fi
done

echo ""

# ═════════════════════════════════════════════════════════════════════
# 1. Create directory structure
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating directory structure...${NC}"

directories=(
    "models"
    "views"
    "security"
    "tests"
    "reports"
    "scripts"
    "docs"
    "static/src/css"
    "static/src/js"
    "data"
)

for dir in "${directories[@]}"; do
    mkdir -p "$PROJECT_ROOT/$dir"
    echo -e "${GREEN}✓ Created: $dir/${NC}"
done

echo ""

# ═════════════════════════════════════════════════════════════════════
# 2. Create __init__.py files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating __init__.py files...${NC}"

# Root __init__.py
cat > "$PROJECT_ROOT/__init__.py" << 'EOF'
"""
FMS (Forecourt Management System) for Odoo 18

A lightweight, operational fuel station management module for Odoo 18.
Solves shift-based fuel reconciliation with automatic residual allocation,
hard-gate validation, and GL integration.

Reference: FMS_Complete_Specification_Technical_Guide.md
"""

from . import models
EOF
echo -e "${GREEN}✓ Created: __init__.py${NC}"

# models __init__.py
cat > "$PROJECT_ROOT/models/__init__.py" << 'EOF'
"""FMS Models"""

from . import fms_shift
from . import fms_pump
from . import fms_logs
from . import fms_shift_entry
from . import fms_shift_reconciliation
EOF
echo -e "${GREEN}✓ Created: models/__init__.py${NC}"

# tests __init__.py
cat > "$PROJECT_ROOT/tests/__init__.py" << 'EOF'
"""FMS Unit Tests"""
EOF
echo -e "${GREEN}✓ Created: tests/__init__.py${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 3. Create __manifest__.py
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating __manifest__.py...${NC}"

cat > "$PROJECT_ROOT/__manifest__.py" << 'EOF'
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
        
        # Views
        "views/fms_pump_views.xml",
        "views/fms_shift_views.xml",
        "views/fms_shift_meter_views.xml",
        "views/fms_shift_dip_views.xml",
        "views/fms_shift_list_views.xml",
        
        # Reports
        "reports/fms_shift_reconciliation_report.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
    "external_dependencies": {
        "python": ["pytest"],
    },
    "post_init_hook": "post_init_hook",
}
EOF
echo -e "${GREEN}✓ Created: __manifest__.py${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 4. Organize documentation
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Organizing documentation...${NC}"

# Move to docs/
mv "$PROJECT_ROOT/FMS_Complete_Specification_Technical_Guide.md" "$PROJECT_ROOT/docs/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: docs/FMS_Complete_Specification_Technical_Guide.md${NC}" || \
    echo -e "${YELLOW}→ docs/FMS_Complete_Specification_Technical_Guide.md (already exists)${NC}"

mv "$PROJECT_ROOT/FMS_DEVELOPMENT_SYSTEM_README.md" "$PROJECT_ROOT/docs/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: docs/FMS_DEVELOPMENT_SYSTEM_README.md${NC}" || \
    echo -e "${YELLOW}→ docs/FMS_DEVELOPMENT_SYSTEM_README.md (already exists)${NC}"

# Move dev files to scripts/
mv "$PROJECT_ROOT/dev-guide.py" "$PROJECT_ROOT/scripts/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: scripts/dev-guide.py${NC}" || \
    echo -e "${YELLOW}→ scripts/dev-guide.py (already exists)${NC}"

mv "$PROJECT_ROOT/tasks.yaml" "$PROJECT_ROOT/scripts/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: scripts/tasks.yaml${NC}" || \
    echo -e "${YELLOW}→ scripts/tasks.yaml (already exists)${NC}"

# Move skill & memory to docs/
mv "$PROJECT_ROOT/fms-development.skill" "$PROJECT_ROOT/docs/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: docs/fms-development.skill${NC}" || \
    echo -e "${YELLOW}→ docs/fms-development.skill (already exists)${NC}"

mv "$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/docs/" 2>/dev/null && \
    echo -e "${GREEN}✓ Moved: docs/CLAUDE.md${NC}" || \
    echo -e "${YELLOW}→ docs/CLAUDE.md (already exists)${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 5. Create .gitignore
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating .gitignore...${NC}"

cat > "$PROJECT_ROOT/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
ENV/
env/
.venv

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# Odoo
odoo/
odoo_bin/

# Temp files
*.tmp
*.bak
PROGRESS.md
REPORT.md

# Node modules (if using JS)
node_modules/
npm-debug.log

# Database
*.db
*.sqlite
*.sqlite3
EOF
echo -e "${GREEN}✓ Created: .gitignore${NC}"

echo ""

# ═════════════════════════════════════════════════════════════════════
# 6. Create placeholder model files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating model placeholders...${NC}"

model_files=(
    "fms_shift.py"
    "fms_pump.py"
    "fms_logs.py"
    "fms_shift_entry.py"
    "fms_shift_reconciliation.py"
)

for model in "${model_files[@]}"; do
    if [ ! -f "$PROJECT_ROOT/models/$model" ]; then
        cat > "$PROJECT_ROOT/models/$model" << EOF
"""
$model — FMS Model

Reference: FMS_Complete_Specification_Technical_Guide.md
"""

from odoo import models, fields, api


# TODO: Implement model
EOF
        echo -e "${GREEN}✓ Created: models/$model${NC}"
    else
        echo -e "${YELLOW}→ models/$model (already exists)${NC}"
    fi
done

echo ""

# ═════════════════════════════════════════════════════════════════════
# 7. Create placeholder security files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating security placeholders...${NC}"

security_files=(
    "fms_groups.xml"
    "ir_model_access.xml"
    "ir_rule.xml"
)

for sec_file in "${security_files[@]}"; do
    if [ ! -f "$PROJECT_ROOT/security/$sec_file" ]; then
        cat > "$PROJECT_ROOT/security/$sec_file" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- TODO: Add security configuration -->
</odoo>
EOF
        echo -e "${GREEN}✓ Created: security/$sec_file${NC}"
    else
        echo -e "${YELLOW}→ security/$sec_file (already exists)${NC}"
    fi
done

echo ""

# ═════════════════════════════════════════════════════════════════════
# 8. Create placeholder view files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating view placeholders...${NC}"

view_files=(
    "fms_pump_views.xml"
    "fms_shift_views.xml"
    "fms_shift_meter_views.xml"
    "fms_shift_dip_views.xml"
    "fms_shift_list_views.xml"
)

for view_file in "${view_files[@]}"; do
    if [ ! -f "$PROJECT_ROOT/views/$view_file" ]; then
        cat > "$PROJECT_ROOT/views/$view_file" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- TODO: Add view configuration -->
</odoo>
EOF
        echo -e "${GREEN}✓ Created: views/$view_file${NC}"
    else
        echo -e "${YELLOW}→ views/$view_file (already exists)${NC}"
    fi
done

echo ""

# ═════════════════════════════════════════════════════════════════════
# 9. Create documentation files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating documentation templates...${NC}"

# RUNBOOK.md
if [ ! -f "$PROJECT_ROOT/docs/RUNBOOK.md" ]; then
    cat > "$PROJECT_ROOT/docs/RUNBOOK.md" << 'EOF'
# FMS Operations Runbook

Daily procedures for operating FMS (Forecourt Management System).

## Table of Contents
1. Opening Shift
2. During Shift
3. Closing Shift
4. Troubleshooting
5. Contact & Support

## Opening Shift

### Prerequisites
- Odoo instance running
- FMS module installed
- User logged in (supervisor or attendant role)

### Steps

1. Navigate to: **Forecourt → Shifts**
2. Click **Create** (new shift)
3. Fill in:
   - **Shift Date:** Today's date
   - **Shift Label:** Select (1_day, 2_evening, 3_night)
   - **Supervisor:** Select supervisor
4. Click **Save**
5. Click **Open Shift** (button)
   - System auto-populates opening meter/dip readings
6. Verify opening values are correct
7. Click **Save**

### What Happens
- Status changes: Draft → Open
- System fetches previous shift's closing readings
- Entry forms become editable
- Attendants can enter sales data

---

## During Shift

### Attendant Tasks

1. Enter meter readings (after each nozzle close or at shift end):
   - Navigate to opened shift
   - Scroll to "Pump Meters" section
   - For each pump:
     - Select pump (auto-filled)
     - Enter **Closing Elec Volume** (from pump display)
     - Enter **Closing Man Mech** (manual reading, if applicable)
   - System auto-calculates: Qty Sold, Amount

2. Enter dip readings (at shift end, usually):
   - Scroll to "Tank Dips" section
   - For each tank:
     - Select tank (auto-filled)
     - Enter **Closing Volume** (from dip stick)
     - System shows variance vs. opening
   
3. Track cash:
   - Note cash dropped to safe
   - Note AR (receivables) created
   - Note card/MPesa transfers
   - Note expenses paid from till

### Supervisor Tasks

- Monitor shift progress (optional)
- Review reconciliation (before close)
- Address discrepancies (if any)

---

## Closing Shift

### Prerequisites
- All meter/dip readings entered
- All cash/AR recorded
- No outstanding issues

### Steps

1. Click **Reconciliation** (read-only section)
   - System shows:
     - FC Cash balance (must = 0)
     - Stock variances (must be < meniscus)
     - Attendant balances (all must = 0)
     - Residual allocations (if any)

2. Review results:
   - If all shows ✅: proceed to step 3
   - If any ❌: investigate & fix before closing

3. Click **Close Shift** (button)
   - System performs hard gate checks:
     - FC Cash = 0 (exactly)?
     - All attendants clear?
     - Variances < meniscus?
   
4. If gates pass:
   - Logs written (meter_log, dip_log)
   - Journals posted (GL)
   - Status changes: Closing → Closed
   - Success message shown

5. If gates fail:
   - Error message shows which gate failed
   - Example: "FC Cash is +50 KES. Cannot close."
   - Supervisor must post adjustment, retry

### What Happens After Close
- Meter/dip logs locked (immutable)
- GL journals posted (sales, residuals, variance)
- Stock adjustments recorded
- Shift marked "Closed"
- Cannot be re-opened

---

## Troubleshooting

### "FC Cash Not Zero"

**Symptom:** Close button shows error: "FC Cash is ±X KES. Cannot close."

**Cause:** Total money in doesn't equal total money out.

**Solution:**
1. Check attendant cash reconciliation:
   - Navigate: Shift → Attendant Cash section
   - For each attendant, verify:
     - Sales + Receipts = Cash + AR + Card + Expenses + Balance
2. If one attendant is short/over:
   - Supervisor investigates
   - Posts adjustment entry (DR AR/Expense | CR FC Cash)
3. Retry close

**Example:**
```
Attendant John:
  In:  Sales 5000 + Receipts 0 = 5000
  Out: Cash 4950 + AR 0 + Card 0 + Expenses 0 = 4950
  Balance: -50 KES (SHORT)

Fix:
  Supervisor posts: DR Employee AR 50 | CR FC Cash 50
  Now balance = 0 ✅
```

---

### "Stock Variance Exceeds Meniscus"

**Symptom:** Close button shows error: "Tank T1: variance 2.00% exceeds meniscus 0.50%"

**Cause:** Tank volume loss/gain exceeds acceptable threshold.

**Solution:**
1. Re-dip the tank (physical recount)
2. Update dip reading with new value
3. Verify new variance is < meniscus
4. Retry close

**Example:**
```
Tank T1 (10,000L capacity):
  Opening: 10,000L
  Closing (first dip): 9,800L
  Variance: 200L (2.0%) → EXCEEDS 0.5% meniscus ❌

  Re-dip: 9,950L
  New Variance: 50L (0.5%) → OK ✅
```

---

### "Attendant Not Cleared"

**Symptom:** Close button shows error: "Attendant Sarah: balance -100.00 KES not cleared."

**Cause:** One attendant's cash doesn't balance.

**Solution:**
1. Locate attendant in Attendant Cash section
2. Check: Sales + Receipts vs. Cash + AR + Card + Expenses
3. Possible causes:
   - Cash short-changed a customer (enters AR instead)
   - Forgot to record a cash drop
   - Forgot to record an expense
4. Attendant explains or Supervisor posts correction
5. Retry close

---

### "Residual Allocation Unexpected"

**Symptom:** Reconciliation shows allocation: "Diesel -100L → Carwash +100L"

**Cause:** Attendant reported non-fuel sales under wrong category.

**Solution (Informational):**
- System detected: Carwash was lumped into Diesel reporting
- Auto-allocated: Moved 100L (worth 22,280 KES) from Diesel to Carwash
- GL posted automatically
- No action needed (expected behavior)

---

## Contact & Support

- **Technical Issues:** Check logs (Odoo admin panel)
- **Spec Reference:** FMS_Complete_Specification_Technical_Guide.md
- **Development:** See dev-guide.py in scripts/

---

**Last Updated:** 2026-08-04  
**Version:** 1.0 (Phase 1 MVP)
EOF
    echo -e "${GREEN}✓ Created: docs/RUNBOOK.md${NC}"
else
    echo -e "${YELLOW}→ docs/RUNBOOK.md (already exists)${NC}"
fi

# INSTALLATION.md
if [ ! -f "$PROJECT_ROOT/docs/INSTALLATION.md" ]; then
    cat > "$PROJECT_ROOT/docs/INSTALLATION.md" << 'EOF'
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
EOF
    echo -e "${GREEN}✓ Created: docs/INSTALLATION.md${NC}"
else
    echo -e "${YELLOW}→ docs/INSTALLATION.md (already exists)${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 10. Create data template
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating data templates...${NC}"

if [ ! -f "$PROJECT_ROOT/data/fms_site_preferences.xml" ]; then
    cat > "$PROJECT_ROOT/data/fms_site_preferences.xml" << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        <!-- FMS Site Preferences Template
             
             Customize for your fuel station:
             - acceptable_variance_pct: Default ±0.5% (0.005)
             - fc_cash_account_id: Cash asset account
             - employee_overage_account_id: AR/advance account
             - miscounted_expense_account_id: Expense account
        -->
        
        <!-- TODO: Add site preferences data -->
        
    </data>
</odoo>
EOF
    echo -e "${GREEN}✓ Created: data/fms_site_preferences.xml${NC}"
else
    echo -e "${YELLOW}→ data/fms_site_preferences.xml (already exists)${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 11. Create static files
# ═════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}Creating static file placeholders...${NC}"

if [ ! -f "$PROJECT_ROOT/static/src/css/fms_responsive.css" ]; then
    cat > "$PROJECT_ROOT/static/src/css/fms_responsive.css" << 'EOF'
/* FMS Responsive Design

   Mobile-first responsive styles for FMS forms.
   Ensures forms work on desktop, tablet, and phone.
*/

/* TODO: Add responsive CSS rules */

/* Mobile (320px - 767px) */
@media (max-width: 767px) {
    /* Stack form fields vertically */
}

/* Tablet (768px - 1024px) */
@media (min-width: 768px) and (max-width: 1024px) {
    /* Two-column layout */
}

/* Desktop (1025px+) */
@media (min-width: 1025px) {
    /* Three-column layout */
}
EOF
    echo -e "${GREEN}✓ Created: static/src/css/fms_responsive.css${NC}"
else
    echo -e "${YELLOW}→ static/src/css/fms_responsive.css (already exists)${NC}"
fi

echo ""

# ═════════════════════════════════════════════════════════════════════
# 12. Summary
# ═════════════════════════════════════════════════════════════════════

echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Project Structure Setup Complete!${NC}"
echo -e "${BLUE}═════════════════════════════════════════════════════════════${NC}\n"

# Print directory tree
echo -e "${YELLOW}Project Structure:${NC}\n"
tree -L 2 "$PROJECT_ROOT" 2>/dev/null || find "$PROJECT_ROOT" -type d -not -path '*/.*' | sort | sed 's|[^/]*/|  |g'

echo ""
echo -e "${YELLOW}Next Steps:${NC}\n"
echo "1. Review project structure:"
echo "   tree -L 2"
echo ""
echo "2. Initialize git repository (if not done):"
echo "   git init"
echo "   git add ."
echo "   git commit -m 'Initial FMS project structure'"
echo ""
echo "3. Create development branch:"
echo "   git checkout -b development"
echo ""
echo "4. Start first task:"
echo "   python scripts/dev-guide.py status"
echo "   python scripts/dev-guide.py task FMS-001"
echo ""
echo "5. Read documentation:"
echo "   cat docs/FMS_DEVELOPMENT_SYSTEM_README.md"
echo "   cat docs/INSTALLATION.md"
echo "   cat docs/RUNBOOK.md"
echo ""
echo -e "${GREEN}Ready to develop! 🚀${NC}\n"
