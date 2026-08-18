# FMS Runbook

Forecourt Management System — Odoo 18 Community Edition
Anika Global Limited | Shell Maanzoni Service Station

---

## Contents

| File | Audience | When to read |
|---|---|---|
| [01-installation.md](01-installation.md) | Sysadmin | First-time setup |
| [02-configuration.md](02-configuration.md) | Manager / Accountant | Before first shift |
| [03-daily-shift.md](03-daily-shift.md) | Supervisor | Every shift close |
| [04-gate-failures.md](04-gate-failures.md) | Supervisor | When shift close is blocked |
| [05-reports.md](05-reports.md) | Manager / Accountant | Period-end reporting |
| [06-administration.md](06-administration.md) | Accountant / Sysadmin | Ongoing admin tasks |
| [07-troubleshooting.md](07-troubleshooting.md) | Supervisor / Sysadmin | Errors and edge cases |
| [08-gl-and-accounting.md](08-gl-and-accounting.md) | Accountant | GL entries, clearing, period-end |
| [09-field-reference.md](09-field-reference.md) | All | Full field definitions for every form |

---

## Navigation

FMS follows Odoo Inventory-style information architecture:

```
Forecourt
  ├── Overview
  │   ├── Dashboard          (station health at a glance)
  │   └── Active Shift       (open/closing shifts — primary operational entry)
  ├── Operations
  │   ├── Shifts             (full shift history)
  │   ├── Fuel Deliveries    (stock.picking filtered to FMS deliveries)
  │   ├── Meter Readings     (immutable meter log audit)
  │   ├── Dip Readings       (immutable dip log audit)
  │   └── Short Sales Adjustments
  ├── Sales & Cash
  │   ├── Cash Reconciliation
  │   ├── Credit Customers
  │   ├── PDC Register
  │   ├── Petty Cash Transactions
  │   └── Sales Receipts
  ├── Reporting
  │   ├── Shift Reconciliation / Wetstock / Meter Reading Audit
  │   ├── Shift Summary / EPRA Throughput
  │   ├── Attendant Sales / Shortage & Overage / Performance
  │   ├── P&L / Balance Sheet / Trial Balance / Debtors Aging  (accountant)
  │   └── + 7 more operational reports
  └── Configuration
      ├── Station Setup      (pumps + nozzles)
      ├── Nozzles
      ├── Shift Definitions & Prices
      ├── Site Preferences
      └── GL Account Setup Check
```

---

## Roles

| Role | Odoo group | Key permissions |
|---|---|---|
| Attendant | `fms.group_fms_attendant` | Overview, Shifts |
| Supervisor | `fms.group_fms_supervisor` | All operational menus, Reporting |
| Accountant | `fms.group_fms_accountant` | Financial reports, Configuration |
| Sysadmin | Odoo Administrator | Shell access, state resets, upgrades |

Groups are hierarchical: Accountant ⊃ Supervisor ⊃ Attendant permissions.

---

## Shift in 60 Seconds

```
Forecourt → Overview → Active Shift → New
  ↓ Open Shift
  ↓ Enter closing meter readings (Meter Readings tab)
  ↓ Enter tank dips (Tank Dips tab)
  ↓ Start Closing
  ↓ Link POS sessions, enter Cash Dropped until Balance = 0
  ↓ Close Shift  ← 5 gates must pass
  ↓ Print Shift Report
```

Target: 15 minutes from last pump transaction.

---

## Development Commands

```bash
make odoo-e2e-update   # update fms + fms_accounting in fms_e2e after code changes
make odoo-e2e          # start app on port 8070
make odoo-update       # update fms in test_fms
```

---

## Key Rules (non-negotiable)

1. Every KES must be accounted for — FC Cash Balance must be exactly 0.
2. Every attendant must clear — each Balance must be exactly 0.
3. Dip variance within meniscus — default ±0.5% per tank.
4. No "close anyway" button — gates cannot be bypassed.
5. Meter/dip logs are immutable — written on close, cannot be edited or deleted.
