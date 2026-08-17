# 05 — Reports

Audience: Manager / Accountant
Role required: `fms.group_fms_accountant` (for GL-linked reports), Supervisor for shift-level reports.

---

## Shift Reports (per shift)

Access from the closed shift form header.

| Button | Content |
|---|---|
| Print Shift Report | Meter readings, attendant cash, residual allocations, dip variances, GL entry reference |
| Print Meter Movement | Opening/closing totalizers per nozzle, RTT, net sold, attendant summary |
| Attendant Shift Statement | Per-attendant breakdown — meter sales, collections, balance |

---

## Operational Reports

**Forecourt → Reporting**

| Report | Filter options | Use |
|---|---|---|
| Wetstock Movement | Date range, product, tank | Daily stock reconciliation per tank |
| Attendant Sales Summary | Date range, attendant | Who sold what, per period |
| Shortage / Overage | Date range | Shifts where variance exceeded meniscus |
| Attendant Performance | Date range, attendant | Shift count, accuracy, shortage rate |
| Risk & Anomaly | Date range | Flags round readings, large variances, unusual patterns |

---

## Financial Reports (fms_accounting module)

**Accounting → FMS Reports** (or Forecourt → Reporting → Financial)

### Profit & Loss

Menu: **Accounting → FMS Reports → Profit & Loss**

Filters: Date range (month, quarter, YTD, custom).

Sections:
- Revenue (fuel, lubricants, LPG, carwash, other)
- Cost of Sales (COGS per product line)
- Gross Profit
- Operating Expenses
- Net Profit / Loss

Output: PDF in Apple SEC filing style (black and white, Arial 10pt).

### Balance Sheet

Menu: **Accounting → FMS Reports → Balance Sheet**

Layout: Single-column stacked.
- Assets: Current → Non-current → Total Assets
- Liabilities: Current → Non-current → Total Liabilities
- Shareholders' Equity
- Total Liabilities and Equity

### Trial Balance

Menu: **Accounting → FMS Reports → Trial Balance**

Shows all accounts with debit and credit totals. Footer confirms debit = credit (balance check in red if unbalanced).

---

## Print a Financial Report

1. Go to the report menu.
2. Set date range using the wizard.
3. Click **Print PDF** or **Export Excel**.

PDF renders via wkhtmltopdf — ensure it is installed on the server (see [01-installation.md](01-installation.md)).

---

## Standard Odoo Reports (also useful)

- **Accounting → Reporting → General Ledger** — all posted journal entries.
- **Accounting → Reporting → Account Moves** — filter by journal to see all FMS shift entries.
- **Inventory → Reporting → Inventory Valuation** — current stock value per product.
