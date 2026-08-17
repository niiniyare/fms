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

---

## Roles

| Role | Group name | Key permissions |
|---|---|---|
| Attendant | `fms.group_fms_attendant` | View shifts, enter readings |
| Supervisor | `fms.group_fms_supervisor` | Open/close shifts, print reports |
| Accountant | `fms.group_fms_accountant` | Site preferences, GL, price periods |

---

## Target shift close time: 15 minutes from last pump transaction.
