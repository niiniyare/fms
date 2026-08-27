# FMS Operations Runbook

Day-to-day operating procedures for the Forecourt Management System.

---

## Daily Shift Workflow

### Open a Shift

1. Go to **Forecourt → Shifts → New**
2. Set `Date` and `Label` (e.g. `2026-09-01`, `1_day`)
3. Assign `Supervisor`
4. Click **Open Shift** — system auto-populates:
   - Meter readings (opening values from previous shift's closing logs)
   - Tank dip entries (one per fuel tank)
5. Attendants record their meter readings during the shift

### Close a Shift

1. Open the shift record
2. Enter **closing meter readings** in the Meter Readings tab:
   - `Close Cash` — electronic cash totalizer reading
   - `Close Elec (L)` — electronic volume totalizer reading
3. Enter **closing tank dips** in the Tank Dips tab:
   - `Closing Dip (L)` — physical dip stick reading per tank
4. Click **Start Closing** — system:
   - Moves shift to `Closing` state
   - Auto-creates Attendant Cash lines (one per attendant)
   - Calculates residual allocations
5. Fill in **Attendant Cash** tab per attendant:
   - `Cash Handover` — physical cash handed to supervisor
   - `MPesa` — mobile money amount
   - `Card` — card payment total
   - `AR / Credit` — credit sales amount
6. Verify all **Gate checks pass** (see Gates section below)
7. Click **Close Shift** — system posts GL journal entries and locks the shift

---

## Hard Gates (Must Pass Before Close)

### Gate 1: FC Cash Balance = 0

**Location:** Attendant Cash tab → FC Cash Balance field (bottom)

**Meaning:** Sum of all attendants' (Total Accountable − Total Declared) must equal zero.

**If non-zero:**
- Find the attendant row highlighted in red
- Verify their cash handover, MPesa, card, AR amounts are correctly entered
- If a genuine variance exists, supervisor posts a correction journal entry via **Accounting → Journal Entries**
- Do NOT close the shift until Gate 1 clears

### Gate 2: All Attendants Clear

**Location:** Attendant Cash tab — each row's Balance column

**Meaning:** Each attendant's individual balance must = 0.

**If non-zero on one attendant:**
- Check their `Cash Handover` vs pump meter sales
- Common cause: attendant forgot to declare MPesa or card amount
- Supervisor can post a short/over adjustment in the journal if cash is genuinely missing

### Gate 3: Stock Variance Within Meniscus

**Location:** Tank Dips tab → Variance % column

**Color coding:**
- Green = ≤ 0.5% (acceptable)
- Orange = 0.5–2.0% (investigate)
- Red = > 2.0% (must resolve before close)

**If red:**
- Verify the dip reading is correct (re-dip if possible)
- Check for delivery during the shift (delivery stock should already be in the dip)
- If variance is real, supervisor posts a stock adjustment via **Inventory → Physical Inventory**

---

## Common Supervisor Actions

### Sync Attendant Cash Lines

Use when: an attendant was assigned to a nozzle after Start Closing, so their cash line is missing.

Click **Sync Attendants** button in the shift header.

### Refresh Sales

Use when: meter entries were edited after Start Closing and the Sales Summary tab shows stale data.

Click **Refresh Sales** button.

### Recalculate Residuals

Use when: product assignments changed or residual allocations look wrong.

Click **Recalculate Residuals** (shows confirmation dialog).

### Emergency Override

If a shift is stuck due to a data error that cannot be resolved via normal workflow:

1. Navigate to the shift
2. Use **Forecourt → Emergency Override** wizard (Supervisor group required)
3. Document the reason — this is logged and audited

---

## Residual Allocations

**Problem:** Attendant reports KES 250,000 Diesel but pump meter shows only KES 180,000 Diesel — the rest was carwash/LPG lumped in.

**System behavior:**
1. Detects under-reported volume per product
2. Allocates the residual litres to the most likely non-fuel product
3. Posts a correction journal: DR Diesel COGS | CR Carwash COGS
4. Shows in the **Residual Allocations** tab

**No action needed** unless the allocation is wrong — use Recalculate Residuals after correcting the entry.

---

## Fuel Deliveries

1. **Forecourt → Fuel Deliveries → New**
2. Enter tanker reference, vendor, delivery date
3. Add one line per product/compartment: product, tank destination, quantity, unit price
4. Enter dip verification fields: `Dip Before`, `Sales During Offload`, `Dip After`
5. Click **Confirm** — system creates:
   - Stock receipt (increases tank inventory)
   - Vendor bill (accounts payable)
6. Delivery variance = `Dip After − (Dip Before + Delivered − Sales During)` — appears on the delivery line

---

## Credit Sales (AR)

1. **Forecourt → Credit Customers** — set up the customer with credit limit and fleet card ref
2. On the shift Attendant Cash line, enter the credit amount in `AR / Credit`
3. At close, an AR journal entry is posted: DR Accounts Receivable | CR Revenue
4. **Forecourt → Reports → AR Statement** — generate customer statement by date range
5. Receive payment via **Forecourt → Payments → Customer Payments**

---

## Petty Cash

1. **Forecourt → Petty Cash → Disbursements → New**
2. Link to shift, assign attendant, enter amount and expense account
3. Click **Post** — creates journal entry DR Expense | CR Petty Cash
4. Disbursements linked to a shift automatically appear in that attendant's `Expenses` column

---

## Reports

| Report | Location | Use |
|---|---|---|
| Shift Report | Shift form → Print Shift Report | End-of-shift summary for supervisor sign-off |
| Meter Movement | Shift form → Print Meter Movement | Nozzle-level sales for audit |
| Daily Station Report | Forecourt → Reports → Daily Station | Cross-shift daily summary |
| Attendant Statement | Forecourt → Reports → Attendant Statement | Per-attendant reconciliation |
| AR Statement | Forecourt → Reports → AR Statement | Customer debt statement |
| VAT Summary | Forecourt → Reports → VAT Summary | Monthly VAT filing support |
| Vehicle Consumption | Forecourt → Reports → Vehicle Consumption | Fleet fuel audit |
| Delivery Register | Forecourt → Reports → Delivery Register | EPRA delivery log |

---

## GL Journal Entries Created on Shift Close

| Entry | Debit | Credit |
|---|---|---|
| Sales journal | Cash/AR/MPesa clearing | Revenue per product |
| VAT (if applicable) | Revenue (net) | Tax Payable |
| Residual allocation | Source product COGS | Target product COGS |
| Stock variance | Inventory variance account | Stock |

All entries are immutable after close. Corrections require a supervisor-posted reversal/adjustment entry.

---

## Audit Trail

- **Meter logs** (`fms.meter_log`) — written on shift close, locked against edit/delete
- **Dip logs** (`fms.dip_log`) — written on shift close and on delivery, locked
- **Chatter** on each shift record — timestamps every state change and user action

Any attempt to modify a closed log raises `ValidationError: Meter/dip logs are immutable after shift close.`

---

## Key Contacts / Escalation

| Issue | Who |
|---|---|
| Shift won't close (gate failure) | Shift Supervisor |
| Journal entry wrong | Station Accountant |
| Stock discrepancy > 2% | Station Manager → EPRA report |
| System error / crash | IT / `abdirahman3878@gmail.com` |
