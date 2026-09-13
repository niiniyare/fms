# FMS Adversarial Validation Report

**Date:** 2026-09-13
**Type:** Second-pass forensic validation — adversarial review of FMS_AUDIT_REPORT.md
**Scope:** All 20 parts requested. Read-only. No code modifications.
**Method:** Every finding verified against actual code. Claims marked: CONFIRMED BUG / LIKELY BUG / DESIGN PROBLEM / POSSIBLE PROBLEM / FALSE POSITIVE / MISUNDERSTANDING / NEEDS BUSINESS DECISION / UNPROVEN.

---

## PART 1 — Verification of 20 Critical Claims from First Audit

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| 1 | Revenue posted twice (FMS + POS) | CONFIRMED BUG | `fms_shift.py _post_sales_journal` always runs; POS also posts on session close. No guard disables one path. |
| 2 | AVCO double-counting | CONFIRMED BUG | Close sequence: `_sync_stock_quant_from_dips` (inventory adjustment = full variance) THEN `_post_stock_consumption` (consumption move = meter sales). Both post COGS. |
| 3 | `clearing_account_id` domain wrong | CONFIRMED BUG | `fms_site_preferences.py:74` — domain `asset_receivable`. Should be `asset_current`. Corrupts AR aging. |
| 4 | FC variance writeoff self-cancels | CONFIRMED BUG | `action_writeoff_fc_variance`: `clearing_account = journal.default_account_id or writeoff_account`. When journal has no `default_account_id`: both debit and credit lines use same account → net zero. |
| 5 | Config settings disconnected | PARTIALLY CORRECT | GL account fields (journal, clearing, revenue, COGS) ARE proxied correctly via `_compute_fms_prefs` / `_set_fms_prefs`. Threshold fields (`meniscus_pct`, `elec_vs_cash_threshold_l`) stored in `ir.config_parameter` only — gates read from `prefs.*` — config UI changes have no effect on gate behavior. |
| 6 | Gate 9 blocks cross-shift payments | CONFIRMED BUG | Gate 9 compares receipts to invoices both from current shift window. Cross-shift customer payment fails the gate. |
| 7 | RTT correction wizard corrupts immutable log | CONFIRMED BUG | `fms_shift_correction_wizard.py` posts correct journal entry then runs raw SQL: `UPDATE fms_meter_log SET rtt_volume = ... WHERE id = %s`. Bypasses `write()` ValidationError. |
| 8 | `delivery_qty` never populated | CONFIRMED BUG | `fms_shift_entry.py _create_dip_log`: neither the base dict nor the `variance_data` update block includes `delivery_qty`. Field exists on `fms.dip_log`, never written. |
| 9 | Closed shifts allow field edits | CONFIRMED BUG | `fms_shift.py write()` only checks `if 'state' in vals and vals['state'] != 'closed'`. Non-state fields unprotected on closed shifts. |
| 10 | PTS integration broken | CONFIRMED BUG | `_try_match_shift` references `fms.shift.date_start` (doesn't exist), `fms.pump.pts_device_id` (doesn't exist), `fms.pump.pts_pump_number` (doesn't exist), `fms.pump.nozzle.pts_nozzle_number` (doesn't exist). Will raise `AttributeError` on first transaction. |
| 11 | `information_schema` query on every compute | CONFIRMED DESIGN PROBLEM | `fms_shift_entry.py _compute_fc_variance` executes 3-table `information_schema` query synchronously every time FC variance recomputes. |
| 12 | Gate 14 redundant | FALSE POSITIVE | Gate 14 IS meaningful in `_apply_emergency_override()` path — that method permits override from 'disputed' state. In that path, G14 fires and is recorded as bypassed gate. |
| 13 | M-Pesa name-based lookup fragile | CONFIRMED DESIGN PROBLEM | `_compute_from_pos` uses `PayMethod.search([('name', 'ilike', 'mpesa')])`. Breaks on rename, translation, or different station naming. |
| 14 | Gate 3 skips non-POS stations | CONFIRMED BUG | `if not self.pos_session_ids: return` — non-POS stations have no attendant balance check. |
| 15 | fms_accounting undeclared dependency | CONFIRMED DESIGN PROBLEM | Not in `__manifest__.py` depends. Detected at runtime via `information_schema`. Race condition risk during upgrade. |
| 16 | Stock moves orphaned (no picking) | FALSE POSITIVE | Headless stock moves without picking are standard in Odoo for automated consumption (MRP, inventory adjustment). Not an error. |
| 17 | `fms.pump` missing `company_id` | CONFIRMED DESIGN PROBLEM | No `company_id` field. UNIQUE(name) is global. Multi-site deployment fails. |
| 18 | `fms.shift.product.sales` FK instability | MISUNDERSTANDING | No direct FK to product.sales from reconciliation. Less dangerous than claimed. Recompute on shift open is correct. |
| 19 | Meniscus default 1000L | LIKELY BUG | `fms_site_preferences.py default_dip_variance_meniscus = 1000.0`. Spec says 0.5%. 1000L on a 10,000L tank = 10% tolerance — Gate 7 is effectively disabled. Needs business confirmation. |
| 20 | Dip log context bypass unsecured | MISUNDERSTANDING | `fms.dip_log.write()` does check `has_group('fms.group_fms_supervisor')` before allowing bypass. Less severe than first audit claimed. |

