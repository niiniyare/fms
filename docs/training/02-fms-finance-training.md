# FMS Finance & Accounting Training Guide
**Audience:** New accountants and finance officers managing a fuel station's books  
**Trainer:** Use this document section-by-section. Each section has trainer notes and trainee exercises.  
**Duration:** 2 days (Day 1: GL fundamentals + shift accounting, Day 2: AR/CR customers, reports, period-end)  
**Prerequisites:** Trainee must have completed `01-fms-operations-training.md` OR must understand how a shift closes.  
**System:** FMS Accounting module on Odoo 18 (fms_accounting)  
**Role required:** `fms.group_fms_accountant` + `account.group_account_manager`

---

## How to Use This Guide

Work through sections in order. Each section has:
- **Concept** — explain this to the trainee in plain language
- **System location** — where in Odoo to find this
- **Demonstration** — trainer shows on screen
- **Exercise** — trainee does it independently
- **Common mistakes** — what to watch for

Do not skip sections — they build on each other.

---

## Day 1: GL, Shift Accounting, and Cash Reconciliation

---

## Section 1 — The Accounting Framework at a Fuel Station

### Concept

A fuel station's accounts have a distinct flow that differs from a normal retailer. Understanding this flow is essential before touching any numbers.

**Revenue is recorded at pump, not at invoice.** When the pump dispenses 50L at KES 222.80/L = KES 11,140, that revenue is captured by the pump meter totalizer. FMS converts the meter reading into a GL journal entry automatically when the shift closes.

**Cash is not banked immediately.** Cash from fuel sales goes into the station safe first. From the safe it is eventually deposited into the bank. Between pump meter and bank deposit there is a "clearing account" that holds the balance — like a staging area.

**The clearing account flow:**
```
Pump meter records sales
    ↓
Shift closes: GL posts
    DR  191600 FMS Cash Clearing     [total sales]
    CR  400000 Diesel Revenue        [diesel portion]
    CR  400100 Unleaded Revenue      [unleaded portion]
    ↓
Accountant posts daily clearing entry:
    DR  101000 Cash in Safe          [cash counted]
    DR  102003 MPesa Account         [verified from M-Pesa statement]
    DR  102001 Card Receivable       [from card terminal report]
    CR  191600 FMS Cash Clearing     [must equal shift total]
    ↓
Bank deposit:
    DR  100000 Bank Account          [deposited cash]
    CR  101000 Cash in Safe          [removed from safe]
```

If the clearing account (191600) has a balance, it means cash is sitting somewhere — in the safe, not yet verified from MPesa, or waiting for card settlement. At month-end, the clearing account must be zero.

**Key accounts you will use daily:**

| Account | Code | Normal Balance | What it holds |
|---|---|---|---|
| Bank Account | 100000 | Debit | Cash in bank |
| Cash in Safe | 101000 | Debit | Physical cash at station |
| Card Receivable | 102001 | Debit | Card payments awaiting settlement |
| MPesa Account | 102003 | Debit | MPesa balance |
| Accounts Receivable | 110000 | Debit | Credit customer outstanding balances |
| FMS Cash Clearing | 191600 | Should be 0 at month-end | Staging between meter and bank |
| Diesel Revenue | 400000 | Credit | Income from Diesel sales |
| Unleaded Revenue | 400100 | Credit | Income from Unleaded sales |
| V-Power Revenue | 400200 | Credit | Income from V-Power sales |
| Diesel COGS | 591000 | Debit | Cost of Diesel sold / residual reclassification |
| Reconciliation Discrepancies | 700002 | Debit | Unresolvable shift variances |

### Exercise

> **Trainee task:** Open Accounting → Chart of Accounts. Find the five accounts listed above. For each account, note: (1) the account type, (2) whether it currently has a balance, (3) what that balance represents. Discuss with trainer.

---

## Section 2 — What Happens When a Shift Closes

### Concept

When a supervisor clicks Close Shift, FMS posts journal entries automatically without human input. The accountant does not need to do anything for the shift's GL to be correct — but they need to understand what was posted so they can verify and clear it.

**What gets posted automatically:**

**Entry 1 — Sales Journal Entry** (one per shift)

```
Date:      2026-01-15
Journal:   FMS Shifts (FCST)
Reference: FMS Shift: FMS/2026/0001

DR  191600  FMS Cash Clearing          237,450.00
CR  400000  Diesel Revenue             153,850.00
CR  400100  Unleaded Revenue            83,600.00
```

The debit is the total of all Elec Cash Sold across all nozzles in the shift.
The credits are broken down per fuel product.

