# FMS Installation Guide

Installs the `fms` and `fms_accounting` Odoo 18 modules on a fresh server.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Ubuntu | 22.04 LTS | 24.04 also works |
| Python | 3.11 | Odoo 18 requirement |
| PostgreSQL | 15+ | |
| Odoo | 18.0 Community | installed at `/home/niini/odoo18` |
| Node.js | 18+ | for Odoo asset compilation |

---

## 1. Clone the Modules

```bash
# FMS core module
git clone https://github.com/your-org/fms.git /home/niini/fms

# FMS accounting extension (optional but recommended)
git clone https://github.com/your-org/fms_accounting.git /home/niini/fms_accounting
```

Both repos must be siblings — `fms_accounting` depends on `fms`.

---

## 2. Install OCA Dependencies

`fms_accounting` depends on several OCA modules. Clone them into `/home/niini/oca/`:

```bash
mkdir -p /home/niini/oca
cd /home/niini/oca

git clone https://github.com/OCA/account-financial-reporting.git --branch 18.0 --depth 1
git clone https://github.com/OCA/account-financial-tools.git      --branch 18.0 --depth 1
git clone https://github.com/OCA/account-reconcile.git            --branch 18.0 --depth 1
git clone https://github.com/OCA/credit-control.git               --branch 18.0 --depth 1
git clone https://github.com/OCA/web.git                          --branch 18.0 --depth 1
git clone https://github.com/OCA/server-ux.git                    --branch 18.0 --depth 1
git clone https://github.com/OCA/reporting-engine.git             --branch 18.0 --depth 1
git clone https://github.com/OCA/server-tools.git                 --branch 18.0 --depth 1
git clone https://github.com/OCA/mis-builder.git                  --branch 18.0 --depth 1
git clone https://github.com/OCA/hr-expense.git                   --branch 18.0 --depth 1
```

> If you only install `fms` (without `fms_accounting`), no OCA deps are needed.

---

## 3. Install Python Dependencies

```bash
source /home/niini/odoo-venv/bin/activate

# OCA helper required by date_range tests
pip install odoo-test-helper

# Playwright (optional, for UI testing only)
pip install playwright
python -m playwright install chromium
```

---

## 4. Create the Database

```bash
cd /home/niini/fms
make setup
```

This runs:
```
odoo-bin -d fms_e2e -i fms,fms_accounting \
  --addons-path=... --stop-after-init --without-demo=all
```

First install takes 5–10 minutes (downloads/compiles assets).

---

## 5. Seed Demo Data (Optional)

```bash
make seed
```

Seeds Kenya Chart of Accounts, fuel products (Diesel, Super, V-Power), two pumps with nozzles, and two tanks.

---

## 6. Start the Server

```bash
make run
```

Opens at **http://localhost:8070**. Default credentials: `admin` / `admin`.

---

## 7. Post-Install Configuration

Do this once after first login:

### 7.1 Chart of Accounts
Settings → Accounting → Fiscal Localization → Kenya (or your country).

### 7.2 Fuel Products
Go to **Forecourt → Configuration → Products**. For each fuel product set:
- `FMS Is Fuel` = ✓
- `Revenue Account` — your sales income account
- `COGS Account` — your cost of goods account
- `Sales Price` — current pump price per litre

### 7.3 Pumps and Nozzles
**Forecourt → Configuration → Pumps**. Create pumps, then nozzles under each pump. Assign a fuel product to each nozzle.

### 7.4 Tanks
**Inventory → Configuration → Locations**. For each tank, tick `FMS Fuel Tank` and set `Fuel Product`.

### 7.5 Site Preferences
**Forecourt → Configuration → Site Preferences**:
- `Require POS Reconciliation` — enable if POS is live
- `Stock Variance Meniscus` — default 0.5%
- `Auto Sync Attendants` — default on (recommended)

### 7.6 Users and Groups
**Settings → Users**. Assign FMS groups:
- `FMS / Attendant` — pump attendants (read-only shift, can enter meter readings)
- `FMS / Supervisor` — shift supervisors (open/close shifts, approve variances)
- `FMS / Accountant` — full accounting access (journal entries, reports)

---

## 8. Verify Installation

```bash
# Run the full test suite against a fresh test DB
make test
```

Expected: **280 tests, 0 failed, 0 errors**.

---

## Upgrading After Code Changes

```bash
git pull
make upgrade   # runs -u fms,fms_accounting --stop-after-init
make run
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: odoo_test_helper` | `pip install odoo-test-helper` in odoo venv |
| `column am.fms_vehicle_id does not exist` | Fresh install race — run `make upgrade` once after install |
| Port 8070 already in use | `fuser -k 8070/tcp` then `make run` |
| OCA module not found | Confirm `--addons-path` includes all OCA repo paths |
| `account_price_include` write error | Do not change this company setting after invoices exist; set per-tax instead |