---

## PART 2 — Accounting Forensic Trace (10 Transaction Types)

### T1: Normal Diesel Sale (no POS, FMS-primary)

```
Shift close → _post_sales_journal:
  DR  Diesel COGS Account         volume × price
  CR  Diesel Revenue Account      volume × price

_post_stock_consumption:
  stock.move (done): location=tank, location_dest=virtual/consumption
  Odoo AVCO: creates stock.valuation.layer → DR COGS CR Stock Valuation

RESULT: COGS posted twice (journal + valuation layer). Revenue posted once.
STATUS: CONFIRMED BUG
```

### T2: Diesel Sale with POS active

```
POS session close → account.move posted by Odoo POS:
  DR  Cash / Payment Clearing     amount
  CR  Diesel Revenue Account      amount

FMS shift close → _post_sales_journal:
  DR  Diesel COGS Account         volume × price
  CR  Diesel Revenue Account      volume × price   ← DUPLICATE

RESULT: Revenue doubled. COGS posted once (correct amount but wrong timing).
STATUS: CONFIRMED BUG
```

### T3: Carwash Sale (lumped into Diesel, residual allocated)

```
Residual detected: Diesel volume over-reported by 100L
→ _post_residual_allocation (if implemented):
  DR  Diesel Revenue              100L × diesel_price
  CR  Carwash Revenue             100L × carwash_price
  DR/CR COGS adjustment

Code comment: "Residual allocation journals removed"
RESULT: Residual detected, journal NOT posted. Diesel revenue overstated. Carwash understated.
STATUS: CONFIRMED BUG (incomplete implementation)
```

### T4: M-Pesa Payment

```
Attendant records M-Pesa collection in fms.shift.attendant.cash
→ _post_sales_journal posts revenue (CR Revenue)
→ M-Pesa "collection" should: DR M-Pesa Clearing CR Cash-in-Hand
→ Current code: no separate M-Pesa clearing entry found in _post_sales_journal

Reconciliation path: undefined. M-Pesa clearing never settled to bank.
STATUS: DESIGN PROBLEM — M-Pesa hangs in clearing permanently
```

### T5: FC Cash Variance Writeoff

```
fc_variance = fc_captured - fc_collected (e.g., KES 500 short)

action_writeoff_fc_variance:
  clearing_account = journal.default_account_id or writeoff_account
  
  Case A (journal has default_account_id):
    DR  Fuel Variance (P&L)       500
    CR  Cash Clearing             500   ← correct

  Case B (journal.default_account_id is null):
    clearing_account = writeoff_account
    DR  Fuel Variance             500
    CR  Fuel Variance             500   ← same account, net zero

STATUS: CONFIRMED BUG (Case B — self-cancelling)
```

### T6: Customer AR Sale (credit sale)

```
Invoice raised → account.move:
  DR  Accounts Receivable         amount
  CR  Revenue                     amount

FMS shift close also posts revenue (T1 above):
  DR  COGS
  CR  Revenue  ← DUPLICATE if POS also posted

Gate 9 checks: receipts ≤ invoiced
  Cross-shift payment → receipts from THIS shift, invoices from PREV shift
  → Gate 9 fires ValidationError → shift cannot close
STATUS: CONFIRMED BUG (Gate 9 cross-shift)
```

### T7: Fuel Delivery Received Mid-Shift

```
Delivery posted via stock.move (purchase receipt):
  DR  Tank Stock (asset)          delivery_qty × cost
  CR  Supplier Payable            delivery_qty × cost

fms.dip_log.delivery_qty: never populated
→ Shift variance formula: closing_dip - opening_dip - delivery - meter_sales
→ delivery = 0 (always) → variance includes full delivery volume as "loss"

STATUS: CONFIRMED BUG
```

### T8: RTT (Return to Tank) Correction

```
Correction wizard:
  Step 1 (correct): 
    DR  Revenue                   rtt_volume × price
    CR  RTT Clearing              rtt_volume × price
    → account.move posted
    
  Step 2 (WRONG):
    UPDATE fms_meter_log SET rtt_volume = rtt_volume + %s WHERE id = %s
    → Raw SQL modifies immutable log
    → rtt_volume changes affect qty_sold_elec stored computed field (but log is immutable — stored value doesn't recompute)

STATUS: CONFIRMED BUG — journal entry correct, SQL update wrong and useless
```

### T9: Attendant Expense (e.g., pump oil purchase)