The amounts come from the meter readings — specifically `elec_cash_sold` (closing Elec Cash minus opening Elec Cash). This is the cash totalizer reading, not a manual entry.

**Entry 2 — Residual Allocation Entry** (one per allocation, if any)

```
Date:      2026-01-15
Journal:   FMS Shifts (FCST)
Reference: FMS Residual: Diesel → Carwash (FMS/2026/0001)

DR  591200  Carwash COGS               1,500.00
CR  591000  Diesel COGS                1,500.00
```

This moves COGS from the product that was over-reported (Diesel) to the product that was actually sold (Carwash). It does not affect revenue — only COGS.

### Where to See These Entries

**From the shift:**
- Open the closed shift (Forecourt → Operations → Shifts → find the shift)
- In the header, the field **Sales GL Entry** shows the journal entry reference — click it to open
- The timestamp shows when it was posted

**From accounting:**
- Accounting → Journal Entries → filter Journal = FMS Shifts

**From the GL:**
- Accounting → Reporting → General Ledger → filter account 191600 → see one debit per shift

### Demonstration

**Trainer:** Open a closed shift. Click the Sales GL Entry link. Walk through the move lines — point out the debit to clearing, the credits to revenue per product. Close and show the same entry from Accounting → Journal Entries.

### Exercise

> **Trainee task:** Find the closed demo shift (FMS/2026/0001 or your first demo shift). Open it. Click the Sales GL Entry. Answer:
> 1. What is the total debit amount?
> 2. How many credit lines are there? What products do they represent?
> 3. What journal was used?
> 4. Is there a residual allocation entry? If yes, between which products and for how much?

---

## Section 3 — The Daily Clearing Entry

### Concept

Every day after all shifts close, the accountant must post a clearing journal entry to move the day's sales from the clearing account (191600) into the actual cash/payment accounts.

This is a **manual entry** — FMS does not post it automatically. The accountant must verify three sources before posting:

**1. MPesa statement**
Log into the station's M-Pesa till account. Download the day's transactions. Total the incoming payments. This is your MPesa debit amount.

**2. Card terminal report**
Print the end-of-day report from each card terminal. Total all card settlements. This is your card debit amount.

**3. Physical cash count**
The supervisor counts the cash in the safe and provides the total. Cross-check against the sum of cash drops across all of today's shifts minus any cash already banked mid-day.

**The entry:**
```
Date:      2026-01-15
Journal:   Cash Journal (or Bank Clearing Journal)
Reference: "Daily clearing — 2026-01-15"

DR  101000  Cash in Safe               150,000.00   (from supervisor cash count)
DR  102003  MPesa Account               70,000.00   (from M-Pesa statement)
DR  102001  Card Receivable             17,450.00   (from card terminal)
CR  191600  FMS Cash Clearing          237,450.00   (matches sum of today's shift sales)
```

The credit must exactly equal the sum of all shift Sales GL entry debits for the day. If they don't match, there is a discrepancy that must be investigated.

### Common Discrepancies and Fixes

| Situation | What you see | Fix |
|---|---|---|
| One shift not yet closed | CR total < today's shifts | Wait for supervisor to close, then post clearing |
| MPesa statement total doesn't match attendant MPesa | Small difference | Check for transactions at midnight crossing the day boundary |
| Card terminal report date is off by 1 day | CR total off by one day's cards | Some card terminals batch by bank settlement date, not transaction date — align to transaction date |
| Safe cash count doesn't match sum of cash drops | Difference in DR cash | Investigate: was a drop recorded but cash not physically in safe? Or vice versa? |

### System Location

**Accounting → Journal Entries → New**

Set:
- Journal: Cash or Bank Clearing
- Date: the shift date (not today if you are posting on the next day)
- Reference: "Daily clearing — [date]"
- Lines: as shown above

### Exercise

> **Trainee task:** Post a daily clearing entry for the demo shift. The demo shift had total meter sales of KES 237,450. Assume: Cash = KES 150,000, MPesa = KES 70,000, Card = KES 17,450. Post the entry. Then open the GL for account 191600 — is the balance from that shift now zero?

---

## Section 4 — Credit Customers and AR Management

### Concept

Some customers — typically fleet operators, government departments, or sacco operators — do not pay at the pump. They have a credit account with the station. The attendant records their transaction as "AR" in the POS. At the end of the month (or as agreed), the station invoices the customer and they pay.

**The flow:**

