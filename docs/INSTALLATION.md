# FMS Installation Guide

Forecourt Management System — Odoo 18 Community Edition  
Version: 18.0.1.0.0 | Author: Anika Global Limited

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Odoo | 18.0 Community | Enterprise also works |
| Python | 3.10 – 3.12 | Must match Odoo's venv |
| PostgreSQL | 14 – 16 | |
| RAM | 2 GB min | 4 GB recommended for multi-user |

Odoo must have these standard modules installed (FMS declares them as dependencies):
`base`, `mail`, `account`, `stock`, `point_of_sale`, `hr`

---

## 1. Copy the Module

Place the `fms` directory inside any folder listed on your `--addons-path`.

```bash
# Example: if custom addons live in /opt/odoo/custom-addons/
cp -r /path/to/fms /opt/odoo/custom-addons/fms

# Verify the manifest is present
ls /opt/odoo/custom-addons/fms/__manifest__.py
```

The directory name **must** remain `fms` — it is the technical module name used in all XML `ref=` attributes and `ir.model.access` records.

---

## 2. Update Addons Path

In your Odoo configuration file (`odoo.conf`):

```ini
[options]
addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom-addons
```

Or pass it on the command line:

```
--addons-path=/opt/odoo/odoo/addons,/opt/odoo/custom-addons
```

---

## 3. Install the Module

### Via the web UI

1. Log in as an Odoo Administrator.
2. **Settings → Activate developer mode** (if not already on).
3. **Apps → Update Apps List**.
4. Search for `Forecourt` or `FMS`.
5. Click **Install**.

### Via the command line

```bash
python /opt/odoo/odoo-bin \
    -d production \
    -i fms \
    --addons-path=/opt/odoo/odoo/addons,/opt/odoo/custom-addons \
    --stop-after-init
```

Using the project Makefile (development only):

```bash
make odoo-install    # installs into the DB named test_fms
```

---

## 4. Post-Install Configuration

All steps below require the **Accountant / Manager** FMS role (or Odoo Administrator).

### 4.1 Chart of Accounts

FMS posts GL entries on every shift close. You need these account types:

| Purpose | Account type | Count |
|---|---|---|
| Fuel Revenue (per product grade) | Income | One per fuel grade |
| Fuel COGS (per product grade) | Expense — Direct Cost | One per fuel grade |
| Cash Clearing / Forecourt Float | Asset — Receivable | One shared account |

Create any missing accounts in **Accounting → Configuration → Chart of Accounts**. Exact names are your choice — you will link them in steps 4.3 and 4.4.

### 4.2 Forecourt Sales Journal

FMS needs one **Sale**-type journal for all shift posting.

1. **Accounting → Configuration → Journals → New**.
2. Name: `Forecourt Sales`, Type: `Sale`.
3. Currency: your company default.

### 4.3 Site Preferences

**Forecourt → Configuration → Site Preferences**

| Field | Recommended value | Effect |
|---|---|---|
| Variance Meniscus (%) | `0.5` | Tank dip variance limit before shift close is blocked |
| Cash Clearing Account | Account from step 4.1 | DR on every shift close (total cash meter KES) |
| Forecourt Sales Journal | Journal from step 4.2 | Journal used for all GL entries |
| Default Fuel Revenue Account | Main income account | Pre-filled on new fuel products |
| Default Fuel COGS Account | Main COGS account | Pre-filled on new fuel products |
| Auto-sync Attendant Cash Lines | ✓ enabled | Creates cash reconciliation rows when "Start Closing" is clicked |

### 4.4 Fuel Products

In **Inventory → Products** (or **Point of Sale → Products**), for each fuel grade:

1. Open (or create) the product.
2. On the **General Information** tab, tick **Is Fuel Product**.
3. Set **Fuel Revenue Account** and **Fuel COGS Account**.
4. Set the **Sales Price** — this is stored as `price_at_close` when residual allocations convert liters to KES.

Non-fuel products sold at the forecourt (carwash, LPG, oils) do **not** need the fuel flag. They are handled by the residual allocation algorithm.

### 4.5 Fuel Tanks

**Inventory → Configuration → Locations**

For each underground storage tank:

1. Open the location (create one with Usage = `Internal` if needed).
2. Tick **Is Fuel Tank**.
3. Set **Fuel Product in Tank** to the matching grade.

Tank locations are used for dip readings and the stock variance hard gate.

### 4.6 Pumps and Nozzles

**Forecourt → Configuration → Pumps**

1. Create one **Pump** record per physical pump unit (e.g. `Pump 1`, `Pump 2`).
2. Inside each pump, add one row per nozzle (A, B, …).
3. Set the **Product** for each nozzle — each nozzle dispenses exactly one fuel grade.
4. **Set the current meter totalizer readings** on each nozzle:
   - **Elec Cash (KES)** — the electronic cash totalizer reading right now
   - **Elec Volume (L)** — the electronic volume totalizer reading right now
   - **Manual Meter (L)** — the mechanical odometer reading right now

   These values become the opening readings for the **first shift ever**. After that, each shift close advances them automatically.

### 4.7 Employees

**Employees → Employees**

For each forecourt attendant:

1. Open the employee record.
2. Tick **Is Forecourt Attendant**.