```
hr.expense submitted against shift:
  DR  Expense Account             amount
  CR  Employee Payable            amount

FMS: expense reduces attendant balance in Gate 3 check
Gate 3 SKIPS for non-POS stations → expense never validated against cash
STATUS: CONFIRMED BUG (inherited from Gate 3 skip)
```

### T10: Month-End Stock Variance Adjustment

```
fms.dip_log stores month_variance and month_var_amount
These are populated at shift close (one-time snapshot)

No GL entry for month variance exists in code.
fms_shift.py has no _post_month_variance_journal method.

STATUS: DESIGN PROBLEM — month variance tracked but never posted to GL
```

---

## PART 3 — Accounting Entry Matrix

| Transaction | DR | CR | Status |
|-------------|----|----|--------|
| Meter sale (FMS-primary) | COGS | Revenue | BUG: COGS doubled (journal + valuation layer) |
| Meter sale (POS active) | COGS | Revenue ×2 | BUG: Revenue doubled |
| FC cash variance writeoff | Fuel Variance | Fuel Variance (same) | BUG: self-cancels when journal has no default account |
| M-Pesa collection | Clearing | ??? | INCOMPLETE: no settlement path |
| Customer AR | AR | Revenue | OK — standard Odoo invoice |
| Fuel delivery | Tank Stock | Supplier Payable | OK — standard purchase receipt |
| RTT correction | Revenue | RTT Clearing | Journal correct; SQL update wrong |
| Residual allocation | Revenue A | Revenue B | INCOMPLETE: code removed |
| Month variance | ??? | ??? | MISSING: no GL posting |
| Attendant expense | Expense | Employee Payable | OK — standard hr.expense |

---

## PART 4 — AVCO Forensics (Numerical Example)

**Setup:** Tank has 10,000L. AVCO unit cost = KES 100/L. Total stock value = KES 1,000,000.

**Shift:** Meter sales = 200L. Closing dip = 9,750L (physical). Variance = 50L (evaporation/loss).

**Current close sequence:**

```
Step A — _sync_stock_quant_from_dips:
  Odoo stock.quant at close: 10,000L (before consumption move)
  Physical dip: 9,750L
  Inventory adjustment: -250L
  stock.valuation.layer: DR COGS 250 × 100 = KES 25,000 | CR Stock Valuation KES 25,000
  Stock after: 9,750L | Value: KES 975,000 | AVCO: 100/L (ratio preserved ✓)

Step B — _post_stock_consumption:
  Consumption move: -200L (meter sales)
  stock.valuation.layer: DR COGS 200 × 100 = KES 20,000 | CR Stock Valuation KES 20,000
  Stock after: 9,550L | Value: KES 955,000 | AVCO: 100/L (ratio preserved ✓)

Step C — _post_sales_journal:
  DR COGS (journal)  KES 20,000
  CR Revenue         KES 20,000
```

**Net result:**
- COGS posted: KES 25,000 (inventory adj) + KES 20,000 (consumption) + KES 20,000 (journal) = KES 65,000
- Only 200L was metered. COGS should be KES 20,000.
- Stock: 9,550L (200L below physical dip of 9,750L)
- AVCO unit cost stays correct (100/L) but total value KES 45,000 understated

**Correct sequence:**
```
Step 1 — _post_stock_consumption:
  Consumption move: -200L
  Stock: 9,800L | Value: KES 980,000

Step 2 — _sync_stock_quant_from_dips (redefined as variance recording only):
  Inventory adjustment for variance only: -(9,800 - 9,750) = -50L
  COGS: 50 × 100 = KES 5,000 (true evaporation loss)
  Stock: 9,750L | Value: KES 975,000

Step 3 — _post_sales_journal:
  (Post revenue only, not COGS — let stock valuation layer handle COGS)
  CR Revenue KES 20,000
  (DR COGS already posted by stock.valuation.layer in Step 1)
```

---

## PART 5 — POS vs FMS Architecture

**Current architecture (broken):**
- POS session active → POS posts revenue on close
- FMS shift close → also posts revenue
- No mutual exclusion

**Option A: FMS-primary (recommended for fuel stations)**
- Disable POS accounting: set journal on `pos.config` to a clearing journal with no P&L impact
- FMS handles all revenue and COGS GL posting
- POS used only for transaction capture (correct totals feed into `_compute_from_pos`)
- Requires: modify `pos.config.fms_clearing_journal` + guard in `_post_sales_journal`

**Option B: POS-primary**
- FMS reads POS data for reconciliation only
- FMS posts no revenue journal
- FMS only posts variance adjustments and meter/dip audit logs
- Simpler but loses FMS nozzle-level granularity in GL

**Current state:** Neither option implemented. Both systems post. CONFIRMED architectural gap.

---

## PART 6 — Payment Architecture

**M-Pesa path:**
```
Attendant records KES 50,000 M-Pesa in fms.shift.attendant.cash.mpesa_amount
→ Gate 1: fc_variance must = 0 (fc_captured - fc_collected)
→ fc_captured includes M-Pesa (computed from POS)
→ fc_collected: manual entry by supervisor
→ If they match: Gate 1 passes

GL entry for M-Pesa: NONE found in code.
Clearing account balance accumulates. Never reconciled to bank statement.
```

