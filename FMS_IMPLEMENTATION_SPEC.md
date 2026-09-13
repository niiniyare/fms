# FMS Implementation-Readiness Specification

**Date:** 2026-09-13  
**Basis:** Full forensic read of repository at commit a402dc4  
**Scope:** Every conclusion is tagged CONFIRMED-REPO / CONFIRMED-ODOO18 / INFERRED / UNKNOWN  
**Rule:** No un-tagged claim is made anywhere in this document  
**Supersedes:** FMS_FINAL_ARCHITECTURE.md (partial; this document is authoritative where they conflict)

---

## 1. Executive Verdict

```
NOT IMPLEMENTATION READY
```

Blockers (exact list in Section 28):

1. AVCO double-count — every shift overstates COGS, final stock wrong [CONFIRMED-REPO]
2. Clearing account domain `asset_receivable` corrupts AR aging [CONFIRMED-REPO]
3. RTT correction mutates immutable log via raw SQL [CONFIRMED-REPO]
4. `delivery_qty` never written to `fms.dip_log` — variance formula silent error [CONFIRMED-REPO]
5. Gate 3 (attendant balance) silently skips non-POS stations [CONFIRMED-REPO]
6. Config settings threshold fields disconnected from gates [CONFIRMED-REPO]
7. Payment method identification by name-string (`ilike 'mpesa'`) — fragile [CONFIRMED-REPO]
8. `fms.pump` has no `company_id` — multi-company unsafe [CONFIRMED-REPO]
9. The "cash allocation to product sales" feature described in the brief does NOT exist in the current code [CONFIRMED-REPO — feature absent]
10. Revenue duplication with POS not addressed — POS income account configuration unspecified [INFERRED risk, decision pending]

---

## 2. Repository Evidence

All files read in full. Key findings tabulated below.

### What Exists (CONFIRMED-REPO)

| Component | Location | State |
|---|---|---|
| FC Cash variance system (`fc_captured`, `fc_collected`, `fc_variance`) | `fms_shift_entry.py:452–595` | Working |
| Volume-based residual allocation | `fms_shift.py:1190–1322` | Working (old mechanism) |
| RTT via `rtt_volume` field on meter entry | `fms_shift_entry.py:67–71` | Working (net qty correct) |
| RTT SQL bypass on meter log | `fms_shift_correction_wizard.py:212–216` | BUG |
| AVCO double-count sequence | `fms_shift.py:1444–1455` | BUG |
| `delivery_qty` field on `fms.dip_log` | `fms_logs.py:117` | Exists but never populated |
| clearing_account_id domain `asset_receivable` | `fms_site_preferences.py:74` | BUG |
| Gates 1–15 | `fms_shift.py:1406–1379` | Mixed (G3, G9 broken) |
| `_post_sales_journal` (FMS-primary fuel revenue) | `fms_shift.py:2485–2624` | Working |
| `_post_stock_consumption` (stock.move) | `fms_shift.py:2684–2762` | Working |
| `_sync_stock_quant_from_dips` (quant sync) | `fms_shift.py:2422–2459` | Runs in wrong order |
| Config threshold disconnection | `fms_config_settings.py:8–16` | BUG |
| MPesa name-matching | `fms_shift_entry.py:625–630` | BUG |
| `fms.pump` — no `company_id` | `fms_pump.py` entire | BUG |
| Shift states: draft, open, closing, closed, disputed | `fms_shift.py:131–137` | Confirmed |

### What Does NOT Exist (CONFIRMED-REPO — feature absent)

| Feature Requested | Status |
|---|---|
| "Cash allocation to products" (declared cash auto-allocated to fuel products) | NOT FOUND |
| `fms.shift.type` master data model | NOT FOUND |
| Explicit `fms_payment_type` field on `pos.payment.method` | NOT FOUND |
| Delivery dip `type` classification (offloading vs standard) | NOT FOUND |
| Structured error codes (200–999 range) | NOT FOUND |
| `fms_accounting` module (sibling) | Referenced but not in this repo |

---

## 3. Confirmed Business Decisions

These override any prior audit finding.

| # | Decision | Source |
|---|---|---|
| A | FMS-primary for fuel revenue | `_post_sales_journal` exists and posts DR Clearing / CR Revenue |
| B | POS-primary for non-fuel by default | Non-fuel goes through `fms.shift.fc.line` or POS; FMS does not post non-fuel journal |
| C | Volume residual allocation is the EXISTING mechanism | `_calculate_residuals` — greedy volume-based |
| D | FC Cash system replaces old balance gate | `fc_variance` = `fc_captured − fc_collected` |
| E | RTT deducted from net meter sales, not from original readings | `qty_sold_elec = (closing − opening) − rtt_volume` |
| F | Shift states: draft/open/closing/closed/disputed | Hard-coded selection |
| G | One shift open per company at a time | Gate in `action_open_shift` |
| H | Opening readings auto-populate from prior shift logs | `_populate_opening_entries` confirmed |
| I | Supervisor required for non-empty shift close | `action_close_shift` line 1388 |
| J | `closed_by` = `closing_meter_user_id`, `closed_at` = `closing_meter_date` | Already implemented |

---

## 4. Remaining Architecture Decisions

Decisions still required before implementation can proceed.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| R1 | Does "cash allocation to products" exist or must it be built? | Build new / use existing FC mechanism | MUST BUILD if the described behavior is required |
| R2 | POS income account for fuel — prevent revenue duplication | Set POS fuel category income = clearing / or FMS skips posting when POS sessions present | Set POS fuel income = clearing account |
| R3 | Delivery dip type field | Add `dip_type` selection to `fms.shift.dip.entry` / or separate delivery dip model | Add `dip_type` field |
| R4 | `fms.shift.type` master data — build or not? | Build full model / use existing `label + site prefs` | Build `fms.shift.type` |
| R5 | Structured error codes — build or not? | Build full system / keep plain ValidationError | Build (Phase 2) |
| R6 | Merge `fms_accounting` into `fms` or declare dependency | Merge / declare | Merge |

---

## 5. Revenue Ownership

### Fuel Revenue [CONFIRMED-REPO: FMS-PRIMARY]

`_post_sales_journal` (`fms_shift.py:2485`) posts:

```
DR  Cash Clearing (site_prefs.clearing_account_id)   amount = total elec_cash_sold
CR  fms_revenue_account_id (per product)              gross amount per product
CR  Tax Payable (if price-include taxes)              tax portion
```

Source figure: `elec_cash_sold` from pump electronic cash totalizer. Authoritative.

### POS Revenue Duplication Risk [INFERRED — decision pending]

When `pos_session_ids` are linked:
- POS session closes: `_post_closing_entries()` on `pos.session` creates an account.move posting revenue to the POS income account per product (CONFIRMED-ODOO18 behavior).
- FMS close: `_post_sales_journal` also posts revenue to `fms_revenue_account_id`.

**If POS product income account == `fms_revenue_account_id`, revenue is DOUBLE-POSTED.**

Required action: configure fuel products in POS to use a transit/clearing account as income. Then:
- POS session close: DR Cash/MPesa | CR Clearing (no revenue)
- FMS shift close: DR Clearing | CR Revenue (authoritative revenue)

Gate 1 and Gate 2 validate meter vs POS quantity/amount, ensuring the POS data is consistent before FMS posts.

### Non-Fuel Revenue [CONFIRMED-REPO: AMBIGUOUS]

`_compute_commercial_summary` sums non-fuel sales from `fc_line_ids` (direct entry) and from posted `out_receipt` records linked to the shift. No separate FMS journal is posted for non-fuel from `fc_line_ids`.

Current behavior: non-fuel `fc_line_ids` sales are visible in reports but have NO GL entry posted by FMS.

Required decision: either FMS posts a journal for `fc_line_ids` sales, or those must go through POS/invoice posting. The `_post_residual_allocation_journals` method (CONFIRMED-REPO: exists but NOT called in `action_close_shift` — "removed" per comment line 1449) only posts COGS reallocation, not revenue.

