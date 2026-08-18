# 05 — Reports

Audience: Manager / Accountant
Role required: `fms.group_fms_accountant` for financial reports; Supervisor for operational reports.

---

## Shift Reports (per shift, from the shift form)

| Button | Content |
|---|---|
| Print Shift Report | Meter readings, attendant cash, residual allocations, dip variances, GL entry reference |
| Print Meter Movement | Opening/closing totalizers per nozzle, RTT, net sold, attendant summary |
| Attendant Shift Statement | Per-attendant breakdown — meter sales, collections, balance |

---

## Operational Reports

**Forecourt → Reporting**

| Report | What it answers |
|---|---|
| Shift Reconciliation | What happened during each shift? Full meter/cash/dip picture. |
| Wetstock | How much stock received, sold, lost/gained per tank? |
| Meter Reading Audit | What did each nozzle meter record? Variance between elec and manual. |
| Shift Summary | Complete final shift picture — sales by product, attendant totals. |
| EPRA Throughput | What throughput must be reported to EPRA? |
| Attendant Sales | Who sold what per period? MPesa / card / cash split. |
| Shortage & Overage | Which shifts had variance beyond meniscus? |
| Attendant Performance | Shift count, accuracy rate, shortage frequency per attendant. |
| Nozzle Performance | Volume and cash per nozzle over time. |
| Risk & Anomaly | Flags: round readings, large variances, unusual patterns. |
| Stock Position | Current stock level, days of cover, reorder status per tank. |
| Incident Register | Drive-offs, incidents, litres lost, value recovered. |
| Attribution Residuals | Lumped sales reclassified between products. |
| Nozzle Handover | Nozzle assignment summary per shift — handover audit. |
| Sales by Category | Revenue breakdown by product category. |

---

## Financial Reports (fms_accounting module — Accountant only)

**Forecourt → Reporting** (visible to `fms.group_fms_accountant`)

| Report | What it answers |
|---|---|
| Profit & Loss | Revenue vs COGS vs expenses — net profit/loss. |
| Balance Sheet | Assets, liabilities, shareholders' equity at a point in time. |
| Trial Balance | All accounts with debit/credit totals — balanced check. |
| Debtors Aging | Outstanding credit customer balances by aging bucket. |
| GL Reconciliation Journal | Shift GL entries cross-referenced to bank/MPesa statements. |

All financial reports output PDF in Apple SEC filing style (black and white, Arial 10pt).

---

## How to Print a Financial Report

1. **Forecourt → Reporting → [Report name]**
2. Set date range in the search bar or wizard.
3. Click **Print PDF** or **Export XLSX**.

PDF requires wkhtmltopdf 0.12.6 on the server.

---

## Standard Odoo Reports (also useful)

- **Accounting → Reporting → General Ledger** — all posted journal entries.
- **Accounting → Journal Entries** — filter Journal = FMS Shifts for shift-specific entries.
- **Inventory → Reporting → Inventory Valuation** — current stock value per product.
- **Accounting → Customers → Aged Receivable** — credit customer aging.