```
Attendant serves fleet customer
    ↓
POS records sale with "AR" payment method
    ↓
Shift closes → GL posts:
    DR  110000 Accounts Receivable
    CR  400000 Revenue
    (The AR appears in shift attendant cash as "AR / Credit")
    ↓
At billing time (end of month):
    Accounting → Customers → Invoices → Create
    The invoice total must match accumulated AR from POS
    ↓
Customer pays:
    Accounting → Customers → Payments → New
    DR  Bank or MPesa
    CR  110000 Accounts Receivable
    Balance on customer's AR goes to zero
```

**Credit limit enforcement:**

FMS Accounting enforces credit limits per customer. When an invoice is posted that would take the customer above their limit, the system raises an error:

```
Credit limit exceeded for NSS Security Ltd.
Limit: KES 500,000
Exposure after this invoice: KES 557,000
```

To override: the accountant ticks "Credit Limit Override" on the invoice and enters a reason. This is logged for audit. **Do not override without manager approval.**

### Viewing Credit Customer Balances

**Accounting → Customers → Customers → [Select a fleet customer]**

On the customer form you will see:
- `Credit Limit (KES)` — the agreed maximum
- `Outstanding Balance (KES)` — what they currently owe (computed from open invoices)
- `Exposure %` — outstanding / limit × 100

If a customer is approaching their limit, contact them before the next delivery.

### Creating a Credit Customer Invoice

**Accounting → Customers → Invoices → New**

| Field | What to set |
|---|---|
| Customer | The fleet account name |
| Invoice Date | The billing period end date |
| Payment Terms | As agreed (e.g. Net 30) |
| Invoice Lines | One line per product: Product = fuel, Qty = litres, Price = pump price |

Post the invoice. The customer's balance increases.

### Recording a Customer Payment

**Accounting → Customers → Payments → New** (or from the invoice → Register Payment)

| Field | What to set |
|---|---|
| Customer | Same fleet account |
| Amount | What they paid |
| Journal | Bank or MPesa depending on how they paid |
| Date | Date payment was received |

Post the payment. It automatically reconciles against the open invoice(s).

### Aged Receivable Report

**Accounting → Reporting → Aged Receivable** (or via MIS Builder)

Shows all customers with outstanding balances, broken into aging buckets:
- Current (0–30 days)
- 31–60 days
- 61–90 days
- 90+ days (critical — chase immediately)

Run this weekly. Any amount in 90+ days needs immediate action: call the customer, consider placing them on hold.

**To place a customer on hold:**
- Open the customer record (Accounting → Customers → Customers)
- Tick the field **On Credit Hold**
- Any new invoice for this customer will be blocked until the hold is lifted

### Exercise

> **Trainee task:** 
> 1. Open the credit customer "NSS Security Ltd." Note their credit limit and current outstanding balance.
> 2. Open their posted invoice (INV/2026/00003). Review the invoice lines.
> 3. Register a partial payment of KES 200,000 against this invoice (use Bank journal, date 2026-01-20).
> 4. After posting the payment, go back to the customer record. What is their new outstanding balance?
> 5. Run the Aged Receivable report. Find NSS Security Ltd. in the report.

---

## Section 5 — Fuel Deliveries

### Concept

When a fuel tanker delivers to the station, two things must happen:

**1. Stock receipt (Inventory)** — records that the physical fuel has arrived in the tank.
**2. Vendor bill (Accounting)** — records that the station owes money to the fuel supplier.

FMS Accounting has a **Fuel Delivery** model that handles both in one step.

### The Fuel Delivery Record

**Forecourt → Accounting → Fuel Deliveries → New** (or from the Forecourt menu)

| Field | What to enter |
|---|---|
| Delivery Date | Date the tanker arrived |
| Tanker / Delivery Note Ref | The delivery note number from the tanker driver |
| Supplier | Select the fuel supplier |
| Lines → Product | Fuel product delivered |
| Lines → Tank | Which underground tank received it |
| Lines → Invoiced Qty (L) | What the delivery note says was delivered |
| Lines → Unit Price | Price per litre from the supplier invoice |
| Dip Before | Tank dip reading BEFORE offloading started (in litres) |
| Sales During | Litres sold from this tank while the tanker was offloading |
| Dip After | Tank dip reading AFTER offloading complete (in litres) |

### Dip Verification (Critical for EPRA)

After entering the dip fields, the system computes:

```
Expected Qty = Dip Before + Invoiced Qty − Sales During

Variance = Dip After − Expected Qty
```

**If Variance = 0:** Perfect — received exactly what was invoiced.  
**If Variance > 0:** Received more than invoiced (rare — document and query supplier).  
**If Variance < 0:** Short delivery — the tanker delivered less than the delivery note stated. This is the most common scenario (temperature contraction, measurement error, driver siphoning). Document and raise a credit note with the supplier for the shortage.