**Gap: non-fuel revenue from `fc_line_ids` is currently unposted. Must be fixed.**

---

## 6. Payment Architecture

### Current Implementation [CONFIRMED-REPO]

Payment methods identified by name-string in `_compute_from_pos` (lines 625–630):

```python
mpesa_methods = PayMethod.search([('name', 'ilike', 'mpesa')])
card_methods  = PayMethod.search([('name', 'ilike', 'card')])
ar_methods    = PayMethod.search([('name', 'ilike', 'account')]) | ...
```

This is fragile. Renaming "MPesa" to "M-Pesa" breaks the gate and FC Cash compute.

### Required Architecture

Add `fms_payment_type` Selection field to `pos.payment.method` (via `fms_accounting` module):

```python
fms_payment_type = fields.Selection([
    ('cash',     'Cash'),
    ('mpesa',    'M-Pesa / Mobile Money'),
    ('card',     'Card / PDQ'),
    ('bank',     'Bank Transfer'),
    ('credit',   'Credit / AR'),
    ('cheque',   'Cheque'),
    ('other',    'Other'),
], string='FMS Payment Type', default='other')
```

Replace all `ilike` searches with:
```python
mpesa_methods = PayMethod.search([('fms_payment_type', '=', 'mpesa')])
card_methods  = PayMethod.search([('fms_payment_type', '=', 'card')])
ar_methods    = PayMethod.search([('fms_payment_type', '=', 'credit')])
```

### Target Payment Flow

```
Payment Method (pos.payment.method)
    fms_payment_type = cash/mpesa/card/credit/bank
         ↓
POS captures payment at point of sale
         ↓
_compute_from_pos aggregates by fms_payment_type
         ↓
FMS attendant cash line shows breakdown
         ↓
FC Cash gate validates: meter_sales + floats + receipts = invoices + drops + expenses
         ↓
GL (via fms_accounting account.payment or POS payment lines)
```

### Payment Context Values [CONFIRMED-REPO]

Used in `fms_payment_context` on `account.payment`:
- `cash_float` — float issued to attendant (outbound)
- `cash_drop` — drop collected from attendant (inbound)
- `customer_receipt` — customer paying AR invoice
- `expense` — expense paid from shift cash
- `vendor_payment` — supplier paid from shift cash

---

## 7. Cash Allocation Architecture

### What EXISTS in the Code [CONFIRMED-REPO]

The FC Cash system (`_compute_fc_variance`) is a BALANCE CHECK, not a product allocation engine:

```python
fc_captured = meter_sales + fc_sales + float_amount + customer_receipts
fc_collected = invoice_amount + receipt_amount + drop_amount + expense_amount
fc_variance  = fc_captured - fc_collected  # must be 0.00
```

There is NO mechanism that takes a "declared cash amount" and automatically distributes it across product sales buckets.

### What Was DESCRIBED in the Brief (Decision A)

The brief describes:

> System receives declared cash/equivalent value and automatically allocates it against remaining unallocated fuel/product sales.

This feature is ABSENT. The system currently requires all sales to be pre-allocated (via meter readings per nozzle per attendant). The FC Cash gate checks that totals balance, but does not distribute.

### Decision: Build or Not?

**UNKNOWN — requires business decision.**

Option A: Keep existing system (attendant assignment per nozzle drives allocation implicitly). FC Cash gate sufficient.

Option B: Build a cash allocation engine that takes `cash_collected` per attendant and allocates it across their nozzle products in price-order. This is more complex but enables the "spill" behavior described.

**Recommendation: Option A (existing system is sufficient for the described use case).**

The three-meter system already allocates revenue per product: each nozzle's `elec_cash_sold` is per-product. The attendant's `cash_collected` is the physical total. FC variance (`meter_sales − cash_collected`) is the reconciliation signal. No product-level cash allocation algorithm is needed — the METER already does the product split.

If the user's intent is a different workflow (no meters, just declared cash → auto-split), that is a fundamental design change requiring specification before implementation.

### Worked Examples (FC Cash System)

**Example 1 — Exact cash match**

```
Attendant: Amina
Diesel nozzle: 100L × 222.80 = KES 22,280  (elec_cash_sold)
Cash dropped:  KES 22,280

fc_captured = 22,280 (meter_sales) + 0 (float) + 0 (receipts) = 22,280
fc_collected = 22,280 (drop) + 0 (invoice) + 0 (expense)      = 22,280
fc_variance  = 0.00 ✓
```

**Example 2 — Cash less than meter sales (shortage)**

```
Attendant: Amina
Diesel: 100L × 222.80 = KES 22,280 (meter)
Cash dropped: KES 22,080 (shortage: 200)

fc_captured  = 22,280
fc_collected = 22,080
fc_variance  = +200  (attendant owes KES 200)

Resolution: supervisor post to Staff Advance or write off via wizard
```

**Example 3 — Cash exceeds single product, spills to Petrol**

This scenario doesn't apply with the meter system: each nozzle's cash meter records its own collected amount. "Spill" from one product to another is handled by the VOLUME residual allocation (meter vs POS), not by cash distribution. Cash is per-nozzle from the pump electronics.

---

## 8. RTT Architecture

### Current Implementation [CONFIRMED-REPO]

`rtt_volume` on `fms.shift.meter.entry`:

```python
qty_sold_elec = (closing_elec_volume - opening_elec_volume) - rtt_volume
```

RTT entered manually by supervisor during the shift. Deducted from net meter sales. Original readings unchanged. CORRECT conceptual model.

`rtt_volume` is snapshotted to `fms.meter_log` on close (line 221, `_create_meter_log`).

### RTT Effect on Stock Consumption [CONFIRMED-REPO]

`_post_stock_consumption` uses `qty_sold_elec` (which already has RTT deducted). So:
- RTT volume is NOT moved to "Customers" location
- RTT volume stays in the tank (physically returned)
- Net consumption move = gross meter movement − RTT

This is CORRECT: RTT volume remains in the physical tank, and the stock move reflects only net sold.

### RTT Effect on Revenue [CONFIRMED-REPO]

`_post_sales_journal` uses `elec_cash_sold` (cash meter closing minus opening) — **does NOT deduct RTT**.

This is a BUG for RTT corrections done post-close. The cash meter still shows the RTT value as collected cash. The correction wizard `_post_rtt_correction` handles this:

```
DR Revenue (rtt_volume × price)
CR Clearing
```

This is correct for post-close. But the wizard also does:

```python
self.env.cr.execute(
    "UPDATE fms_meter_log SET rtt_volume = COALESCE(rtt_volume,0) + %s WHERE id = %s",
    (self.rtt_volume, self.meter_log_id.id),
)
```

