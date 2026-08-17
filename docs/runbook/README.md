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

## Roles

| Role | Odoo group | Key permissions |
|---|---|---|
| Attendant | `fms.group_fms_attendant` | View shifts, enter readings |
| Supervisor | `fms.group_fms_supervisor` | Open/close shifts, print reports |
| Accountant | `fms.group_fms_accountant` | Site preferences, GL, price periods |
| Sysadmin | Odoo Administrator | Shell access, state resets, upgrades |

Groups are hierarchical: Accountant ⊃ Supervisor ⊃ Attendant permissions.

---

## Shift in 60 Seconds

```
New → Open Shift
  ↓ Enter closing meter readings (Meter Readings tab)
  ↓ Enter tank dips (Tank Dips tab)
  ↓ Start Closing
  ↓ Link POS sessions (Attendant Cash tab)
  ↓ Enter Cash Dropped per attendant until Balance = 0
  ↓ Close Shift  ← all 5 gates must pass
  ↓ Print Shift Report
```

Target: 15 minutes from last pump transaction.

---

## Key Rules (non-negotiable)

1. **Every KES must be accounted for.** FC Cash Balance must be exactly 0.
2. **Every attendant must clear.** Each individual Balance must be exactly 0.
3. **Dip variance within meniscus.** Default ±0.5% per tank.
4. **No "close anyway" button.** Gates cannot be bypassed.
5. **Meter/dip logs are immutable.** Written on close, cannot be edited or deleted.