EPRA regulations require all delivery variances to be documented. The dip log written on delivery confirmation is the official record.

### Confirming a Delivery

Click **Confirm Delivery**. The system:
1. Creates a `stock.picking` (inventory receipt) — the physical stock enters the tank location.
2. Creates a `vendor bill` (`account.move` type `in_invoice`) — payable to the supplier.
3. Writes a `fms.dip_log` record with `dip_type = offloading` — the official delivery dip record.
4. Links all three to the delivery header.

After confirming, go to the vendor bill and post it (or leave it in draft if the supplier invoice hasn't arrived yet — post when you receive the paper invoice).

### Paying the Supplier Bill

When the supplier invoice arrives (usually by email or post):
1. Go to Accounting → Vendors → Bills.
2. Find the draft bill created from the delivery.
3. Verify the amounts and date match the paper invoice.
4. Post the bill.
5. When payment is made: Accounting → Vendors → Payments → New. Select the supplier, amount, date, and bank journal.

### Exercise

> **Trainee task:**
> 1. Open the demo delivery record (VE-TK-20260110-001 from Vivo Energy).
> 2. Review the dip verification fields. Calculate the expected quantity manually and verify it matches the system's computation.
> 3. What is the variance? Is this a short delivery or an over-delivery?
> 4. Note the delivery is in Draft state. Discuss with trainer: what would happen if you clicked Confirm Delivery right now?

---

## Section 6 — MIS Builder Financial Reports

### Concept

FMS uses OCA MIS Builder for professional financial reports: Profit & Loss, Balance Sheet, and Cash Flow. These are not just snapshots — they pull live from the GL and can be run for any date range.

**Location:** Accounting → Reporting → MIS Reports

### Creating a Report Instance

MIS Builder uses "templates" (formula definitions) and "instances" (a template + a date range + a company). The templates for P&L, Balance Sheet, and Cash Flow are pre-loaded when `mis_template_financial_report` and `mis_builder_cash_flow` are installed.

To run a report:
1. Go to Accounting → Reporting → MIS Reports.
2. Click New.
3. Set **Name** (e.g. "P&L January 2026").
4. Set **Template** (e.g. "Profit & Loss").
5. Set **Date From** and **Date To**.
6. Click **Preview** (on-screen) or **Print** (PDF).

### Profit & Loss Report

Shows: Revenue − Cost of Sales − Operating Expenses = Net Profit

For a fuel station, the typical structure:

```
REVENUE
  Diesel Sales             400000
  Unleaded Sales           400100
  V-Power Sales            400200
  LPG Sales                400300
  Carwash / Non-fuel       400400
─────────────────────────────────
Gross Revenue

COST OF SALES
  Diesel COGS              591000
  Unleaded COGS            591100
─────────────────────────────────
Gross Profit

OPERATING EXPENSES
  Electricity              641000
  Water                    642000
  Salaries                 630000
  Repairs & Maintenance    660000
─────────────────────────────────
Net Profit Before Tax
```

**What to watch:**
- Gross margin on Diesel should be consistent (pump price − supplier cost). If it drops suddenly, either the pump price was not updated after a supplier price change, or there is an inventory loss.
- Check if operating expenses are in the correct period (date on the bill must be in the period you are reporting).

### Balance Sheet Report

Shows: Assets = Liabilities + Equity

**Key items to verify monthly:**

| Item | What to look for |
|---|---|
| Cash in Safe (101000) | Should match the physical safe count |
| MPesa Account (102003) | Should match the M-Pesa till balance on the paybill statement |
| FMS Cash Clearing (191600) | **Must be zero at month-end** — if not, an uncleared shift entry exists |
| Accounts Receivable (110000) | Should match the Aged Receivable report total |
| Accounts Payable | Should match sum of unpaid supplier bills |

### Cash Flow Report

Shows: Operating cash in/out, investing cash in/out, financing cash in/out.

For a fuel station:
- **Operating:** Cash from sales (actual bank receipts), payments to suppliers, salaries.
- **Investing:** Equipment purchases, tank upgrades.
- **Financing:** Loan repayments, equity injections.

**Critical insight:** The P&L may show profit but the cash flow may show negative. This happens when credit customers haven't paid. Watch the "Change in Receivables" line — a large increase means money is owed but not collected.

### Exercise

> **Trainee task:**
> 1. Go to Accounting → Reporting → MIS Reports → New.
> 2. Create a P&L instance for January 2026 (2026-01-01 to 2026-01-31).
> 3. Preview it. What is the total revenue? What is the total from Diesel sales?
> 4. Create a Balance Sheet instance for 2026-01-15.
> 5. Find the FMS Cash Clearing account balance. Is it zero? If not, what does the balance represent?

---

## Section 7 — OCA GL Reports (General Ledger, Trial Balance)

### Concept

OCA Financial Reports (from `account_financial_report` module) provide detailed transaction-level GL reports that MIS Builder doesn't cover:

- **General Ledger** — every transaction on every account in date range
- **Trial Balance** — all accounts with opening balance, period debits, period credits, closing balance
- **Open Items** — all accounts with unreconciled items (outstanding invoices, unmatched payments)
- **Aged Partner Balance** — AR and AP by partner, aged by due date
- **Journal Ledger** — all entries in a specific journal

**Location:** Accounting → Reporting → OCA Accounting Reports

### General Ledger — How to Read It

The GL is the master record of every transaction in the system. Use it for:
- Tracing a specific entry (where did this KES 45,000 come from?)
- Confirming a shift's posting (did shift FMS/2026/0001 post correctly?)
- Investigating an account balance (why does 191600 still have a balance?)

**To run:**
1. Accounting → Reporting → OCA Accounting Reports → General Ledger
2. Set date range, optionally filter by account.
3. Click **Export** to get PDF or Excel.

**Reading the output:**
```
Account: 191600 FMS Cash Clearing

Date          Reference                    Debit          Credit        Balance
2026-01-15    FMS Shift: FMS/2026/0001    237,450.00                   237,450.00 DR
2026-01-15    Daily clearing — 2026-01-15              237,450.00            0.00
```

The account starts at zero, goes up with the shift entry, comes back to zero with the clearing entry. If it stays at a positive balance, a clearing entry is missing.

### Trial Balance — Monthly Close Verification

Run the Trial Balance at month-end **before** closing the month.

It must balance: total debits = total credits.

If it doesn't balance, there is a corrupted entry (extremely rare in Odoo — usually caused by a system crash mid-transaction). Contact the system administrator immediately.

Look at the Trial Balance for:
- Any unexpected large balance on 191600 (uncleared shifts)
- Any balance on revenue accounts where the balance is a debit (should be credit-normal — a debit balance means the account has been over-reversed)
- Any unexpectedly large balance on 700002 (Reconciliation Discrepancies) — means many shifts had unresolved variances

### Exercise

> **Trainee task:**
> 1. Run the OCA General Ledger for account 191600 for January 2026.
> 2. Identify each debit entry — what shift or event created it?
> 3. Identify each credit entry — what clearing entry offset it?
> 4. Is the closing balance zero?
> 5. Run the Trial Balance for January 2026. Does it balance (total debits = total credits)?

---

## Day 2: AR Management, Vendor Bills, Period-End Close

---

## Section 8 — Monthly AR Reconciliation

### Concept

At the end of each month, the accountant must reconcile the Accounts Receivable account (110000):

**Step 1:** Run the Aged Receivable report. This shows every outstanding invoice per customer.

**Step 2:** Call or email each customer with an outstanding balance. Send them a statement of account.

**Step 3:** Match any payments received against open invoices. Odoo does this automatically when you post a payment — it will try to match against the oldest open invoice first.

**Step 4:** For invoices that are genuinely irrecoverable (customer gone, liquidated, disputed): write them off to Bad Debts (624000).

**Writing off a bad debt:**

In Accounting → Customers → Invoices, open the uncollectable invoice. Click **Credit Note** to create a credit note for the full amount. Post the credit note with account 624000 Bad Debts as the counter-account. This removes it from AR and records it as an expense.

**Step 5:** Confirm the balance on account 110000 in the GL matches the total from the Aged Receivable report. They should be identical. If they differ, there is a reconciliation issue — usually a payment that was posted but not matched to an invoice.

### Monthly AR Checklist

```
[ ] Run Aged Receivable report
[ ] For each customer with balance:
    [ ] 0-30 days: send statement, no action
    [ ] 31-60 days: call customer, confirm receipt of invoice
    [ ] 61-90 days: formal written demand, escalate to manager
    [ ] 90+ days: consider credit hold, discuss write-off
[ ] Match any unmatched payments to invoices
[ ] Confirm GL balance (110000) = Aged Receivable total
[ ] Report any write-offs to manager for approval
```

### Exercise

> **Trainee task:**
> 1. Run the Aged Receivable report for 2026-02-08 (30 days after the demo invoices).
> 2. Find NSS Security Ltd. — what is their balance? Which bucket?
> 3. Find Nairobi County Government — what is their balance?
> 4. Open NSS Security Ltd.'s customer record. What is their credit exposure percentage?
> 5. Discuss with trainer: what would you do if the county government has not paid after 60 days?

---

## Section 9 — Month-End Close Sequence

### Concept

At month-end, the accountant performs a structured sequence of steps to close the books. Doing them in order prevents having to undo and redo work.

**Full month-end sequence:**

### Step 1: Close all shifts for the month

Verify Forecourt → Operations → Shifts → Filter: Date = [last month], State ≠ Closed.

Any shift still Open or Closing must be closed by the supervisor before you proceed. Contact the supervisor — do not proceed with open shifts.

### Step 2: Post all daily clearing entries

Go to Accounting → Journal Entries → Filter: Journal = FMS Shifts, Date = [last month].

For each shift entry, verify there is a corresponding clearing entry (search for "Daily clearing — [date]" in the same date). Any day without a clearing entry — post it now (you may need to reconstruct from the MPesa statement and cash count records from that date).

### Step 3: Verify clearing account balance

**Accounting → Reporting → OCA GL** → account 191600 → date range = last month.

The closing balance must be zero. If not, identify which day's clearing is missing and post it.

### Step 4: Post all vendor bills

Accounting → Vendors → Bills → Filter: Date = last month, State = Draft.

Every draft bill for last month must be posted or moved to next month. A draft bill means the expense is not yet in the P&L. If the service was rendered this month, the bill must be posted this month (matching principle).

If the supplier invoice hasn't arrived, post the bill with estimated amounts and note "Accrual — [supplier] [service] [period]" in the reference. When the actual invoice arrives, edit and reconcile.

### Step 5: Post all customer invoices

Accounting → Customers → Invoices → Filter: Date = last month, State = Draft.

Same as vendor bills — any credit customer invoice for last month must be posted this month.

### Step 6: Reconcile AR and AP

- Run Aged Receivable → confirm total matches GL account 110000
- Run Aged Payable → confirm total matches GL account 210000 (or equivalent AP account)

### Step 7: Run Trial Balance

Accounting → Reporting → OCA GL → Trial Balance → date = last day of month.

- Total Debits must equal Total Credits.
- Review any accounts with unexpected balances.
- Confirm 191600 = 0.
- Confirm 700002 (Reconciliation Discrepancies) balance — investigate if large.

### Step 8: Run Profit & Loss

MIS Reports → P&L → last month date range.

- Review gross revenue by product. Does it match the sum of shift sales entries?
- Review gross margin (revenue − COGS). Is it in line with expected margin?
- Review operating expenses — are all costs captured?

### Step 9: Run Balance Sheet

MIS Reports → Balance Sheet → last day of month.

- Verify cash accounts (Safe, MPesa, Bank) match physical counts and statements.
- Verify AR balance matches aged receivable.
- Verify equity is positive and growing.

### Step 10: Lock the period

Accounting → Settings → Lock Date.

Set the lock date to the last day of the closed month. This prevents anyone from posting entries to the closed period accidentally.

Only the accountant (or manager with the `account.group_account_manager` role) can update the lock date.

### Month-End Checklist

```
PRE-CLOSE
[ ] All shifts for the month are Closed
[ ] All daily clearing entries posted
[ ] Account 191600 balance = 0

BILLS & INVOICES
[ ] All vendor bills for the month posted (or accrued)
[ ] All customer invoices for the month posted
[ ] Fuel delivery vendor bills posted and matched to delivery records

AR / AP RECONCILIATION
[ ] Aged Receivable matches GL account 110000
[ ] Aged Payable matches GL payables account
[ ] Bad debts written off (with manager approval)

REPORTING
[ ] Trial Balance run — balanced
[ ] P&L reviewed — no unusual items
[ ] Balance Sheet reviewed — cash accounts verified
[ ] Cash Flow reviewed — AR movement explained

LOCK
[ ] Period locked in Accounting → Settings → Lock Date
[ ] Manager sign-off obtained
```

### Exercise

> **Trainee task:** Using the demo data, work through the month-end checklist for January 2026:
> 1. Is the demo shift closed? (Check Forecourt → Operations → Shifts)
> 2. Is there a daily clearing entry for 2026-01-15? If not, post one.
> 3. What is the balance on account 191600?
> 4. Are all three customer invoices posted?
> 5. Are both vendor bills posted?
> 6. Run the Trial Balance for 2026-01-31.
> 7. Run the P&L for January 2026. What is the total revenue?

---

## Section 10 — Common Accounting Errors and How to Fix Them

### Error 1: Wrong Date on a Posted Entry

**Problem:** A shift closing entry was posted with yesterday's date instead of today's.

**Fix:**
In Odoo, you cannot change the date of a posted journal entry directly. You must:
1. Create a reversal (Accounting → Journal Entries → open the entry → Reset to Draft → Reverse). This creates an equal and opposite entry on today's date, cancelling the original.
2. Re-post the original entry with the correct date.

**Prevention:** Always verify the shift date in FMS before closing. The GL entry date matches the shift date — not the date you click Close Shift.

### Error 2: Revenue Posted to Wrong Account

**Problem:** V-Power sales are appearing in Diesel Revenue (400000) instead of V-Power Revenue (400200).

**Fix:** This means the V-Power product's `fms_revenue_account_id` was set to the wrong account.

1. Go to Inventory → Products → V-Power → FMS tab.
2. Change the revenue account to 400200.
3. This only affects future shifts. Past entries need a manual correction:
   - Post a manual journal entry: DR 400000 (reverse the wrong entry amount), CR 400200 (post to correct account).
   - Reference: "Revenue account correction — V-Power [date range]."

### Error 3: Clearing Account Not Zero at Month-End

**Problem:** Account 191600 has a KES 45,000 debit balance at 31 January.

**Investigation:**
1. Run the GL for 191600 for the month.
2. Find the entry (or entries) that have no matching credit.
3. Those are the shifts whose clearing entries are missing.

**Fix:**
Post the missing clearing entry now, backdated to the correct date (if the period is still open). If the period is locked, post in the current period with a note explaining the correction.

### Error 4: Attendant Balance Was Force-Zeroed

**Problem:** A shift was closed with a non-zero attendant balance by someone who posted a manual journal entry to force the balance to zero, but did not investigate.

**How to detect:**
- Look at the Reconciliation Discrepancies account (700002) — any balance here is a red flag.
- Click through to the journal entries crediting 700002 — they will reference a shift.
- Open that shift and review the Notes tab — there should be an explanation.

**Fix:**
If the variance was genuine (theft, error), the entry stands but the investigation must be documented and reported to management. If the variance was a data entry error and the actual cash is correct, the entry may need reversal and re-posting after correct data is identified.

### Error 5: Credit Customer Invoice Posted Twice

**Problem:** Customer was billed twice for the same period's fuel.

**Detection:** Run the Aged Receivable report — customer balance is double what you expect. Customer will complain.

**Fix:**
1. Open the duplicate invoice.
2. Click **Credit Note** → Post.
3. The credit note cancels the duplicate invoice and the customer's balance returns to correct.

**Prevention:** Before creating a credit invoice, search for existing invoices for that customer and period to avoid duplicates.

---

## Section 11 — Tax and VAT (Kenya Context)

### Concept

As of the current setup, FMS posts revenue amounts inclusive of VAT (if VAT is configured on the POS products). Odoo handles VAT calculation at POS session level — FMS does not separately compute VAT.

**For the VAT return:**
1. Accounting → Reporting → OCA Accounting Reports → VAT Report.
2. Set the VAT period (monthly in Kenya).
3. The report shows: taxable base, output tax (sales VAT), input tax (purchase VAT), net payable.
4. File the return with KRA via iTax using these figures.

**VAT on fuel — Kenya:**
Fuel is zero-rated for VAT in Kenya as of 2023 (excise duty applies separately via the pump price). Verify current KRA guidelines — this can change. If your products are set to "Tax = 0" or "Exempt," the VAT report will show zero output tax for fuel which is correct.

**Excise duty:**
Excise duty is embedded in the pump price (set by the Energy and Petroleum Regulatory Authority). FMS does not separately track excise duty — it is included in the revenue figure. Reporting excise duty separately (if required by KRA) must be done using the pump throughput volumes multiplied by the current excise rate.

---

## Section 12 — Access Control and Audit Trail

### Concept

FMS is designed so that the audit trail cannot be tampered with. Key principles:

**Immutable logs:** When a shift closes, `fms.meter_log` and `fms.dip_log` records are written. These records have Python-level protection on `write()` and `unlink()` — any attempt to modify or delete them raises a `ValidationError`. This means even a system administrator cannot change what the meter showed when the shift was closed.

**Posted journal entries:** Once a journal entry is posted in Odoo, it cannot be deleted. It can only be reversed (which creates a paper trail). Even database-level deletion would break Odoo's audit sequence.

**Who can do what:**

| Action | Attendant | Supervisor | Accountant | Admin |
|---|---|---|---|---|
| Open shift | No | Yes | No | Yes |
| Enter meter readings | No | Yes | No | Yes |
| Close shift | No | Yes | No | Yes |
| Post journal entries | No | No | Yes | Yes |
| Create customer invoices | No | No | Yes | Yes |
| Post/modify credit customer invoices | No | No | Yes | Yes |
| Delete `fms.meter_log` | Never | Never | Never | Never |
| Change a closed shift's readings | Never | Never | Never | Never |

**Auditors asking about a period:**
Pull: all shift reports (printed PDFs), GL for the period (OCA General Ledger), Aged Receivable at period end, vendor bill register. These four documents, together, give a complete picture of operations.

---

## Quick Reference Card — Accountant Daily/Monthly Tasks

```
DAILY TASKS
─────────────────────────────────────────────────────
After all shifts close:
  [ ] Verify all shifts for today are in Closed state
  [ ] Note total shift GL debits to 191600 for today
  [ ] Get MPesa statement for today from business till
  [ ] Get card terminal report for today
  [ ] Get cash count from supervisor
  [ ] Post daily clearing entry:
        DR  Cash/MPesa/Card accounts
        CR  191600 FMS Cash Clearing
  [ ] Confirm 191600 balance for today = 0

WEEKLY TASKS
─────────────────────────────────────────────────────
  [ ] Run Aged Receivable — chase 60+ day balances
  [ ] Post any pending vendor bills received this week
  [ ] Review Reconciliation Discrepancies account (700002)

MONTHLY TASKS
─────────────────────────────────────────────────────
  [ ] All shifts closed
  [ ] All clearing entries posted — 191600 = 0
  [ ] All vendor bills posted or accrued
  [ ] All customer invoices posted
  [ ] AR reconciled (Aged Receivable = GL 110000)
  [ ] Trial Balance balanced
  [ ] P&L reviewed and approved by manager
  [ ] Balance Sheet reviewed
  [ ] Period locked

KEY CONTACTS
─────────────────────────────────────────────────────
System Admin       : ___________________________
Station Manager    : ___________________________
Fuel Supplier AP   : ___________________________
KRA VAT Officer    : ___________________________
EPRA Contact       : ___________________________

KEY ACCOUNTS
─────────────────────────────────────────────────────
Cash Clearing      : 191600
Cash in Safe       : 101000
MPesa Account      : 102003
Card Receivable    : 102001
AR                 : 110000
Bad Debts          : 624000
Discrepancies      : 700002
```

---

## Assessment — Can the Trainee Handle Month-End Independently?

Before sign-off, the trainee must complete this assessment without assistance using demo data:

1. Post a daily clearing entry for 2026-01-15 (amounts: Cash 100k, MPesa 90k, Card 47.45k).
2. Post a payment from NSS Security Ltd for KES 300,000 against their January invoice.
3. Run the Aged Receivable report for 2026-02-15 and state the outstanding balance for each customer.
4. Run the Trial Balance for January 2026 and confirm it balances.
5. Run the P&L for January 2026 and state: total revenue, gross profit.
6. Identify whether account 191600 is zero after the clearing entry.
7. Explain (verbal) what they would do if a shift supervisor forgot to close yesterday's shift.

**Pass criteria:** All six tasks completed without errors. Verbal explanation of point 7 is logical and complete.

---

## Appendix A — Keyboard Shortcuts and Navigation Tips

| Action | Shortcut |
|---|---|
| Save current record | Ctrl + S |
| Discard unsaved changes | Discard button (top-left of form) |
| Search and filter | Use the search bar at top of list view — click the dropdown for filter presets |
| Open record in new tab | Ctrl + Click on any link |
| Print current form | Use the Print button — do NOT use Ctrl+P (browser print) — it won't format correctly |

## Appendix B — Where to Find Things

| What you need | Where to find it |
|---|---|
| A specific shift | Forecourt → Operations → Shifts → search by date or reference |
| A specific GL entry | Accounting → Journal Entries → search by reference number |
| A customer's open invoices | Accounting → Customers → Invoices → filter by customer + state=Posted |
| A supplier's unpaid bills | Accounting → Vendors → Bills → filter by supplier + state=Posted + payment_state=Not Paid |
| Account balance on a date | Accounting → Reporting → OCA GL → set date and account filter |
| Monthly P&L | Accounting → Reporting → MIS Reports → find or create P&L instance |
| Monthly Balance Sheet | Accounting → Reporting → MIS Reports → find or create BS instance |
| Credit customer outstanding | Accounting → Customers → Customers → open customer record |
| Daily M-Pesa total | Download from M-Pesa business portal for the paybill number |
