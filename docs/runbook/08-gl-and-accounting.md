# 08 — GL and Accounting

Audience: Accountant
Role required: `fms.group_fms_accountant`

---

## What FMS Posts to the GL

Every closed shift with non-zero sales produces two sets of journal entries.

### Entry 1 — Sales Journal Entry

Posted once per shift on Close Shift.

```
Journal:   FMS Shifts (miscellaneous)
Date:      Shift date
Reference: "FMS Shift: FMS/2026/0001"

DR  191600  FMS Cash Clearing          100,000.00
CR  400000  Sales of Diesel Income      72,000.00
CR  400100  Sales of Unleaded Income    18,000.00
CR  400200  Sales of V-Power Income     10,000.00
```

**Debit side:** A single line to the clearing account for total elec cash meter sales across all products.

**Credit side:** One line per fuel product with a configured `fms_revenue_account_id`. Products without a revenue account are skipped (warning logged).

The clearing account is configured in Forecourt → Configuration → Site Preferences.

---

### Entry 2 — Residual Allocation Journal Entries

Posted one entry per reallocation line after the sales entry.

```
Journal:   FMS Shifts
Date:      Shift date
Reference: "FMS Residual: Diesel → Carwash (FMS/2026/0001)"

DR  591200  Carwash COGS          35,000.00
CR  591000  Diesel COGS           35,000.00
```

**Purpose:** Corrects COGS when sales were lumped across products.
Does not affect revenue lines — only reclassifies COGS.

---

## Account Wiring (per product)

For each fuel product, two accounts must be set:

**Forecourt → Products → [Fuel Product] → FMS tab** (or Inventory → Products)

| Field | Account type | Example |
|---|---|---|
| Fuel Revenue Account | `income` or `income_other` | 400000 Sales of Diesel Income |
| Fuel COGS Account | `expense_direct_cost` | 591000 Cost of Sales — Diesel |

Products with no revenue account wired: **skipped silently** (sales not posted to GL for that product, only logged as warning). Fix before the next shift closes.

---

## Viewing GL Entries

**Option 1:** From the closed shift form
- Field **Sales GL Entry** — click to open the `account.move` record.
- Button **Residual Entries** — lists all allocation `account.move` records.

**Option 2:** Accounting → Journal Entries
- Filter: Journal = FMS Shifts, Date = shift date.

**Option 3:** Accounting → Reporting → General Ledger
- Filter by account (e.g. 400000) to see all shifts posting to that account.

---

## Clearing Account Flow

The clearing account (e.g. 191600 FMS Cash Clearing) accumulates debits from shift closes. It must be cleared daily or per period by a separate entry:

```
DR  102003  Lipa Na Mpesa          60,000.00    (actual MPesa received)
DR  101000  Cash in the Safe       30,000.00    (physical cash counted)
DR  102001  Equity Visa            10,000.00    (card receipts)
CR  191600  FMS Cash Clearing     100,000.00
```

This clearing entry is **not posted automatically** — the accountant posts it manually in Accounting → Journal Entries after verifying the day's bank collections, MPesa statements, and cash counts match.

The balance on 191600 should be 0 at month-end if all shifts are cleared.

---

## Chart of Accounts — Key FMS Accounts

Based on Anika Global Limited chart of accounts:

| Code | Account | FMS use |
|---|---|---|
| 101000 | Cash in the Safe | Debit when clearing cash from 191600 |
| 102003 | Lipa Na Mpesa | Debit when clearing MPesa from 191600 |
| 102004 | Shell Card Account | Debit when clearing Shell card receipts |
| 110000 | Accounts Receivable (A/R) | Credit for AR/credit sales on attendant cash |
| 191600 | FMS Cash Clearing | DR on every shift close |
| 400000 | Sales of Diesel Income | CR on Diesel shift sales |
| 400100 | Sales of Unleaded Income | CR on Unleaded shift sales |
| 400200 | Sales of V-Power Income | CR on V-Power shift sales |
| 400300 | Sales of LPG Income | CR on LPG shift sales |
| 400400 | Sales of Lubricant Income | CR on lubricant sales |
| 591000 | Diesel Cost of Sales | DR/CR in residual allocation |
| 591100 | Unleaded Cost of Sales | DR/CR in residual allocation |
| 591200 | Carwash / Other COGS | DR in residual allocation |
| 624000 | Bad Debts | DR when writing off uncollectable AR |
| 700002 | Reconciliation Discrepancies | Post unresolvable shift variances here |

---

## Period-End Checklist

### Daily
- [ ] All shifts for the day are in Closed state.
- [ ] Clearing account (191600) debits for the day match total shift cash meter sales.
- [ ] Post clearing journal entry: DR cash/MPesa/card accounts | CR 191600.
- [ ] Verify bank SMS / MPesa statement matches MPesa collections.

### Weekly
- [ ] Review Shortage/Overage report — investigate any shifts with dip variance > 0.5%.
- [ ] Check Attendant Performance report — flag any attendants with recurring shortages.
- [ ] Reconcile Accounts Receivable (110000) — confirm credit customers have invoices.

### Monthly
- [ ] Run Trial Balance report — confirm debits = credits.
- [ ] Run Profit & Loss — review gross margin per product.
- [ ] Run Balance Sheet — confirm clearing account (191600) balance = 0.
- [ ] Reconcile Shell Card Account (102004) against Shell statement.
- [ ] Review and write off bad debts if any credit customers are overdue.
- [ ] Post any fuel inventory adjustments from EPRA dip variance investigations.

---

## Manual Journal Entries

Post in **Accounting → Journal Entries → New**.

Always use the FMS Shifts journal for FMS-related corrections. Set the reference to the relevant shift number for traceability.

**Correcting a missed cash drop (attendant handed in cash after shift closed):**
```
DR  101000  Cash in the Safe       5,000.00
CR  191600  FMS Cash Clearing      5,000.00
Ref: "Late cash drop — FMS/2026/0001 — [Attendant name]"
```

**Writing off unresolvable shift variance:**
```
DR  700002  Reconciliation Discrepancies    500.00
CR  191600  FMS Cash Clearing               500.00
Ref: "Variance write-off — FMS/2026/0001"
```

**Posting a fuel delivery:**
Not handled automatically by FMS — post via Inventory → Receipts (stock move) plus Accounting → Vendor Bills (vendor invoice). Quantity received posts to stock; cost posts to COGS on bill validation.

---

## AR / Credit Customers

Credit sales appear on attendant cash rows as **AR / Credit (KES)** — sourced from linked POS sessions.

The corresponding POS entry debits a receivable account. To maintain accuracy:

1. POS must be configured with a credit payment method mapped to account 110000 (Accounts Receivable).
2. When the customer pays: **Accounting → Customers → Payments → New** — this settles the open receivable.
3. Monthly: run **Accounting → Customers → Aged Receivable** — chase overdue customers.

---

## Tax / VAT

FMS shift sales are posted as gross amounts (VAT-inclusive if the product has taxes configured on the POS product). Odoo handles VAT split at POS session level. FMS does not perform a separate VAT calculation.

For VAT summary reporting: **Accounting → Reporting → Tax Report** — select the period and generate the Kenya VAT return.