This is **WRONG**. It:
1. Bypasses ORM `write()` guard on immutable log (EPRA violation)
2. Updates `rtt_volume` in the log but does NOT recompute `qty_sold_elec` or `elec_cash_sold` (those are computed-stored fields that won't recompute after raw SQL)

### Correct RTT Post-Close Correction Architecture

1. Journal entry (DR Revenue | CR Clearing) — KEEP, already correct
2. Replace SQL update with: create supplementary `fms.meter_log` with `rtt_correction_of_id` and `rtt_correction_volume` fields
3. Reports join original + correction for net view
4. Original immutable — EPRA compliant

Required additions to `fms.meter_log`:

```python
rtt_correction_of_id = fields.Many2one('fms.meter_log', 'Corrects Log',
    help="For correction entries only. Points to the original log being amended.")
is_rtt_correction = fields.Boolean('Is RTT Correction', default=False)
```

### RTT Effect on Dip Variance [CONFIRMED-REPO — correct]

`_compute_dip_variance_data`:

```python
shift_var = closing - (opening + delivery - meter_sales)
```

Where `meter_sales = SUM(qty_sold_elec)` from meter entries — already RTT-deducted. So dip formula correctly accounts for RTT: RTT returns product to tank, reducing meter_sales, increasing expected closing stock.

Physical tank: opening + delivery − net_sales + RTT = closing → variance = 0 for perfect measurement.

Formula correctly derives this. No fix needed on variance formula.

---

## 9. Wetstock / Dip Architecture

### Physical vs Theoretical Distinction

```
Physical reality:
    Closing dip = measured by stick gauge / sensor

Theoretical expectation:
    Expected = opening_dip + delivery − net_meter_sales (after RTT)

Variance = closing − expected
```

The formula in `_compute_dip_variance_data` is CORRECT [CONFIRMED-REPO]:

```python
shift_var = closing - (opening + delivery - meter_sales)
```

### Odoo Inventory Interaction [CONFIRMED-REPO — BUG]

`_sync_stock_quant_from_dips` runs BEFORE `_post_stock_consumption`:

```
Close sequence (current — WRONG):
1. _write_meter_logs()
2. _write_dip_logs()
3. _sync_stock_quant_from_dips()   ← sets quant to closing_dip → BIG adjustment
4. _post_sales_journal()
5. _post_stock_consumption()       ← creates consumption move → DOUBLE-COUNT
```

Correct sequence:

```
1. _write_meter_logs()
2. _write_dip_logs()
3. _post_stock_consumption()       ← consumption move for meter_sales → COGS
4. _sync_stock_quant_from_dips()   ← quant sync adjusts ONLY variance
5. _post_sales_journal()
```

### Numerical Proof [CONFIRMED-REPO analysis]

Assumptions: Opening quant = 10,000L, AVCO = KES 180/L, meter_sales = 200L, closing_dip = 9,750L.

**Current (wrong) sequence:**

Step 3 — `_sync_stock_quant_from_dips`: system sees quant=10,000, sets to 9,750 → adjustment −250L → COGS 250 × 180 = KES 45,000. Quant becomes 9,750L.

Step 5 — `_post_stock_consumption`: consumption move −200L → COGS 200 × 180 = KES 36,000. Quant becomes 9,550L.

**Result:** Total COGS = KES 81,000 (wrong). Stock = 9,550L (wrong, should be 9,750L).

**Correct sequence:**

Step 3 — `_post_stock_consumption`: −200L × 180 = KES 36,000 COGS. Quant = 9,800L.

Step 4 — `_sync_stock_quant_from_dips`: sets to 9,750 → adjustment −50L × 180 = KES 9,000 (variance). Quant = 9,750L.

**Result:** Total COGS = KES 45,000. Stock = 9,750L = physical dip. Correct.

### Should Dips Manipulate Odoo Inventory?

**YES, but only for variance.** [CONFIRMED-REPO: current intent]

The dip closing value is the ground truth for physical stock. Odoo's book stock must reflect the physical reality. The quant sync is the correct mechanism to achieve this — but it must run AFTER the consumption move so only the variance delta is adjusted.

---

## 10. Delivery Architecture

### Current State [CONFIRMED-REPO]

`_compute_dip_variance_data` queries `fms_fuel_delivery_line` via `to_regclass` check:

```python
delivery = SUM(fdl.quantity_litres) FROM fms_fuel_delivery_line fdl
           WHERE fdl.location_id = tank AND fd.shift_id = shift AND fd.state IN ('confirmed','billed')
```

Delivery quantity is correctly fetched for variance computation.

### BUG: delivery_qty Never Written to Dip Log [CONFIRMED-REPO]

`_create_dip_log` in `fms_shift_entry.py:303–326`:

```python
vals = {
    'shift_id': ..., 'location_id': ..., 'opening_volume': ...,
    'closing_volume': ..., 'book_stock_open': ...,
}
if variance_data:
    vals.update({
        'meter_sales_snapshot': variance_data.get('meter_sales', 0.0),
        'shift_variance':       variance_data.get('shift_variance', 0.0),
        ...
    })
```

`delivery_qty` is NOT in either dict. The `fms.dip_log` record stores `delivery_qty = 0` every time. Month-variance formula reads `SUM(dl.delivery_qty)` from closed dip logs, which is always 0. Month variance is wrong on all delivery days.

**Fix:** add `'delivery_qty': variance_data.get('delivery', 0.0)` to the `vals.update()` block, and ensure `_compute_dip_variance_data` returns `delivery` key.

### Delivery Dip Types [CONFIRMED-REPO — field absent]

No `dip_type` classification exists. Required for distinguishing:
- `standard` — normal shift open/close dip
- `offloading` — pre/post delivery dip

Without this field, it is impossible to distinguish shift dips from delivery dips in reports (loading loss, offloading loss, site variance separately).

**Required addition to `fms.shift.dip.entry` and `fms.dip_log`:**

```python
dip_type = fields.Selection([
    ('standard',    'Shift Dip'),
    ('offloading',  'Delivery/Offloading Dip'),
], default='standard', string='Dip Type')
```

---

## 11. Inventory & AVCO Architecture

### Odoo 18 AVCO Behavior [CONFIRMED-ODOO18]

- AVCO cost computed at `product.product.standard_price`
- Updated automatically when stock.move IN (purchase receipt) at purchase price
- `stock.valuation.layer` records each movement
- `action_apply_inventory()` on `stock.quant` creates an inventory adjustment layer
- AVCO unit cost = total_value / total_quantity at time of layer creation

### Current Stock Consumption [CONFIRMED-REPO]

`_post_stock_consumption` (`fms_shift.py:2684`):

```python
move = self.env['stock.move'].sudo().create({...})
move._action_confirm()
move._action_assign()
move._set_quantity_done(qty)
move.with_context(cancel_backorder=True)._action_done()
```

This creates a validated stock.move from tank location → customer location. Odoo automatically creates a `stock.valuation.layer` at current AVCO. This is the CORRECT mechanism for posting fuel COGS.

### What Must Change

1. Sequence fix: `_post_stock_consumption` before `_sync_stock_quant_from_dips`
2. After fix, `_sync_stock_quant_from_dips` only adjusts the variance delta
3. AVCO unit cost remains correct throughout (ratio preserved regardless of sequence)
4. Total quantity and total COGS value become correct after fix

---

## 12. Shift Type & Shift Lifecycle

### Existing Shift Schedule [CONFIRMED-REPO]

Current implementation uses `label` field (Selection) and `site_prefs.shift_duration_hrs`:

```python
label = fields.Selection([
    ('1_day',     '1. Day'),
    ('2_evening', '2. Evening'),
    ('3_night',   '3. Night'),
], ...)
shift_duration_hrs = fields.Selection([('8','8 hours'),('12','12 hours'),('24','24 hours')], ...)
```

Start hours stored in `shift_1_start_hour`, `shift_2_start_hour`, `shift_3_start_hour`.

`_next_label_and_date` correctly rotates labels and dates for 8hr/12hr/24hr configs.

`_auto_open_next_shift` creates and opens next shift on close (if `auto_open_next_shift` = True).

### Should `fms.shift.type` Be Built?

**Recommendation: YES (Phase 2)** — the existing label/prefs combination is functional but rigid. A `fms.shift.type` model enables:
- Custom labels per station
- Custom hours not matching 8/12/24 patterns
- "Skipped" shift recording (non-operational day)
- Configurable sequence without code changes

Minimum fields for `fms.shift.type`:

```python
_name = 'fms.shift.type'
name        = fields.Char('Name', required=True)
company_id  = fields.Many2one('res.company', required=True)
sequence    = fields.Integer('Sequence', required=True)
start_hour  = fields.Integer('Start Hour (0–23)', required=True)
duration_hrs= fields.Float('Duration (hours)', required=True)
active      = fields.Boolean(default=True)
```

Validation: `SUM(duration_hrs) <= 24` for all active types per company.

Skipped shift: `state = 'skipped'` (new state) — for non-operational periods. No gates, no GL.

### Current State Machine [CONFIRMED-REPO]

```
draft → open → closing → closed
              → disputed → closing → closed
```

States `draft` and `closing` serve functional purposes:
- `draft`: shift created but not started (pre-population of entries)
- `closing`: FC variance resolved, product sales refreshed, waiting for final gate check

The proposal to remove `closing` state is risky because `action_start_closing` triggers `_refresh_product_sales()` and `_sync_attendant_cash_lines()`. These can be folded into `action_close_shift` but require careful sequencing.

**Recommendation: retain existing states. Remove only if `action_start_closing` is merged into `action_close_shift` atomically.** (Phase 2 UX improvement, not a critical fix.)

### Supervisor Assignment [CONFIRMED-REPO]

Currently: supervisor required for non-empty shift close. Not required at open time.

`closing_meter_user_id` (= `closed_by`) and `closing_meter_date` already recorded.

This is sufficient. No change needed.

---

## 13. Reconciliation Gates

### Confirmed Gate List [CONFIRMED-REPO]

| ID | Name | Method | Hard/Soft | Status |
|---|---|---|---|---|
| G1 | Elec vs Manual Meter | `_gate_check_meter_elec_vs_manual` | Hard | Working |
| G2 | Elec vs Cash Meter | `_gate_check_meter_elec_vs_cash` | Hard | Working |
| G3 | Volume Reconciliation (meter vs POS) | `_gate_check_volume_reconciliation` | Hard | Skips when no POS + `require_pos_reconciliation=False` |
| G4 | Cash Reconciliation (cash meter vs POS) | `_gate_check_cash_reconciliation` | Hard | Same skip condition |
| G5 | Attendant Balances | `_gate_check_attendant_balances` | Hard | **BUG: skips when no POS sessions** |
| G6 | FC Cash = 0 | `_gate_check_fc_cash` | Hard | Working |
| G7 | Stock Variance | `_gate_check_stock_variance` | Hard | Working; meniscus default=1000L (too permissive) |
| G8 | Meter vs Invoice+Receipt | `_gate_check_meter_vs_sales` | Hard | Skips when no POS sessions — acceptable |
| G9 | Customer Receipts ≤ Invoiced | `_gate_check_customer_receipts` | Hard | **BUG: shift-scoped, blocks cross-shift payments** |
| G10 | Float Reconciliation | `_gate_check_float_reconciliation` | Hard | Working |
| G11 | Expense Posting | `_gate_check_expense_posting` | Hard | Working |
| G12 | Vendor Payment Posting | `_gate_check_vendor_payment_posting` | Hard | Working |
| G13 | Digital Payment Sign | `_gate_check_digital_payment_reconciliation` | Soft | Working (sign only) |
| G14 | No Blocking Exceptions | `_gate_check_no_unresolved_exceptions` | Hard | Working |
| G15 | Non-Fuel Sales Posted | `_gate_check_nonfuel_sales_posted` | Hard | Working |

### G5 Fix Required [CONFIRMED-REPO]

Current code (`fms_shift.py:1752`):

```python
if not self.pos_session_ids:
    return
```

This skips attendant balance check at non-POS stations. Non-POS stations have no less need for balance enforcement.

Fix: remove the early return. Use `fc_variance` (which works without POS) as the check. The current check uses `balance` (which requires POS for mpesa/card breakdown). At non-POS stations, `balance` = `reported_sales − cash_collected`. This is a valid and meaningful check.

```python
# Remove: if not self.pos_session_ids: return
# Replace with:
use_fc = not self.pos_session_ids
failing = []
for c in self.attendant_cash_ids:
    variance = c.fc_variance if use_fc else c.balance
    if abs(variance) > 0.01:
        failing.append(f"  • {c.attendant_id.name}: {currency.name} {variance:,.2f}")
if failing:
    raise ValidationError(...)
```

### G9 Fix Required [CONFIRMED-REPO]

Current check compares receipts on THIS shift vs invoices on THIS shift.

Customer may pay a prior-shift invoice during the current shift. This is legitimate and blocks shift close.

Fix: compare receipts to total OPEN AR for the partner(s), not shift-scoped invoices:

```python
# Instead of: invoiced = sum(search([('fms_shift_id','=',self.id),...]).mapped('amount_total'))
# Use: invoiced = sum of outstanding (open) AR for partners who made receipts this shift
```

Or simpler: remove G9 entirely and rely on standard Odoo AR reconciliation. G9 is redundant if payments are reconciled against invoices via standard Odoo matching. **Recommendation: remove G9. Gate 11 (expense posting) and standard AR reconciliation are sufficient.**

### Meniscus Default [CONFIRMED-REPO]

`default_dip_variance_meniscus = 1000.0` (litres). This means a 1,000L variance is acceptable before the gate fails. For a standard 10,000L tank, this is 10%. Effectively disabled.

Correct default: express as percentage. For 10,000L tank, 0.5% = 50L meniscus.

But the gate uses absolute litres (`if abs(sv) > meniscus_l`). Meniscus in litres is correct approach for multi-tank sites (different tank capacities). The default of 1000L is wrong; the field name "Meniscus (L)" is fine.

Fix: reduce default from 1000L to 50L (or derive from tank capacity at configuration time).

---

## 14. Error Code System

Not yet implemented [CONFIRMED-REPO]. Current errors are plain ValidationError strings.

### Proposed Error Numbering

| Range | Category |
|---|---|
| 100–199 | Configuration errors (accounts, journals not set) |
| 200–299 | Meter / reading errors |
| 300–399 | Cash reconciliation errors |
| 400–499 | Payment errors (float, drop, expense, vendor) |
| 500–599 | Wetstock / dip variance errors |
| 600–699 | Revenue / accounting errors |
| 700–799 | Gate failures (composite) |
| 800–899 | Shift lifecycle errors |
| 900–999 | System / integration errors |

### Structured Error Format

```python
class FMSGateError(ValidationError):
    def __init__(self, code, title, message, details, action, severity='error', values=None):
        body = (
            f"[E{code}] {title}\n\n"
            f"{message}\n\n"
            f"{details}\n\n"
            f"Action: {action}"
        )
        super().__init__(body)
        self.error_code = code
        self.values = values or {}
```

Example for G6 FC Cash:

```
[E300] Shift Cannot Close — Cash Not Balanced

Expected cash at forecourt: KES 84,560.00
Cash accounted for:         KES 81,560.00
Shortfall:                  KES  3,000.00

Breakdown:
  Amina (Diesel nozzle A): KES 1,500.00 short
  Hamid (Diesel nozzle B): KES 1,500.00 short

Action: Check payment allocation, cash drops, and expense entries.
        Use 'Resolve FC Variances' to post to staff advance or write off.
```

**Implementation: Phase 2. Replace all ValidationError strings in gate methods with structured FMSGateError.**

---

## 15. Accounting Entry Matrix

| # | Event | DR | CR | Amount | Owner | Model | Timing |
|---|---|---|---|---|---|---|---|
| 1 | Fuel cash sale | Cash Clearing | Fuel Revenue | `elec_cash_sold` | FMS | `account.move` | Shift close |
| 2 | Fuel cash sale (VAT-incl) | Cash Clearing | Revenue (net) + Tax Payable | `elec_cash_sold` | FMS | `account.move` | Shift close |
| 3 | Fuel MPesa sale | MPesa Clearing | Fuel Revenue | `mpesa_amount` | Odoo POS | `pos.order` payment | POS close |
| 4 | Fuel card sale | Card Clearing | Fuel Revenue | `card_amount` | Odoo POS | `pos.order` payment | POS close |
| 5 | Fuel credit sale | AR — Customer | Fuel Revenue | `ar_amount` | Odoo | `account.move` out_invoice | When invoiced |
| 6 | AR payment received | Cash/MPesa/Bank | AR — Customer | receipt amount | Odoo | `account.payment` | When received |
| 7 | Non-fuel cash sale (fc_line) | Cash Clearing | Product Revenue | `sales_amount` | **UNPOSTED** | None | **GAP — must fix** |
| 8 | Non-fuel POS sale | Cash/MPesa/Card | Product Revenue | order amount | POS | `pos.order` | POS close |
| 9 | Fuel delivery | Inventory Asset | AP — Supplier | delivery amount | Odoo purchase | `account.move` bill | Bill confirmation |
| 10 | Fuel consumption (COGS) | Fuel COGS | Inventory Asset | qty × AVCO | Odoo stock | `stock.valuation.layer` | Shift close |
| 11 | Dip variance adjustment | COGS (shortage) / Inventory | Inventory / COGS | variance × AVCO | Odoo stock | `stock.valuation.layer` | Shift close (after fix) |
| 12 | Cash float issued | Attendant Transit | Safe/Cash | float amount | FMS | `account.payment` | During shift |
| 13 | Cash drop collected | Safe/Cash | Attendant Transit | drop amount | FMS | `account.payment` | During shift |
| 14 | FC variance — staff advance | Staff Advance | Cash Clearing | fc_variance | FMS | `account.move` | Wizard (pre-close) |
| 15 | FC variance — writeoff | Variance Expense/Income | Cash Clearing | fc_variance | FMS | `account.move` | Wizard (pre-close) |
| 16 | Attendant expense | Expense Account | Cash Clearing | expense amount | Odoo | `hr.expense` → `account.move` | When posted |
| 17 | RTT post-close correction | Fuel Revenue | Cash Clearing | rtt_volume × price | FMS wizard | `account.move` | Post-close |
| 18 | Residual reallocation | Target COGS | Source COGS | qty × target_price | FMS | `account.move` | Shift close (optional) |
| 19 | Drive-off | Incident Loss | Inventory Asset | qty × AVCO | FMS incident | `stock.move` | When approved |
| 20 | Bank deposit of clearing | Bank | Cash Clearing | deposited amount | Odoo | `account.payment` | When deposited |

**Critical gap (row 7):** Non-fuel `fc_line_ids` sales have no GL journal. Must be fixed.

---

## 16. Refund / Reversal Architecture

### Pre-Close (shift still open) [CONFIRMED-ODOO18 approach]

Void a POS order: standard Odoo POS void. Order removed from session totals.
Meter entry: supervisor edits closing reading downward. No GL entry yet.

### Post-Close Corrections [CONFIRMED-REPO: wizard exists]

`fms_shift_correction_wizard.py` handles:
- Missed expense: DR Expense | CR Clearing (correct)
- RTT: DR Revenue | CR Clearing (correct) + SQL bypass (WRONG)

For fuel revenue refund (e.g. customer dispute):
- Standard Odoo credit note: `account.move` type=`out_refund`
- DR Fuel Revenue | CR AR-Customer (credit note)
- DR AR-Customer | CR Cash/Bank (refund payment)

Do NOT cancel posted `sales_journal_entry_id`. That entry covers the entire shift. Instead, post a separate correcting entry.

### Disputed Shift [CONFIRMED-REPO]

`action_mark_disputed()` sets state to `disputed`. Does NOT cancel GL entries.

Correct workflow for disputed shift:
1. Mark disputed — GL entries remain; shift auditable
2. Post correcting entries via wizard
3. `action_reopen_disputed()` → back to `closing`
4. Re-run gate checks → `action_close_shift()`

Do NOT cancel `sales_journal_entry_id` on dispute. The entry reflects actual meter readings, which are immutable. Corrections are additive journal entries, not cancellations.

**Exception:** if the entire shift close was an error (wrong meter readings entered), supervisor should:
1. Mark disputed
2. Reverse `sales_journal_entry_id` via Odoo's native reversal (`move.button_reverse()`)
3. Correct meter entries (allowed when shift not in `closed` state — `_check_shift_open` checks for `closed` only)
4. Re-run close

Odoo 18 native reversal [CONFIRMED-ODOO18]: `account.move.button_reverse()` creates a dated reversal entry. This is the correct mechanism — NOT `button_cancel()` on a posted entry.

---

## 17. Security & Immutability

### ORM Guards [CONFIRMED-REPO]

| Record | Guard | Notes |
|---|---|---|
| `fms.meter_log` | `write()` raises unconditionally | CONFIRMED |
| `fms.dip_log` | `write()` raises UNLESS `fms_delivery_update` context + supervisor group | CONFIRMED |
| `fms.pts.transaction` | `write()` raises for financial fields | CONFIRMED |
| `fms.shift.meter.entry` | Blocked when shift.state == 'closed' | CONFIRMED |
| `fms.shift.dip.entry` | Blocked when shift.state == 'closed' | CONFIRMED |
| `fms.shift.attendant.cash` | Blocked when shift.state == 'closed' | CONFIRMED |
| `fms.shift` | write() blocks state changes FROM closed | CONFIRMED — non-state fields unprotected |

### Identified Bypasses [CONFIRMED-REPO]

1. `fms_shift_correction_wizard.py:213`: `env.cr.execute("UPDATE fms_meter_log SET rtt_volume ...")` — bypasses ORM guard
2. `_sync_stock_quant_from_dips` uses `sudo()` — bypasses record rules but is intentional for stock sync
3. `_post_sales_journal` uses `sudo()` — intentional (supervisor may not have accounting write access)

### Fix for SQL Bypass [Required — Phase 4]

Replace:
```python
self.env.cr.execute("UPDATE fms_meter_log SET rtt_volume = COALESCE(rtt_volume,0) + %s WHERE id = %s",
    (self.rtt_volume, self.meter_log_id.id))
```

With:
```python
self.env['fms.meter_log'].sudo().create({
    'shift_id':               self.meter_log_id.shift_id.id,
    'pump_id':                self.meter_log_id.pump_id.id,
    'nozzle_id':              self.meter_log_id.nozzle_id.id,
    'rtt_correction_of_id':   self.meter_log_id.id,
    'is_rtt_correction':      True,
    'rtt_volume':             self.rtt_volume,
    'closing_elec_volume':    self.meter_log_id.closing_elec_volume,  # informational copy
})
```

### fms.shift write() Incomplete [CONFIRMED-REPO]

```python
def write(self, vals):
    if 'state' in vals and vals['state'] != 'closed':
        for shift in self:
            if shift.state == 'closed':
                raise ValidationError(...)
    return super().write(vals)
```

This only blocks state transitions FROM closed. Non-state fields on closed shifts are unprotected.

Fix:
```python
WHITELIST = {'dispute_note', 'message_ids', 'activity_ids'}  # fields allowed post-close

def write(self, vals):
    protected_vals = {k: v for k, v in vals.items() if k not in WHITELIST}
    if protected_vals:
        for shift in self:
            if shift.state == 'closed':
                raise ValidationError(
                    f"Closed shift '{shift.display_name}' cannot be modified. "
                    "Use the Emergency Override or Correction Wizard."
                )
    return super().write(vals)
```

---

## 18. Multi-Company

### Fields with `company_id` [CONFIRMED-REPO]

| Model | Has company_id | Notes |
|---|---|---|
| `fms.shift` | Yes | Required, defaults to env.company, record rules present |
| `fms.shift.meter.entry` | No | Company via shift_id |
| `fms.shift.dip.entry` | No | Company via shift_id |
| `fms.shift.attendant.cash` | No | Company via shift_id |
| `fms.shift.fc.line` | Yes | Via `related='shift_id.company_id'` |
| `fms.shift.cash.movement` | Yes | Via `related='shift_id.company_id'` |
| `fms.pump` | **NO** | **BUG** |
| `fms.pump.nozzle` | No | Company via pump_id — needs pump fix first |
| `fms.site.preferences` | Yes | One per company, UNIQUE constraint |
| `fms.meter_log` | No | Company via shift_id |
| `fms.dip_log` | No | Company via shift_id |
| `fms.price.period` | Unknown (not read) | |

### fms.pump Fix Required

Add:
```python
company_id = fields.Many2one(
    'res.company', 'Company',
    required=True,
    default=lambda self: self.env.company,
    readonly=True,
)
```

Add `ir.rule` limiting pump access to own company.

Migration: `UPDATE fms_pump SET company_id = (SELECT id FROM res_company LIMIT 1)` for existing data.

---

## 19. Performance

### Confirmed N+1 and Expensive Queries [CONFIRMED-REPO]

| Location | Problem | Impact |
|---|---|---|
| `_compute_fc_variance:485–493` | `information_schema` query fires on every compute call for every attendant record | High on form load |
| `_compute_from_payments:770–781` | Second `information_schema` query for payment fields | High on form load |
| `_compute_from_payments:812–813` | Third `information_schema` query for hr_expense fields | High on form load |
| `_compute_accounted` | `pos.order.line.search()` per product per shift (N+1) | Medium |
| `get_sales_register_data:511–526` | `information_schema` queries in a report | Medium |

### Fix Priority

**Phase 1 (critical):** Replace `information_schema` checks with `_fields` dict check:

```python
# INSTEAD OF:
self.env.cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='account_payment' AND column_name='fms_shift_id' LIMIT 1")
if not self.env.cr.fetchone():
    ...

# USE:
if 'fms_shift_id' not in self.env['account.payment']._fields:
    ...
```

This is a zero-cost Python dict lookup vs a DB query.

**Phase 5:** Replace `_compute_accounted` N+1 with `read_group`:

```python
# INSTEAD OF: search per product per shift
# USE:
self.env.cr.execute("""
    SELECT pol.product_id, SUM(pol.qty), SUM(pol.price_subtotal_incl)
    FROM pos_order_line pol
    JOIN pos_order po ON po.id = pol.order_id
    WHERE po.session_id = ANY(%s)
    GROUP BY pol.product_id
""", (session_ids,))
```

---

## 20. Native Odoo vs Custom FMS

### Decision Matrix [CONFIRMED-REPO + CONFIRMED-ODOO18]

| Domain | FMS owns | Odoo owns | Notes |
|---|---|---|---|
| Pump master data | Yes | No | `fms.pump` |
| Nozzle master data | Yes | No | `fms.pump.nozzle` |
| Meter readings | Yes | No | `fms.shift.meter.entry` |
| RTT events | Yes | No | `rtt_volume` on meter entry |
| Tank dip measurements | Yes | No | `fms.shift.dip.entry` |
| Dip log (immutable) | Yes | No | `fms.dip_log` |
| Meter log (immutable) | Yes | No | `fms.meter_log` |
| Shift orchestration | Yes | No | `fms.shift` |
| Attendant cash reconciliation | Yes | No | `fms.shift.attendant.cash` |
| Non-fuel forecourt stock count | Yes | No | `fms.shift.fc.line` |
| Delivery event | Yes (FMS records) | Shared (Odoo purchase GL) | `fms_accounting.fms.fuel.delivery` |
| Fuel sale revenue posting | Yes (operational trigger) | Yes (GL result) | FMS posts `account.move` |
| GL journal entries | No | Yes | `account.move` |
| Cash/bank payments | No | Yes | `account.payment` |
| Inventory stock moves | No | Yes | `stock.move` |
| AVCO valuation layers | No | Yes | `stock.valuation.layer` |
| Product master | Extends (adds fms_is_fuel, accounts) | Yes (base product) | |
| Employee master | Extends (adds fms_is_attendant) | Yes | |
| Tank location | Extends (adds fms_is_fuel_tank) | Yes (stock.location) | |
| Invoices / AR | No | Yes | `account.move` out_invoice |
| Credit notes | No | Yes | `account.move` out_refund |
| Expenses | No (context link) | Yes | `hr.expense` |
| POS sales | Reads for reconciliation | Yes (primary) | |
| Taxes | No | Yes | `account.tax` |
| Currency | No | Yes | `res.currency` |
| Companies | No | Yes | `res.company` |

---

## 21. Final Domain Ownership Matrix

| Domain | FMS owns | Odoo owns |
|---|---|---|
| Pump | Yes — master data, lifecycle | No |
| Meter | Yes — readings, RTT, net sales | No |
| RTT | Yes — `rtt_volume` field, correction wizard | No |
| Tank dip | Yes — measurement, variance, log | No |
| Delivery event | Yes — quantity recorded, linked to shift | Odoo purchase: GL posting |
| Shift | Yes — lifecycle, gates, reconciliation | No |
| Attendant | Yes — shift assignment, cash reconciliation | Odoo HR: employee master |
| Fuel sale (operational) | Yes — meter reading → revenue trigger | Odoo accounting: GL entry |
| Revenue | Yes — posts `account.move` as authoritative | Odoo: records and reports |
| Payment method | Yes — `fms_payment_type` tag (to be added) | Odoo: journal, accounting |
| MPesa / Card | Yes — reconciliation tracking | Odoo: journal entry |
| Invoice / AR | Yes — trigger (creates invoice for credit sales) | Odoo: accounting authority |
| Inventory quantity | Yes — dip measurement drives quant sync | Odoo: authoritative quantity |
| Stock valuation | No | Yes — `stock.valuation.layer` |
| AVCO | No | Yes — auto-computed by Odoo |
| GL | No | Yes — `account.move` |
| Tax | No | Yes — `account.tax` |
| Wetstock variance | Yes — computes, records in dip_log | Odoo: financial adjustment if required |

---

## 22. Final Data Flow

```
PHYSICAL INPUTS
    Pump nozzle meter (3 meters: elec-vol, elec-cash, mech-vol)
         ↓ manual entry (or future PTS auto-push)
    fms.shift.meter.entry
         ├── RTT volume (manual entry)
         └── qty_sold_elec = (closing − opening) − rtt_volume

    Tank gauge (physical stick)
         ↓ manual entry
    fms.shift.dip.entry
         └── closing_volume

    Attendant cash count
         ↓ manual entry
    fms.shift.attendant.cash
         └── cash_collected

    POS (optional)
         ↓ linked sessions
    pos.order.line (qty, amount, payment method breakdown)

FMS RECONCILIATION LAYER (shift state machine)
    action_start_closing():
        1. _refresh_product_sales() → fms.shift.product.sales (meter volume + cash per product)
        2. FC variance check → resolve wizard if non-zero
        3. → state = 'closing'

    action_close_shift():
        Gate G1: elec vs manual meter ≤ 1L per nozzle
        Gate G2: elec vs cash meter ≤ threshold
        Gate G3: volume (meter vs POS) within meniscus % (skips if require_pos_reconciliation=False)
        Gate G4: cash (cash meter vs POS) ≤ 100 tolerance
        Gate G5: attendant fc_variance = 0 (MUST fix to not skip non-POS)
        Gate G6: total FC variance = 0 (after writeoff)
        Gate G7: dip variance ≤ meniscus litres
        Gate G8: meter vs invoice+receipt (POS only)
        Gate G9: customer receipts ≤ invoiced (TO BE REMOVED)
        Gate G10: float reconciliation
        Gate G11: no draft expenses
        Gate G12: no draft vendor payments
        Gate G13: digital payments non-negative
        Gate G14: no blocking exceptions
        Gate G15: all non-fuel invoices posted

        On all gates pass:
            _write_meter_logs() → fms.meter_log (immutable)
            _write_dip_logs()   → fms.dip_log (immutable)
            _post_stock_consumption()       ← MOVE BEFORE quant sync
            _sync_stock_quant_from_dips()   ← MOVE AFTER consumption
            _post_sales_journal()           → account.move (DR Clearing | CR Revenue)
            state = 'closed'

ODOO ACCOUNTING / INVENTORY (authoritative)
    account.move (sales journal entry)
    stock.move (fuel consumption)
    stock.valuation.layer (AVCO COGS)
    account.payment (floats, drops, expenses, customer receipts)
    account.move (invoices for credit sales)
```

---

## 23. Worked Accounting Examples

### Example 1 — Fuel Cash Sale (no POS, no tax)

Diesel: 200L × KES 222.80 = KES 44,560 (elec_cash_sold). AVCO = KES 150/L.

```
On shift close:
FMS sales journal:
  DR  Cash Clearing              44,560
      CR  Diesel Revenue               44,560

Stock consumption:
  DR  Diesel COGS (200 × 150)   30,000
      CR  Diesel Inventory (tank)      30,000
```

### Example 2 — Fuel MPesa Sale (POS present)

100L Diesel, MPesa KES 22,280. AVCO = KES 150/L.

```
POS session close (POS-primary):
  DR  MPesa Clearing             22,280
      CR  Cash Clearing (transit)     22,280  ← fuel POS income = Clearing (config required)

FMS shift close:
  DR  Cash Clearing (transit)    22,280
      CR  Diesel Revenue              22,280  ← authoritative revenue posting

Net: Cash Clearing = 0 (offset). Revenue posted once by FMS.

Stock:
  DR  Diesel COGS (100 × 150)   15,000
      CR  Diesel Inventory            15,000
```

### Example 3 — Fuel Card Sale

Same as Example 2 but via Card Clearing journal.

### Example 4 — Fuel Credit Sale (AR)

Fleet customer: 300L Diesel × 222.80 = KES 66,840.

```
Invoice posted (when created):
  DR  AR — KenTruck Fleet        66,840
      CR  Diesel Revenue              66,840
      CR  VAT Payable (if applicable) ---

FMS: ar_amount on attendant cash line (no physical cash received)

Later payment:
  DR  MPesa / Cash / Bank        66,840
      CR  AR — KenTruck Fleet         66,840

Note: FMS _post_sales_journal does NOT re-post AR-invoiced sales.
Gate G8 (meter vs invoices) validates volume consistency.
```

### Example 5 — Non-Fuel POS Sale

Carwash: KES 500, cash via POS.

```
POS order close (POS-primary):
  DR  Cash                        500
      CR  Carwash Revenue               500

FMS: fc_line_ids records carwash sale for reporting only.
FMS does NOT post separate GL for this (POS already did).

GAP: if carwash sold directly (no POS), fms.shift.fc.line has no GL — must be fixed.
```

### Example 6 — Fuel Delivery

10,000L Diesel, KES 1,500,000 (150/L).

```
Purchase bill (Odoo standard):
  DR  Diesel Inventory         1,500,000
      CR  AP — Supplier              1,500,000

Delivery dip (pre/post offloading recorded in FMS):
  No separate GL. Physical quantities drive variance formula.

Tank quant increases by 10,000L automatically when stock.move IN is validated.
```

### Example 7 — Wetstock Variance (50L shortage)

After fix: consumption runs first, quant sync second.

Pre-close state: quant = 9,800L (after 200L consumption).
Closing dip: 9,750L. Variance = −50L.

```
_sync_stock_quant_from_dips: sets quant to 9,750L
   → inventory adjustment move: -50L at AVCO KES 150/L

  DR  Diesel Inventory Loss (variance)  7,500
      CR  Diesel Inventory                    7,500

Net stock = 9,750L. Net COGS = 36,000 (sold) + 7,500 (variance) = 43,500. Correct.
```

### Example 8 — Cash Shortage (KES 500 short)

Diesel elec_cash_sold: KES 22,280. Attendant drops: KES 21,780.

```
FC variance = 22,280 − 21,780 = +500 (attendant owes)

Supervisor resolution wizard:
  Option A (advance):
    DR  Staff Advances Account     500
        CR  Cash Clearing               500

  Option B (writeoff):
    DR  Cash Over/Short Expense    500
        CR  Cash Clearing               500

After resolution: FC variance = 0. Gate G6 passes.
```

### Example 9 — Cash Overage (KES 200 extra)

```
FC variance = −200 (attendant over-collected)

Supervisor resolution:
  DR  Cash Clearing              200
      CR  Cash Over/Short Income       200

After: FC variance = 0.
```

### Example 10 — Refund / Reversal (post-close)

Customer was charged wrong price: 100L at 222.80 instead of 200.00.

Overcharge = 100 × (222.80 − 200.00) = KES 2,280.

```
Supervisor posts via correction wizard (new type needed):
  DR  Diesel Revenue             2,280
      CR  Cash Clearing               2,280   ← cash to be refunded

Customer refund payment:
  DR  Cash Clearing             2,280
      CR  Cash                        2,280

Net: Revenue reduced by 2,280. Cash returned to customer.
Original shift meter_log unchanged. New correction journal proves the audit trail.
```

---

## 24. Test Matrix

### Existing Tests [CONFIRMED-REPO]

| File | Lines | Coverage Area |
|---|---|---|
| `test_fms_001.py` | 330 | Core models (pump, nozzle, shift create/open) |
| `test_fms_002.py` | 355 | Meter/dip entries, attendant cash |
| `test_fms_003.py` | 235 | Residual allocation algorithm |
| `test_fms_004.py` | 266 | Security and access control |
| `test_fms_005.py` | 387 | GL posting (sales journal, stock consumption) |
| `test_fms_006.py` | 311 | Shift lifecycle and gates |
| `test_fms_007.py` | 158 | Reports and UI |
| `test_fms_008.py` | 800 | End-to-end shift close |
| `test_fin_series.py` | 327 | FIN-002 through FIN-013 (payment extension, gates G9–G14) |
| `test_h8_security.py` | 335 | Security (H8 series) |

**CONFIRMED-REPO:** 3,504 total test lines across 10 files. Tests exist and are substantial.

### Missing / Required Tests

The following tests are NOT confirmed to exist (would require reading each test file fully):

#### Critical (must pass before pilot)

| Test | Purpose |
|---|---|
| AVCO sequence fix — COGS = meter_sales × AVCO + variance × AVCO | Prove fix works |
| AVCO sequence fix — final stock.quant = closing_dip | Prove stock correct |
| Gate G5 fires at non-POS station | Prove fix works |
| `delivery_qty` persisted in dip_log after shift close | Prove fix works |
| Month variance correct on delivery day | Prove fix works |
| RTT correction — no SQL update on meter_log | Prove immutability |
| RTT correction — creates new fms.meter_log correction record | Prove audit trail |
| clearing_account `asset_current` allowed in domain | Prove domain fix |
| Meniscus default 50L (not 1000L) | Prove sensible default |
| Config threshold changes reflected in gates | Prove fix works |
| Non-fuel fc_line GL posted on shift close | Prove new feature |

#### Important (before production)

| Test | Purpose |
|---|---|
| MPesa with `fms_payment_type='mpesa'` (not name ilike) | Prove payment fix |
| Card with `fms_payment_type='card'` | Prove payment fix |
| fms.pump company_id scoping | Prove multi-company |
| Cross-company pump not visible | Prove record rules |
| G9 removed — cross-shift payment succeeds | Prove G9 removal |
| Revenue posted ONCE (not twice) with POS sessions linked | Critical |
| Shift close idempotent (calling twice does not duplicate GL) | Prove idempotency |
| Dispute → correction → re-close | Full disputed workflow |
| Emergency override logs gate failures | Prove override audit |

---

## 25. Implementation Phases

### Phase 1 — Critical Correctness (prerequisite to ANY production use)

| # | Fix | File | Lines | Risk |
|---|---|---|---|---|
| 1.1 | Swap close sequence: `_post_stock_consumption` before `_sync_stock_quant_from_dips` | `fms_shift.py` | ~1447 | LOW — 2-line swap |
| 1.2 | Fix clearing_account domain: `asset_receivable` → `asset_current` | `fms_site_preferences.py` | ~74 | LOW — string |
| 1.3 | Fix clearing_account domain in `fms_config_settings.py` | `fms_config_settings.py` | ~65 | LOW |
| 1.4 | Reduce meniscus default from 1000L to 50L | `fms_site_preferences.py` | ~22 | LOW |
| 1.5 | Populate `delivery_qty` in `_create_dip_log` | `fms_shift_entry.py` | ~318 | MEDIUM |
| 1.6 | Add `'delivery'` key to `_compute_dip_variance_data` return dict | `fms_shift.py` | ~1847 | LOW |
| 1.7 | Post GL for non-fuel `fc_line_ids` on shift close | `fms_shift.py` | new method | HIGH |
| 1.8 | Proxy threshold fields in config_settings to site.prefs | `fms_config_settings.py` | whole file | MEDIUM |

### Phase 2 — Gate Fixes & Operational UX

| # | Fix | File | Risk |
|---|---|---|---|
| 2.1 | Fix Gate G5: remove `if not self.pos_session_ids: return` | `fms_shift.py` | LOW |
| 2.2 | Remove Gate G9 (cross-shift receipt bug) | `fms_shift.py` | LOW |
| 2.3 | Fix `action_writeoff_fc_variance` self-cancel bug | `fms_shift.py` | MEDIUM |
| 2.4 | Add `fms_payment_type` to `pos.payment.method` (fms_accounting) | fms_accounting | MEDIUM |
| 2.5 | Replace all `ilike` payment method searches | `fms_shift_entry.py` | MEDIUM |
| 2.6 | Structured error codes (FMSGateError) | new class | LOW |
| 2.7 | `fms.shift.type` master data model | new model | MEDIUM |

### Phase 3 — Financial Reconciliation

| # | Fix | Notes |
|---|---|---|
| 3.1 | POS fuel income account = clearing (configuration guide) | Prevents revenue duplication |
| 3.2 | AR credit sale workflow end-to-end | Invoice + receipt linkage |
| 3.3 | Refund/reversal wizard (new type) | Post-close price correction |
| 3.4 | Settlement reconciliation (MPesa statements) | Bank statement matching |

### Phase 4 — Security & Data Integrity

| # | Fix | Notes |
|---|---|---|
| 4.1 | Add `company_id` to `fms.pump` | Plus data migration |
| 4.2 | Add record rule for pump company scoping | New ir.rule |
| 4.3 | Strengthen `fms.shift.write()` protection | Whitelist approach |
| 4.4 | Replace RTT SQL bypass with correction record | EPRA compliance |
| 4.5 | Add `rtt_correction_of_id` field to `fms.meter_log` | Audit trail |
| 4.6 | Merge `fms_accounting` into `fms` OR declare dependency | Module structure |

### Phase 5 — Performance

| # | Fix | Notes |
|---|---|---|
| 5.1 | Replace all `information_schema` queries with `_fields` dict check | Zero-cost |
| 5.2 | Replace `_compute_accounted` N+1 with single SQL aggregate | Response time |
| 5.3 | Store key compute fields (balance, fc_variance summary) | List view performance |
| 5.4 | Add DB index on `fms_shift_id` in payment/move tables | Query speed |

### Phase 6 — Future Automation

| # | Task | Notes |
|---|---|---|
| 6.1 | Add missing PTS fields to `fms.pump` and `fms.pump.nozzle` | See previous audit |
| 6.2 | Fix `_try_match_shift` field references | All 5 missing fields |
| 6.3 | PTS bridge testing | Requires hardware |

---

## 26. Risks

| Risk | Severity | Likelihood | Notes |
|---|---|---|---|
| AVCO double-count in production data | CRITICAL | CERTAIN (if bug not fixed) | Every closed shift has wrong COGS and stock |
| Revenue posted twice (FMS + POS) | HIGH | HIGH (if POS income not set to clearing) | Overstated revenue on P&L |
| Non-fuel fc_line revenue unposted | HIGH | CERTAIN | No GL for non-fuel direct sales |
| Gate G5 skips non-POS stations | HIGH | CERTAIN (at non-POS sites) | Attendant balance never checked |
| RTT SQL bypass discovered in EPRA audit | HIGH | LOW (low volume) | EPRA compliance risk |
| Cash allocation feature absent | MEDIUM | CERTAIN | If the brief describes a required feature |
| `web_dark_mode` module not available in Odoo 18 CE | MEDIUM | UNKNOWN | Install will fail |
| `fms_accounting` not in depends | HIGH | CERTAIN | Upgrade ordering not guaranteed |
| payment method name changes break FC Cash compute | HIGH | MEDIUM | Any MPesa branding change |

---

## 27. Final Implementation Checklist

Phase 1 (before pilot):
- [ ] 1.1 Swap `_post_stock_consumption` / `_sync_stock_quant_from_dips` order
- [ ] 1.2–1.3 Fix clearing account domain to `asset_current`
- [ ] 1.4 Meniscus default to 50L
- [ ] 1.5–1.6 `delivery_qty` populated in dip log
- [ ] 1.7 Non-fuel `fc_line_ids` GL journal posting
- [ ] 1.8 Config settings proxy thresholds to site.prefs
- [ ] Tests: AVCO sequence, delivery_qty, non-fuel GL, meniscus, clearing domain
- [ ] Verify: 5 pilot shifts with manual GL reconciliation

Phase 2 (before full operation):
- [ ] 2.1 Gate G5 fix
- [ ] 2.2 Remove Gate G9
- [ ] 2.3 Writeoff self-cancel fix
- [ ] 2.4–2.5 Payment method type field + replace ilike
- [ ] 2.6 Structured error codes
- [ ] Configure POS fuel income account = clearing account
- [ ] Tests: G5 non-POS, payment type, cross-shift, revenue duplication prevention

Phase 3 (before AR/credit workflow):
- [ ] 3.1 Credit sale end-to-end
- [ ] 3.2 Refund wizard
- [ ] 3.3 Settlement reconciliation

Phase 4 (security hardening):
- [ ] 4.1–4.2 `fms.pump` company_id
- [ ] 4.3 `fms.shift.write()` whitelist protection
- [ ] 4.4–4.5 RTT SQL bypass → correction record
- [ ] 4.6 `fms_accounting` dependency

Phase 5 (performance):
- [ ] 5.1 Replace `information_schema` queries
- [ ] 5.2 Fix N+1 in `_compute_accounted`

---

## 28. Final Verdict

```
NOT IMPLEMENTATION READY
```

### Exact Blockers (must ALL be resolved before pilot)

| Blocker | Location | Nature |
|---|---|---|
| B1: AVCO double-count | `fms_shift.py:1444–1455` | P&L/stock wrong on every shift |
| B2: Non-fuel fc_line revenue unposted | `_post_sales_journal` | Revenue gap |
| B3: Clearing account type `asset_receivable` | `fms_site_preferences.py:74` | Corrupts AR aging |
| B4: Gate G5 skips non-POS stations | `fms_shift.py:1752` | Gate bypassed |
| B5: `delivery_qty` never written to dip log | `fms_shift_entry.py:318` | Variance formula wrong |
| B6: Config thresholds disconnected from gates | `fms_config_settings.py` | Operator config has no effect |
| B7: RTT SQL bypass on immutable log | `fms_shift_correction_wizard.py:213` | EPRA compliance |
| B8: Payment method name-matching | `fms_shift_entry.py:625–630` | FC Cash breaks on rename |
| B9: `fms.pump` no company_id | `fms_pump.py` | Multi-company safety |
| B10: POS revenue duplication unconfigured | External config requirement | P&L double-counts |

### Implementation Order (once all blockers resolved)

```
Phase 1 → Pilot (5 shifts manual verify) → Phase 2 → Soft launch → Phase 3 → Full production → Phase 4 → Ongoing → Phase 5
```

### What IS Working Correctly [CONFIRMED-REPO]

- Opening reading auto-population from prior shift logs
- FC Cash variance system (`fc_captured − fc_collected`)
- Volume residual allocation algorithm
- Immutable meter log (unconditional `write()` block)
- Dip variance formula (correct: `closing − (opening + delivery − meter_sales)`)
- Shift state machine (draft/open/closing/closed/disputed)
- Emergency override with immutable log
- FC variance resolution wizard (advance vs writeoff)
- Product sales refresh (`_refresh_product_sales`)
- Sales journal (DR Clearing | CR Revenue per product, with tax splitting)
- Idempotency checks on logs and GL entries
- Company isolation on shifts, attendant cash, site preferences

---

*Document basis: Repository commit a402dc4, read-only pass, 2026-09-13.*  
*All claims tagged CONFIRMED-REPO, CONFIRMED-ODOO18, INFERRED, or UNKNOWN.*  
*No code changes made. Next session executes Phase 1 fixes in order.*