For the employee to receive POS-sourced payment breakdowns (MPesa, card, AR), their employee record must be linked to an Odoo user account via the **Related User** field.

### 4.8 User Roles

**Settings → Users → (edit each user)**

| FMS Role | Odoo Group | Who gets it |
|---|---|---|
| Attendant | Forecourt Management / Attendant | Pump attendants (meter/dip entry only) |
| Shift Supervisor | Forecourt Management / Shift Supervisor | Supervisors (open/close shift, print reports) |
| Accountant / Manager | Forecourt Management / Accountant / Manager | Finance, station managers (read all, manage preferences) |

Supervisor implies Attendant rights. Accountant implies Supervisor rights.

---

## 5. Running Tests

```bash
# Via Odoo's test runner (required — tests use the Odoo ORM)
python /opt/odoo/odoo-bin \
    -d test_fms \
    --addons-path=/opt/odoo/odoo/addons,/opt/odoo/custom-addons \
    --test-enable --stop-after-init -i fms

# Via Makefile shortcut
make odoo-test
```

All 29 UAT tests must pass before go-live:

| Class | Tests | Covers |
|---|---|---|
| `TestUAT1NormalClose` | 6 | Basic shift open → close cycle |
| `TestUAT2ResidualAllocation` | 3 | Meter/POS mismatch handling |
| `TestUAT3Gate1Block` | 2 | FC cash variance blocks close |
| `TestUAT4Gate3Block` | 3 | Tank dip variance blocks close |
| `TestUAT5SequentialShifts` | 3 | Opening readings carry over correctly |
| `TestUAT6Gate1VolumeBlock` | 5 | Volume reconciliation gate (Gate 1) |
| `TestUAT7Gate2CashBlock` | 5 | Cash reconciliation gate (Gate 2) |

---

## 6. Updating After a Code Change

```bash
python /opt/odoo/odoo-bin \
    -d production \
    -u fms \
    --addons-path=/opt/odoo/odoo/addons,/opt/odoo/custom-addons \
    --stop-after-init

# Via Makefile
make odoo-update
```

Always use `-u` (update) on a live database — it migrates XML records in-place without touching existing shift data.

---

## 7. Installing the Accounting Module (`fms_accounting`)

`fms_accounting` is a separate optional module that adds credit customers, fuel deliveries, petty cash, and VAT splitting. It depends on `fms` — install `fms` first.

### Copy and register

```bash
cp -r /path/to/fms_accounting /opt/odoo/custom-addons/fms_accounting
```

The `--addons-path` entry you already added covers it automatically (same parent directory).

### Install

```bash
# CLI
python /opt/odoo/odoo-bin -d production -i fms_accounting \
    --addons-path=/opt/odoo/odoo/addons,/opt/odoo/custom-addons \
    --stop-after-init

# Or via Apps UI: search "FMS Accounting" → Install
```

### Post-install configuration

| Step | Where | What to do |
|---|---|---|
| Delivery sequence | auto | `DEL/YYYY/NNNN` created on install |
| Petty cash float | Forecourt → Accounting → Petty Cash Float | Create one record per company, select a cash journal |
| Credit customers | Forecourt → Accounting → Credit Customers | Create fleet accounts, set credit limits |
| Supplier for deliveries | Contacts | Mark fuel suppliers with `Is Supplier` |
| Fuel product taxes | Products → Taxes | Add VAT tax to fuel products; `fms_accounting` auto-splits net + tax on shift GL posting |

### Coexistence with Cybrosys accounting addon

`fms_accounting` only creates `account.move` records programmatically and does **not** override `account.move` form views. Cybrosys can be installed alongside it for financial reports and bank reconciliation without view conflicts. Install order: `fms` → `fms_accounting` → Cybrosys.

---

## 8. Uninstalling

Uninstalling FMS **permanently deletes** all shift, meter log, and dip log records. Do not uninstall on a production database with operational history.

To reset a development database:

```bash
make odoo-drop       # drops test_fms (prompts for confirmation)
make odoo-install    # fresh install with demo data
```

---

## Troubleshooting

**`Module 'fms' not found` on install**  
Check that `fms/` sits directly inside a directory on `--addons-path`, not nested a level deeper (`custom-addons/fms/__manifest__.py` ✓, not `custom-addons/project/fms/__manifest__.py` ✗).

**`ir.model.access` errors on startup**  
Run `-u fms` to reload security files. This usually means code was updated without restarting Odoo.

**Shift close fails — "No sale-type journal found"**  
Create the Forecourt Sales journal (step 4.2) and select it in Site Preferences (step 4.3).

**Shift close fails — "Cannot find a receivable/clearing account"**  
Set the Cash Clearing Account in Site Preferences (step 4.3).

**Opening meter readings are all zero on the first shift**  
Set the current totalizer values on each nozzle in Pumps configuration (step 4.6) before opening the first shift.

**`web.assets_backend` not found on `-u fms`**  
Confirm you are running Odoo 18. The `assets` manifest key format changed between Odoo 16 and 18.

**`base.paperformat_a4` error on reports**  
This is a known Odoo 18 CE issue. FMS uses `paperformat_euro` instead. Run `-u fms` to pick up the fix.