**Card path:** Same gap — no settlement entry.

**Cash path:** 
```
Cash drop → account.payment (DR Cash | CR Clearing)
Clearing settled on bank statement matching (standard Odoo)
This path works correctly.
```

**Fix needed:** Add GL entry on M-Pesa/card capture: DR M-Pesa Receivable | CR Revenue Clearing. Settle on Safaricom statement import.

---

## PART 7 — Shift State Machine

**States:** `draft → open → closing → closed` + `disputed` (exception path)

**Transitions verified in code:**

| From | To | Method | Guard |
|------|----|--------|-------|
| draft | open | `action_open` | Site prefs configured |
| open | closing | `action_request_close` | Any user |
| closing | closed | `action_close` | 15 gates pass |
| closing | disputed | `action_mark_disputed` | Supervisor |
| disputed | closing | `action_resolve_dispute` | Supervisor |
| any | closed | `_apply_emergency_override` | Manager + override log |

**Issue:** `fms_pts.py` searches for `state in ['open', 'in_progress', 'draft']`. `in_progress` is not a valid state. Search silently ignores it (Odoo domain `in` with invalid value just doesn't match). No error, but `in_progress` matches nothing.

**Write protection:** `fms_shift.py write()` checks `if 'state' in vals and vals['state'] != 'closed'`. Non-state fields unprotected when shift is closed. Direct ORM calls (including wizard code) can modify closed shift data.

---

## PART 8 — Gate Analysis

| Gate | Name | Implementation | Status |
|------|------|----------------|--------|
| G1 | FC Cash = 0 | `fc_variance == 0` | OK — correct |
| G2 | Elec vs cash threshold | Reads `prefs.elec_vs_cash_threshold_l` | OK — but threshold config disconnected (H1) |
| G3 | Attendant balances | Skips if no `pos_session_ids` | BUG — non-POS stations skip |
| G4 | All meter entries complete | Checks required fields | OK |
| G5 | All dip entries complete | Checks required fields | OK |
| G6 | No negative stock | Checks closing dip > 0 | OK |
| G7 | Dip variance < meniscus | Reads `prefs.default_dip_variance_meniscus` (default 1000L) | LIKELY BUG — default too high |
| G8 | All attendants cleared | Same as G3 | BUG — same skip |
| G9 | Receipts ≤ invoiced | Per-shift domain | BUG — cross-shift payments fail |
| G10 | No open exceptions | Checks `fms.exception` state | OK |
| G11 | Stock moves confirmed | Checks pending moves | OK |
| G12 | Journal entries balanced | Checks unposted moves | OK |
| G13 | Residual allocated | Checks `residual_allocation_ids` | INCOMPLETE — allocation journals removed |
| G14 | No unresolved exceptions | Redundant with G10 on normal path | Meaningful in emergency override path |
| G15 | Supervisor approval | Checks `approved_by_id` | OK |

---

## PART 9 — Wetstock Domain Model

**Variance formula (correct):**
```
shift_variance = closing_dip - (opening_dip + delivery - meter_sales)
```

**Implementation in `_create_dip_log`:**
```python
shift_variance = closing_volume - opening_volume - meter_sales_snapshot
# delivery_qty missing → formula = closing - opening - sales
# Correct formula: closing - (opening + delivery - sales)
# Actual: closing - opening - sales
# Difference: delivery volume treated as unexplained loss
```

**Month variance:** Stored in `fms.dip_log.month_variance`. Computed at shift close. Never posted to GL. No method for month-start resetting.

**ATG integration:** No model for automatic tank gauge. PTS-2 handles pump transactions only. Tank readings are manual dip entries.

---

## PART 10 — PTS Status

**Protocol understanding:** CORRECT. `fms_pts.py` accurately models jsonPTS `UploadPumpTransaction` packet fields.

**What works:**
- `fms.pts.device` model — stores device serial, last seen, WS connected flag
- `fms.pts.transaction` model — correct field mapping to jsonPTS packet
- Immutability guards on transaction records
- `create_from_pts` entry point for WebSocket bridge calls

**What is broken (non-functional):**

| Reference in code | Reality |
|-------------------|---------|
| `fms.shift.state in ['in_progress']` | State doesn't exist |
| `fms.shift.date_start` | Field doesn't exist on fms.shift |
| `fms.pump.pts_device_id` | Field doesn't exist on fms.pump |
| `fms.pump.pts_pump_number` | Field doesn't exist on fms.pump |
| `fms.pump.nozzle.pts_nozzle_number` | Field doesn't exist on fms.pump.nozzle |
| `fms.shift.meter.entry.pts_transaction_id` | Field doesn't exist |
| `fms.shift.meter.entry.pts_volume` | Field doesn't exist |
| `fms.shift.meter.entry.pts_tc_volume` | Field doesn't exist |
| `fms.shift.meter.entry.closing_totalizer` | Field doesn't exist |

**Assessment:** SCAFFOLDING. Protocol understood, models exist, all matching logic broken. 9 missing fields needed to make matching functional.

---

## PART 11 — Native Odoo Model Review (24 Models)

| Model | Purpose | Issues |
|-------|---------|--------|
| `fms.shift` | Main orchestration | God class (2762L), close sequence bug, write protection gap |
| `fms.shift.meter.entry` | Pump readings | Missing PTS fields, name-based payment lookup |
| `fms.shift.dip.entry` | Tank dip readings | OK |
| `fms.shift.attendant.cash` | Cash reconciliation | Gate 3 skip affects this |
| `fms.shift.product.sales` | Computed product totals | N+1 in accounted compute |
| `fms.shift.residual.allocation` | Residual tracking | Journals removed — incomplete |
| `fms.shift.override.log` | Override audit trail | OK — correct design |
| `fms.shift.exception` | Exception tracking | OK |
| `fms.meter_log` | Immutable meter audit | write() correct; bypassed by wizard |
| `fms.dip_log` | Immutable dip audit | delivery_qty never populated |
| `fms.pump` | Pump master | Missing company_id, missing PTS fields |
| `fms.pump.nozzle` | Nozzle master | Missing pts_nozzle_number |
| `fms.pts.device` | PTS controller | OK as-is |
| `fms.pts.transaction` | PTS transactions | Matching broken (field references) |
| `fms.price.period` | Fuel price history | OK |
| `fms.site.preferences` | Station config | Wrong clearing account domain |
| `fms.config.settings` | Settings proxy | Threshold fields disconnected |
| `fms.attendant.statement` | Report model | OK |
| `fms.shift.report` | SQL view | OK |
| `fms.tank.stock.summary` | SQL view | OK |
| `fms.product.summary` | SQL view | OK |
| `fms.delivery.order` | Fuel delivery | OK |
| `fms.delivery.order.line` | Delivery lines | OK |
| `fms.expense.category` | Expense categories | OK |

---

## PART 12 — OCA Research

**Applicable OCA modules (Odoo Community Association):**

| OCA Module | Relevance | Use |
|------------|-----------|-----|
| `account_move_template` | Journal entry templates | Replace 200-line `_post_sales_journal` with template instantiation |
| `account_payment_clearing` | Clearing account management | May solve M-Pesa/card settlement gap |
| `stock_inventory_cost_info` | AVCO visibility | Debugging aid for stock valuation issues |
| `mis_builder` | Management reporting | Replace SQL view reports |

**Assessment:** OCA modules are optional enhancements. None are blockers. `account_move_template` offers the most value for maintainability of the GL posting logic.

---

## PART 13 — Security Forensics

**Attack scenario 1: Bypass immutable meter log**
```
Attacker with DB access or ORM bypass context:
  self.env['fms.meter_log'].browse(id).sudo().write({'closing_elec_volume': 9999})
  → ValidationError (unconditional in write())
  
  But: direct SQL via any model with cr.execute:
  self.env.cr.execute("UPDATE fms_meter_log SET closing_elec_volume = 9999 WHERE id = %s", (id,))
  → Succeeds. No guard at DB level.
  
STATUS: Immutability is ORM-layer only. Not DB-enforced.
```

**Attack scenario 2: Escalate to supervisor mid-gate**
```
Gate 3 skips for non-POS station → no attendant check.
Attacker posts attendant cash entries after Gate 3 passes.
Shift closes with unvalidated attendant balances.
STATUS: CONFIRMED gap — Gate 3 skip is an attack surface.
```

**Attack scenario 3: Modify closed shift data**
```
fms_shift.write() only protects state changes.
Supervisor calls: shift.write({'fc_collected': 0})  ← on closed shift
→ Succeeds. No error.
STATUS: CONFIRMED — closed shift data mutable via ORM.
```

**Positive security findings:**
- `fms.dip_log` delivery update bypass requires supervisor group check ✓
- `fms.shift.override.log` correctly records bypass actor and timestamp ✓
- `fms.pts.transaction` immutability guards are correct ✓
- Access control groups exist and are structured correctly ✓

---

## PART 14 — Data Integrity

| Integrity Concern | Status |
|-------------------|--------|
| Duplicate PTS transaction | UNIQUE(pts_device_id, pts_transaction_id) ✓ |
| Duplicate shift meter entry | UNIQUE(shift_id, nozzle_id) — needs verification |
| Orphaned meter logs (shift deleted) | `ondelete='cascade'` on shift_id ✓ |
| Nozzle letter unique per pump | `@constrains` check ✓ |
| Opening reading from previous shift | Rule 3 in spec — implementation not verified in this pass |
| Residual allocation sums to zero | Greedy algorithm correct but no constraint enforcing it |
| Month variance reset at period start | No implementation found |

---

## PART 15 — Performance Analysis

| Hotspot | Type | Severity |
|---------|------|----------|
| `_compute_fc_variance`: 3× `information_schema` queries | N-per-compute DB hit | HIGH — runs on every record load |
| `_compute_accounted` in product.sales: 1 POS search per line | N+1 | MEDIUM |
| `_compute_from_pos`: multiple `search()` calls without cache | N-per-shift | MEDIUM |
| `_try_match_shift` in PTS: sequential searches | N per transaction | LOW (PTS broken anyway) |
| `nozzle_count` on pump: `len(nozzle_ids)` vs `read_group` | Minor | LOW |

**Fix priority:** `information_schema` query first (HIGH, one-line fix per field check).

---

## PART 16 — God Class Analysis

`fms_shift.py` — 2762 lines, single model, handles:

1. State machine (7 states, 6 transitions)
2. 15 hard gates
3. GL journal posting (sales, COGS, variance)
4. Stock moves (consumption, inventory adjustment)
5. Audit log creation (meter logs, dip logs)
6. Residual allocation (detection + allocation)
7. Dashboard computed fields
8. Report generation
9. Scheduling (shift auto-open)
10. Emergency override

**Verdict:** Refactor into mixins after bugs fixed. Suggested split:
- `ShiftStateMixin` — state transitions + write protection
- `ShiftGateMixin` — 15 gate methods
- `ShiftAccountingMixin` — GL posting
- `ShiftStockMixin` — stock moves
- `ShiftAuditMixin` — log creation
- `fms.shift` — orchestration only

**Do not refactor while bugs exist.** Mixin extraction without tests risks introducing new bugs.

---

## PART 17 — Documentation vs Code Verification

| Documented Claim | Code Reality | Status |
|------------------|--------------|--------|
| "FC Cash must = 0 exactly" | Gate 1: `fc_variance == 0` | MATCH ✓ |
| "Opening readings auto-fetched from previous shift" | Not found in `action_open` | UNPROVEN |
| "Residuals always allocated" | Allocation journals removed | MISMATCH ✗ |
| "Hard gates non-negotiable" | Emergency override path exists | PARTIAL — gates bypassable with log |
| "EPRA tamper-proof audit trail" | SQL bypass in wizard | MISMATCH ✗ |
| "Meniscus default 0.5%" | Default = 1000L | MISMATCH ✗ |
| "PTS-2 integrated" | Scaffolding only | MISMATCH ✗ |
| "Config settings control gate thresholds" | Thresholds disconnected | MISMATCH ✗ |
| "GL accounts configured per site" | GL accounts correctly proxied | MATCH ✓ |

---

## PART 18 — Corrections to Previous Audit

| Previous Claim | Correction | Type |
|----------------|------------|------|
| "Config settings entirely disconnected" | GL account fields correctly synced via `_set_fms_prefs`. Only threshold fields disconnected. | PARTIAL CORRECTION |
| "Gate 14 fully redundant" | G14 meaningful in emergency override path from 'disputed' state. | CORRECTION |
| "Dip log context bypass unsecured" | Supervisor group check IS present. Less severe than claimed. | CORRECTION |
| "AVCO unit cost shifts" | AVCO unit cost STAYS correct (ratio preserved). Total value and quantity wrong. | PRECISION CORRECTION |
| "product.sales FK instability dangerous" | No direct FK from reconciliation to product.sales. Risk lower than claimed. | CORRECTION |
| "Stock moves orphaned = bug" | Headless stock moves without picking are standard Odoo pattern for automated consumption. | FALSE POSITIVE |
| "fms.pump name UNIQUE = bug" | Design problem, not bug. Single-site deployment is fine. Multi-site needs company scope. | RECLASSIFICATION |

---

## PART 19 — Final Architectural Decisions (24 Questions)

**Q1. Single source of truth for fuel inventory?**
Stock quant. `_sync_stock_quant_from_dips` forces dip=quant but runs before consumption move, breaking the chain. Fix: remove quant sync; let stock moves be sole driver. Dip log = physical measurement, not authoritative for GL.

**Q2. Clearing accounts — use `asset_receivable` or `asset_current`?**
`asset_current` (current liability). FC cash clearing is internal, never owed by customer. `asset_receivable` corrupts AR aging reports and Odoo's `partner_type` reconciliation. One-line fix in `fms_site_preferences.py:74`.

**Q3. M-Pesa — is it AR or cash equivalent?**
NEEDS BUSINESS DECISION. Option A: Cash equivalent — DR Bank/Mobile Money, CR Revenue on shift close. Option B: AR — DR M-Pesa Receivable, CR Revenue; cleared when Safaricom settles. Current code creates unreconcilable balance because both sides use same clearing account on different documents.

**Q4. POS integration — parallel revenue or FMS-only?**
Cannot be both. Choose: (A) POS-primary: FMS reads POS data for reconciliation only, posts no revenue. (B) FMS-primary: disable POS accounting, FMS posts all revenue. Current code assumes FMS-primary but doesn't disable POS accounting. NEEDS BUSINESS DECISION.

**Q5. Stock moves — with picking or without?**
Without picking is acceptable for automated FMS consumption. The orphan concern was a false alarm. Standard Odoo pattern.

**Q6. AVCO vs standard price for fuel?**
AVCO is correct. Fix the sequence bug, not the method.

**Q7. `fms_accounting` — declare as dependency or inline?**
Declare in `__manifest__.py` depends. Replace `information_schema` detection with `'fms_shift_id' in self.env['account.payment']._fields` — pure Python O(1).

**Q8. Site preferences vs `ir.config_parameter` — pick one?**
Site preferences. Proxy all threshold/schedule fields through `fms.site.preferences` the same way GL account fields are. The split between the two systems is the bug.

**Q9. Residual allocation — greedy or proportional?**
Keep greedy. Matches station workflow. Proportional adds rounding complexity for no operational benefit.

**Q10. Immutable logs — how to handle corrections?**
Correction journal only. Never touch raw log. Override log entry records the correction. RTT wizard must drop the SQL update.

**Q11. Gate 9 (receipts vs invoiced) — fix or remove?**
Fix. Change domain: filter invoices by date within shift window only, or compare to total AR balance. The intent is valid.

**Q12. `fms.pump.name` UNIQUE — scope to company?**
NEEDS BUSINESS DECISION. Single-site: global unique fine. Multi-site: add `company_id` + `UNIQUE(name, company_id)`.

**Q13. PTS integration — continue or drop for MVP?**
Add 9 missing fields without implementing full matching logic. Models exist, protocol understood. Add fields now; complete matching in Phase 2.

**Q14. `delivery_qty` in dip log — populate or remove?**
Populate. It drives the shift variance formula. Stations receiving deliveries will show all delivered volume as unexplained loss if not populated.

**Q15. FC variance writeoff — which journal?**
Require non-null `default_account_id` on the writeoff journal, or use `fms_clearing_account_id` explicitly on both lines with correct debit/credit. Remove the `or writeoff_account` fallback.

**Q16. Gate 3 skip for non-POS stations — keep or fix?**
Fix. Gate 3 must check `attendant_cash_ids` directly. Remove POS session dependency from gate logic.

**Q17. `_compute_from_pos` name-based payment lookup — fix?**
Fix. Add `fms_payment_type` selection field to `pos.payment.method`. Filter on that field, not `name ilike 'mpesa'`.

**Q18. `information_schema` query — replace with what?**
```python
has_payment_fms = 'fms_shift_id' in self.env['account.payment']._fields
```
Pure Python, O(1), no DB round-trip. Three lines replace the 15-line SQL block.

**Q19. `fms.shift` god class — break up now or later?**
Later. Break into mixins after bugs fixed and tests cover behavior. Don't refactor while broken.

**Q20. Native Odoo reconciliation vs custom FC Cash gate?**
Keep custom Gate 1. Odoo reconciliation is payment-against-invoice. FC Cash is cash-in-hand count. Different concepts.

**Q21. `fms.shift.product.sales` — computed or stored?**
Computed is fine. Fix the N+1 in `_compute_accounted` with `read_group`. Keep computed.

**Q22. Override log — sufficient?**
Yes. Add: correction wizard must write an override log entry when it runs, not modify raw meter log.

**Q23. Meniscus default (1000L) — bug or config?**
LIKELY BUG. Change default to 50.0 or make percentage-based. Needs business confirmation of acceptable tolerance.

**Q24. `fms_revenue_account_id` — should it be `required=True`?**
Yes. Add required constraint on fuel products, or add pre-close gate that verifies all active nozzle products have revenue accounts configured.

---

## PART 20 — Priority Matrix

### CRITICAL — Fix before first production close

| # | Finding | Impact | Fix | Files |
|---|---------|--------|-----|-------|
| C1 | AVCO double-count: quant sync before consumption | Wrong COGS, wrong inventory — permanent | Fix close sequence: consumption move first, then quant sync for variance only | `fms_shift.py` |
| C2 | Revenue duplication: FMS + POS both post to revenue | Double revenue in GL, wrong P&L | Choose FMS-primary or POS-primary; disable the other path | `fms_shift.py`, `fms_shift_entry.py` |
| C3 | FC variance writeoff self-cancels | Variance never written off; shift cannot close cleanly | Fix both lines to use explicit accounts with correct debit/credit | `fms_shift.py` |
| C4 | Gate 9 blocks cross-shift payments | Legitimate receipts prevent shift close | Fix domain: compare shift-window invoices only | `fms_shift.py` |
| C5 | Clearing account domain: `asset_receivable` | Corrupts AR aging | Change to `asset_current` in `fms_site_preferences.py:74` | `fms_site_preferences.py` |
| C6 | RTT correction wizard bypasses immutable log via SQL | EPRA non-compliance; audit trail corrupted | Remove SQL update; correction journal is sufficient | `fms_shift_correction_wizard.py` |
| C7 | `delivery_qty` never populated in dip log | Shift variance wrong for any shift with delivery | Populate in `_create_dip_log` from delivery records | `fms_shift_entry.py` |

### HIGH — Fix before UAT

| # | Finding | Impact | Fix |
|---|---------|--------|-----|
| H1 | Config thresholds disconnected from gates | Operator configures meniscus, gates ignore it | Proxy threshold fields through `fms.site.preferences` |
| H2 | Gate 3 skips when no POS sessions | Non-POS attendant balances unchecked | Rewrite gate to iterate `attendant_cash_ids` directly |
| H3 | Products without revenue accounts silently skipped | Missing GL lines; revenue understated | Add required constraint or pre-close validation gate |
| H4 | `information_schema` query on every compute | 3 synchronous schema queries per page load | Replace with `'field' in model._fields` |
| H5 | Closed shifts allow non-state field edits | Data integrity broken | Extend `write()` protection to all fields when `state == 'closed'` |
| H6 | M-Pesa/card clearing account never reconciled | Growing unreconcilable balance | Define and implement settlement path |

### MEDIUM — Fix in first sprint after go-live

| # | Finding | Impact | Fix |
|---|---------|--------|-----|
| M1 | PTS fields missing on 3 models | PTS matching always fails with AttributeError | Add 9 missing fields |
| M2 | Name-based M-Pesa/card payment lookup | Breaks on rename or translation | Add `fms_payment_type` to `pos.payment.method` |
| M3 | Meniscus default 1000L | Gate 7 effectively disabled | Change default to 50.0 or make percentage-based |
| M4 | N+1 in `_compute_accounted` | Performance on large shifts | Rewrite with `read_group` |
| M5 | `fms_accounting` not declared as dependency | Upgrade race condition | Add to `__manifest__.py` depends |

### LOW — Phase 2

| # | Finding | Fix |
|---|---------|-----|
| L1 | `fms.pump` UNIQUE not scoped to company | Add `company_id` + `UNIQUE(name, company_id)` |
| L2 | God class `fms_shift.py` 2762 lines | Extract mixins after bugs fixed |
| L3 | Month variance never posted to GL | Add `_post_month_variance_journal` |
| L4 | `variance_pct` legacy field formula incorrect | Fix or remove |

---

## Bottom Line

1. **Foundation is viable.** Core data model (shift → meter entry → dip entry → attendant cash) correctly captures the forecourt workflow. Not a rewrite candidate.

2. **Three bugs will cause financial losses on day one:** revenue duplication (C2), AVCO double-count (C1), and FC variance writeoff self-cancel (C3). Fix before any production use.

3. **Two bugs are operational blockers:** Gate 9 (C4) and FC variance writeoff (C3). Station cannot close shifts on normal business days with cross-shift AR customers.

4. **EPRA compliance broken.** RTT correction wizard (C6) directly modifies the immutable meter log via raw SQL. An EPRA auditor examining the log will see incorrect raw readings with no audit trail of the change.

5. **Config UI is half-wired.** GL account fields correctly sync. Threshold fields (meniscus, variance limits) do not. Operator changes in settings UI silently have no effect on gate behavior.

6. **PTS integration is scaffolding, not working code.** Do not ship it as "integrated" — ship it as "ready for integration pending field additions."

7. **The accounting module dependency is a ticking time bomb.** A module upgrade that runs before `fms_accounting` will silently lose all payment/expense reconciliation for that shift.

8. **Preserve:** shift state machine (correct), residual allocation algorithm (correct), immutable log design (correct intent, broken by wizard), hard gate concept (correct, two gates have implementation bugs).

9. **Redesign:** the close sequence (quant sync + consumption move order), the config settings proxy pattern (extend to all fields), Gate 3 (remove POS dependency), Gate 9 (fix invoice domain).

10. **Delete:** the SQL `UPDATE` in the RTT correction wizard. The journal entry it posts is correct and sufficient.

11. **Use native Odoo:** `account.move` for all GL (already done), `stock.quant.action_apply_inventory()` for physical counts only (not as part of shift close revenue path), `hr.expense` for attendant expenses (already done).

12. **Use OCA if available:** `account_move_template` for repeatable journal entry patterns — reduces the 200-line `_post_sales_journal` to template instantiation.

13. **Remain custom:** shift orchestration, hard gates, residual allocation, meter/dip log immutability, EPRA audit trail format.

14. **Fix first (Phase 0, one day of work):** C1, C3, C5, C6 — all are 1–10 line changes with no schema migration. C2 requires a business decision first. C4 requires domain fix. C7 requires populating one dict.

15. **Architecture worth continuing.** The decision to build on Odoo 18 (native accounting, native stock, native POS) instead of a parallel system is correct. The bugs are implementation errors, not architectural ones. Fix the close sequence, fix the gate logic, fix the config proxy gap — the rest is production-grade.
