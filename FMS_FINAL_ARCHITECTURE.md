# FMS Final Architecture Decision Document

**Date:** 2026-09-13  
**Author:** Architecture Review — Claude Code  
**Scope:** Odoo 18 Community FMS module, full forensic + decision pass  
**Status:** DEFINITIVE — supersedes FMS_AUDIT_REPORT.md and FMS_ADVERSARIAL_VALIDATION.md  

---

## Section 1 — Repository Inventory

Files read in full:

| File | Lines | Role |
|---|---|---|
| `__manifest__.py` | ~50 | Module definition |
| `models/fms_shift.py` | 2762 | God class — shift orchestration |
| `models/fms_shift_entry.py` | 914 | Meter/dip entries, attendant cash |
| `models/fms_shift_reconciliation.py` | ~400 | Product sales, residual allocations |
| `models/fms_shift_cash_movement.py` | ~200 | Float/drop auto-payments |
| `models/fms_shift_fc_line.py` | ~150 | Non-fuel goods/service lines |
| `models/fms_site_preferences.py` | ~300 | Site config, GL references |
| `models/fms_config_settings.py` | ~200 | Odoo Settings UI proxy |
| `models/fms_pump.py` | 186 | Pump/nozzle master data |
| `models/fms_pts.py` | 245 | PTS-2 device + transaction |
| `models/fms_logs.py` | ~180 | Immutable meter/dip logs |
| `models/fms_incident.py` | ~120 | Drive-off register |
| `models/fms_price_period.py` | ~80 | EPRA price periods |
| `wizards/fms_shift_correction_wizard.py` | ~250 | RTT correction |
| `security/fms_groups.xml` | ~60 | 3-group hierarchy |
| `security/ir_rule.xml` | ~120 | Record rules |

Native Odoo 18 models relevant to FMS:
- `account.move` / `account.move.line` — GL journal entries
- `account.payment` — cash/bank payments
- `stock.move` / `stock.quant` / `stock.valuation.layer` — inventory + AVCO
- `pos.order` / `pos.session` — POS sales
- `hr.expense` — attendant expense claims
- `hr.employee` — attendant master

---

## Section 2 — Verification of Previous Audit Findings

### CONFIRMED BUGS

**BUG-01: AVCO double-count (sequence reversal)**  
Evidence: `fms_shift.py` close sequence lines 1444–1455.  
`_sync_stock_quant_from_dips()` runs BEFORE `_post_stock_consumption()`.  
`action_apply_inventory()` creates an inventory adjustment valuation layer for full (opening − closing) before the consumption move creates its own layer.  
Net result: ~2× COGS posted. Stock quantity ends 1 consumption-worth below physical dip.  
Severity: CRITICAL — P&L and stock ledger wrong every shift.

**BUG-02: FC variance writeoff self-cancels**  
Evidence: `action_writeoff_fc_variance` lines 425–488.  
`clearing_account = journal.default_account_id or writeoff_account`  
When journal has no `default_account_id`, both debit and credit sides use `writeoff_account`. Net zero. Variance remains uncleared.  
Mitigated by: shift now requires `fc_writeoff_account_id` — but journal fallback path remains live.  
Severity: HIGH.

**BUG-03: Gate 5 skips non-POS stations**  
Evidence: `fms_shift.py` lines 1750–1766.  
`if not self.pos_session_ids: return`  
Attendant balance check skipped entirely at stations without POS.  
Severity: HIGH — core hard gate silently disabled for non-POS deployments.

**BUG-04: Gate 9 cross-shift payment failure**  
Evidence: lines 2183–2215.  
Compares THIS shift's receipts against THIS shift's invoices only.  
Customer paying a prior-shift invoice triggers ValidationError.  
Severity: MEDIUM — operational disruption, valid payments blocked.

**BUG-05: RTT correction SQL bypass**  
Evidence: `fms_shift_correction_wizard.py` lines 210–216.  
`env.cr.execute("UPDATE fms_meter_log SET rtt_volume = ...")`  
Bypasses ORM `write()` guard on immutable log.  
Journal entry (DR Revenue | CR Clearing) is correct.  
SQL update is non-compliant with EPRA immutability requirement.  
Severity: HIGH — EPRA audit failure risk.

**BUG-06: delivery_qty never populated in dip log**  
Evidence: `fms_shift_entry.py` `_create_dip_log` lines 303–326.  
`delivery_qty` field exists on `fms.dip_log` but neither dict in `_create_dip_log` includes it.  
Wetstock variance formula silently treats deliveries as phantom losses.  
Severity: HIGH — variance calculations wrong on delivery days.

**BUG-07: clearing_account_id domain wrong type**  
Evidence: `fms_site_preferences.py` line 74.  
`domain=[('account_type', '=', 'asset_receivable')]`  
`asset_receivable` is Odoo's AR type — Odoo partner reconciliation targets this type for customer invoice matching. Using it for a cash clearing account corrupts AR aging reports.  
Correct type: `asset_current` (or `asset_cash` if restricted to bank/cash accounts).  
Severity: HIGH — accounting integrity.

**BUG-08: meniscus default wrong unit**  
Evidence: `fms_site_preferences.py`.  
`default_dip_variance_meniscus = fields.Float(default=1000.0)`  
Spec says 0.5% of tank capacity (e.g. 50L for 10,000L tank).  
1000L default passes gate for virtually any real variance.  
Severity: MEDIUM — gate effectively disabled at default.

### CONFIRMED ARCHITECTURAL PROBLEMS

**ARCH-01: fms_accounting not declared as dependency**  
Evidence: `__manifest__.py` — no `fms_accounting` in `depends`.  
`fms_shift_entry.py` uses `information_schema` SQL to detect presence of `fms_shift_id` columns at runtime.  
Module upgrade ordering not guaranteed.  
Fix: either declare dependency, or make FMS self-contained and move those field definitions in.

**ARCH-02: Config settings threshold fields disconnected from gates**  
Evidence: `fms_config_settings.py` — threshold fields use `config_parameter='fms.xxx'` (stored in `ir.config_parameter`).  
Gates read from `prefs.elec_vs_cash_threshold_l` and `prefs.default_dip_variance_meniscus` (site.prefs model fields, different storage).  
Changes via Settings UI have zero effect on gate behavior.  
Severity: HIGH — operators believe they are configuring gates; they are not.

**ARCH-03: PTS integration references non-existent fields**  
Evidence: `fms_pts.py` `_try_match_shift` lines 196–233.  
Searches for `fms.pump.pts_device_id` — field does not exist on `fms.pump`.  
Searches for `fms.pump.pts_pump_number` — does not exist.  
Filters `nozzle.pts_nozzle_number` — does not exist on `fms.pump.nozzle`.  
Writes `pts_transaction_id`, `pts_volume`, `pts_tc_volume`, `closing_totalizer` to meter entry — none exist on `fms.shift.meter.entry`.  
PTS matching is completely broken. Cannot link any transaction to a shift.

**ARCH-04: information_schema queries in compute methods**  
Evidence: `fms_shift_entry.py` `_compute_fc_variance` lines 483–596 and `_compute_from_payments` lines 753–849.  
`information_schema.columns` query runs in a stored compute — fires on every read, on every attendant record, on every shift load.  
Schema does not change at runtime. Cost: ~1ms per query × every compute = significant on list views.

**ARCH-05: Revenue duplication when POS sessions present**  
`_post_sales_journal` posts DR Clearing | CR Revenue using `elec_cash_sold`.  
POS session close already posted revenue for each order via standard Odoo POS accounting.  
If POS sessions linked to shift and POS journal targets revenue accounts, revenue is double-posted.  
Decision required — see Section 3.

**ARCH-06: fms.pump missing company_id**  
`fms.pump` has no `company_id` field.  
Multi-company deployment: pumps not scoped to company. All companies share pump list.

### PREVIOUS AUDIT CORRECTIONS

| Prior Finding | Correction |
|---|---|
| "Gate 14 fully redundant" | NOT redundant — meaningful when shift re-enters from 'disputed' state via emergency override path |
| "Config GL fields entirely disconnected" | GL fields ARE correctly proxied through site.prefs via compute/inverse. Only threshold fields are disconnected. |
| "Dip log delivery bypass has no auth check" | Supervisor group check IS present in `fms.dip_log.write()` |
| "AVCO unit cost wrong" | Unit cost (ratio) stays correct. Total value and quantity wrong. |
| "Opening readings require manual re-entry" | `_populate_opening_entries()` confirms auto-population from previous shift's logs |

---

## Section 3 — Revenue Ownership Decision

### The 9 Payment Scenarios

| # | Scenario | POS Posts Revenue? | FMS Posts Revenue? | Problem |
|---|---|---|---|---|
| 1 | Cash sale, POS present | Yes — pos.order close | Yes — `_post_sales_journal` | DOUBLE |
| 2 | Cash sale, no POS | No | Yes | Correct |
| 3 | MPesa sale, POS present | Yes | Yes | DOUBLE |
| 4 | MPesa sale, no POS | No | Yes | Correct |
| 5 | Credit/AR sale, POS | Yes (deferred) | Yes | DOUBLE |
| 6 | Credit/AR sale, no POS | No | Yes | Correct |
| 7 | Card sale, POS | Yes | Yes | DOUBLE |
| 8 | Card sale, no POS | No | Yes | Correct |
| 9 | Drive-off (incident) | No | No (stock only) | Correct |

Scenarios 1, 3, 5, 7 currently double-post revenue when POS sessions are linked.

### Decision: FMS-PRIMARY

**FMS owns revenue recognition for fuel sales.** POS journal for fuel products must be configured to post to the Cash Clearing account (not revenue accounts) so POS acts as payment capture only.

Rationale:
- FMS has three-meter-validated volume. POS does not.
- FMS applies residual allocation corrections. POS cannot.
- FMS is where EPRA-mandated shift reconciliation happens.
- POS data is source of payment method breakdown, not revenue amount.

Implementation required:
1. Fuel product POS category must use clearing journal for income account.
2. FMS `_post_sales_journal` remains authoritative.
3. Gate 4 (cash meter vs POS revenue) validates POS total against FMS clearing balance — works correctly under FMS-primary.

---

## Section 4 — Complete Accounting Flow Table

All transaction types, debit/credit accounts, models used.

| # | Transaction | DR | CR | Model |
|---|---|---|---|---|
| 1 | Fuel cash sale | Cash Clearing | Fuel Revenue | account.move (FMS) |
| 2 | Fuel MPesa sale | MPesa Clearing | Fuel Revenue | account.move (FMS) |
| 3 | Fuel card sale | Card Clearing | Fuel Revenue | account.move (FMS) |
| 4 | Fuel credit sale | AR — Customer | Fuel Revenue | account.move (FMS) |
| 5 | Customer AR receipt | Cash/MPesa | AR — Customer | account.payment |
| 6 | Non-fuel cash sale | Cash Clearing | Non-fuel Revenue | account.move (FMS) |
| 7 | Residual reallocation | Diesel COGS | Carwash COGS | account.move (FMS) |
| 8 | Stock consumption | COGS | Inventory Asset | stock.valuation.layer |
| 9 | Dip variance adjustment | COGS (shortage) | Inventory Asset | stock.valuation.layer |
| 10 | Fuel delivery (purchase) | Inventory Asset | AP — Supplier | account.move (purchase) |
| 11 | Attendant float issued | Attendant Float Clearing | Safe/Cash | account.payment |
| 12 | Cash drop received | Safe/Cash | Attendant Float Clearing | account.payment |
| 13 | FC cash variance writeoff | Cash Clearing | Variance Expense | account.move (FMS) |
| 14 | Attendant expense | Expense Account | Cash Clearing | hr.expense + account.move |
| 15 | Drive-off stock write-off | Incident Loss | Inventory Asset | stock.move |
| 16 | Drive-off revenue reversal | Fuel Revenue | Cash Clearing | account.move (FMS) |
| 17 | Price period adjustment | COGS | Inventory (AVCO adj) | account.move (FMS) |
| 18 | RTT correction | Fuel Revenue | Cash Clearing | account.move (wizard) |
| 19 | Vendor payment | AP — Supplier | Cash/Bank | account.payment |
| 20 | POS fuel payment capture | Cash Clearing | Cash Clearing (transit) | pos.order — fuel category |
| 21 | Shift disputed — reversal | Reverse all shift entries | Reverse all shift entries | account.move (FMS reverse) |
| 22 | Opening bank deposit | Bank | Cash Clearing | account.payment |
| 23 | Carwash service sale | Cash Clearing | Carwash Revenue | account.move (FMS) |
| 24 | LPG sale | Cash Clearing | LPG Revenue | account.move (FMS) |
| 25 | Tax payable (VAT-inclusive) | Revenue (gross) | Tax Payable + Revenue (net) | account.move tax lines |

---

## Section 5 — Clearing Account Semantics

**Name:** Cash Clearing / Forecourt Cash Clearing  
**Meaning:** Cash physically collected at forecourt, not yet banked.  
**Nature:** Current asset (transit cash). NOT accounts receivable.  
**Correct Odoo account type:** `asset_current`

The account is debited when fuel is sold (cash received at forecourt).  
The account is credited when:  
- Cash is deposited to bank (DR Bank | CR Clearing)  
- FC variance is written off (DR Clearing | CR Variance)  

Using `asset_receivable` (current bug) causes:  
- Odoo partner reconciliation logic treats balance as customer AR
- Appears in AR aging reports under a phantom customer
- Auto-reconcile wizard attempts to match against customer invoices
- Corrupts Days Sales Outstanding metrics

Fix: change `domain=[('account_type', '=', 'asset_receivable')]` to `domain=[('account_type', 'in', ['asset_current', 'asset_cash'])]`

---

## Section 6 — Credit / AR Sales Architecture

**Scenario:** Fleet account (e.g. KenTruck) fills 500L Diesel on credit.

Flow:
1. Attendant records sale on shift — marks as AR/credit
2. FMS `_post_sales_journal` posts: DR AR-Customer | CR Diesel Revenue
3. `fms.shift.attendant.cash._compute_balance` includes `ar_amount` in `total_out`
4. Attendant's FC cash balance = 0 (credit sales don't require cash)
5. Customer receives invoice (standard `account.move` out_invoice)
6. Customer pays later — `account.payment` created with `fms_shift_id` = current shift at time of payment
7. Gate 9 checks: payments in THIS shift ≤ invoices in THIS shift

Gate 9 bug (BUG-04): cross-shift payments fail because the invoice may belong to a prior shift.  
Fix: Gate 9 should check payments ≤ total open AR for the customer, not shift-scoped.

---

## Section 7 — Payment Source of Truth

| Payment Method | Source of Truth | Reconciliation Point |
|---|---|---|
| Cash | Attendant physical count (`cash_collected`) | FC cash balance = 0 (Gate 6) |
| MPesa | M-Pesa statement from telco | Gate 13 (digital payment sign check) |
| Card | POS terminal report | Gate 13 |
| Credit/AR | Customer invoice + account.payment | Gate 9 |
| Fuel float | `fms.shift.cash.movement` | Gate 10 |
| Expense | `hr.expense` linked to shift | Gate 11 |
| Vendor payment | `account.payment` linked to shift | Gate 12 |

MPesa and card lookup: `fms_shift_entry.py` `_compute_from_pos` uses `PayMethod.search([('name', 'ilike', 'mpesa')])` — fragile name match. Production risk if payment method renamed.  
Recommendation: add `fms_payment_type` Selection field to `pos.payment.method` (in fms_accounting) — tag methods explicitly rather than name-matching.

---

## Section 8 — Wetstock / Inventory Architecture

**Three data sources per tank per shift:**

1. **Opening dip** — physical tank gauge at shift start (L)  
2. **Delivery** — fuel received during shift from `fms_fuel_delivery_line` (L)  
3. **Meter sales** — volume dispensed per nozzle from meter entries (L)  
4. **Closing dip** — physical tank gauge at shift end (L)

**Correct variance formula:**  
`shift_variance = closing_dip − (opening_dip + delivery − meter_sales)`

- Positive variance: more fuel in tank than expected (evaporation recovery, gauge error)
- Negative variance: less fuel in tank than expected (evaporation, leak, theft)
- Acceptable range: ±meniscus threshold (currently defaulting to 1000L — BUG-08)

**Current flow (broken):**

```
_sync_stock_quant_from_dips()   # sets quant to closing_dip → adjustment = -(opening - closing)
_post_stock_consumption()       # creates consumption move for meter_sales
```

Result: COGS = (opening − closing) + meter_sales. Double-counts meter_sales as loss.

**Correct flow:**

```
_post_stock_consumption()       # consumption move for meter_sales → COGS
_sync_stock_quant_from_dips()   # quant sync for residual variance only → COGS or gain
```

After fix: COGS = meter_sales + variance_adjustment. Matches physical reality.

---

## Section 9 — Delivery Architecture

Deliveries modeled in `fms_accounting` module via `fms.fuel.delivery` and `fms.fuel.delivery.line`.  
`_compute_dip_variance_data` uses `to_regclass('fms_fuel_delivery_line')` to detect if table exists — graceful degradation when fms_accounting not installed.

BUG-06: `_create_dip_log` never writes `delivery_qty` to dip log. The correct delivery quantity is computed in `_compute_dip_variance_data` but not persisted.

Fix: in `_create_dip_log`, fetch delivery from `fms_fuel_delivery_line` (same query used in variance compute) and include in `vals` dict.

Delivery GL (not in FMS module — standard Odoo purchase):  
`DR Inventory Asset | CR AP Supplier`

---

## Section 10 — AVCO / Stock Valuation

Odoo 18 AVCO mechanism:
- Each `stock.move` in creates a `stock.valuation.layer` at current AVCO
- `action_apply_inventory()` on `stock.quant` creates an inventory adjustment valuation layer
- AVCO unit cost = total_value / total_quantity at time of move

**Double-count numerical proof:**

Assumptions: opening book stock = 10,000L, AVCO = KES 180/L, meter_sales = 200L, closing_dip = 9,750L

Expected result: COGS = 200L × 180 = KES 36,000. Variance = 9,750 − (10,000 + 0 − 200) = −50L.

Current broken sequence:
1. `_sync_stock_quant_from_dips`: sets quant to 9,750L. System sees current quant = 10,000L → adjustment = −250L. Layer: −250L × 180 = KES 45,000 COGS.
2. `_post_stock_consumption`: consumption move −200L × 180 = KES 36,000 COGS.
3. Final quant after consumption: 9,750 − 200 = 9,550L (200L below physical).
4. Total COGS: KES 81,000. Correct COGS: KES 36,000 + 9,000 (variance) = KES 45,000.

Correct sequence:
1. `_post_stock_consumption`: −200L × 180 = KES 36,000. Quant = 9,800L.
2. `_sync_stock_quant_from_dips`: sets quant to 9,750L. Adjustment = −50L × 180 = KES 9,000. Quant = 9,750L.
3. Total COGS: KES 45,000. Stock = 9,750L. Matches dip.

---

## Section 11 — Shift Architecture and All Gates

**Shift states:** draft → open → closing → closed | disputed

**State transitions:**
- `draft → open`: `action_open()` — populates opening meter/dip entries from prior shift logs
- `open → closing`: `action_start_close()` — supervisor initiates, triggers all gate checks
- `closing → closed`: `action_close()` — passes all 15 gates, writes logs, posts GL
- `closed → disputed`: `action_dispute()` — supervisor override, reopens for correction
- `disputed → closed`: re-run close sequence after corrections

**All 15 Gates:**

| Gate | Check | Skip Condition | Severity |
|---|---|---|---|
| G1 | Elec meter vs manual meter (±1L/nozzle) | None | HARD |
| G2 | Elec meter vs cash meter (configurable L threshold) | None | HARD |
| G3 | Volume reconciliation: meter vs POS | `require_pos_reconciliation` = False OR no pos_session_ids | HARD |
| G4 | Cash reconciliation: cash meter vs POS revenue (±100) | No POS sessions | HARD |
| G5 | Attendant balance = 0 each | `not self.pos_session_ids` (BUG-03) | HARD |
| G6 | FC cash = 0 (after writeoff) | None | HARD |
| G7 | Stock dip variance ≤ meniscus | None | HARD |
| G8 | Meter sales vs invoices + receipts | No POS sessions | HARD |
| G9 | Customer receipts ≤ invoiced | None | HARD (BUG-04) |
| G10 | Float reconciliation (all floats accounted) | None | HARD |
| G11 | No draft expenses | None | HARD |
| G12 | No draft vendor payments | None | HARD |
| G13 | Digital payment sign (MPesa/card ≥ 0) | None | SOFT (sign only) |
| G14 | No unresolved exceptions (state != disputed) | None | HARD |
| G15 | All non-fuel sales posted | None | HARD |

G5 bug makes it functionally SOFT at non-POS stations.

---

## Section 12 — Shift Close Target: 10-Minute Close

**Operations at shift close (measured against 10-min target):**

| Step | Operation | Estimated Time |
|---|---|---|
| 1 | Enter closing meter readings | 2–3 min |
| 2 | Enter closing dip readings | 1 min |
| 3 | Enter cash count | 1 min |
| 4 | System: run 15 gates | <5 sec |
| 5 | System: write_meter_logs, write_dip_logs | <2 sec |
| 6 | System: _post_stock_consumption | <3 sec |
| 7 | System: _sync_stock_quant_from_dips | <3 sec |
| 8 | System: _post_sales_journal | <5 sec |
| 9 | System: _auto_open_next_shift | <2 sec |
| **Total** | | **~5–7 min (nominal)** |

Bottleneck risks:
- `information_schema` queries in compute fields fire on every form load during data entry
- N+1 in `_compute_accounted` (one POS search per product line)
- Large POS session: `pos.order` search scans entire session order set

10-min target is achievable IF:
1. BUG-01 (AVCO sequence) fixed — current sequence causes inconsistent stock state post-close, requiring manual correction
2. `information_schema` queries replaced with cached `_fields` checks
3. `_compute_accounted` N+1 replaced with single aggregated query

---

## Section 13 — Cash Architecture

**FC Cash system:**

`fc_cash_balance = fc_captured − fc_collected`

Where:
- `fc_captured` = sum of all cash meter readings (what pumps recorded as cash)
- `fc_collected` = cash physically handed in by all attendants

**For balance = 0:**
- Every shilling captured by pump must be physically counted in
- Or written off via `action_writeoff_fc_variance` (supervisor action, requires fc_writeoff_account_id)

**Cash movement flow:**
1. Shift opens: supervisor issues float — `fms.shift.cash.movement` (type=float) → `account.payment` (DR Attendant | CR Safe)
2. Attendant collects cash during shift
3. Attendant submits cash drop — `fms.shift.cash.movement` (type=drop) → `account.payment` (DR Safe | CR Attendant)
4. Shift close: `cash_collected` vs `fc_captured` → if delta, writeoff

Gate 6 requires exact zero AFTER writeoff. Supervisor must decide: accept loss (writeoff to variance expense) or investigate.

---

## Section 14 — Non-Fuel Sales Boundary

Non-fuel sold via `fms.shift.fc.line` per attendant:
- Goods: `opening_qty + delivery_qty − closing_qty = qty_sold`
- Services (carwash, LPG cylinder exchange): direct amount entry
- Each line has product_id with its own revenue account

GL: `DR Cash Clearing | CR [product revenue account]`

Non-fuel vs fuel boundary:
- Fuel: metered (three-meter system), tracked via `fms.shift.meter.entry`
- Non-fuel: counted (stock count method), tracked via `fms.shift.fc.line`
- Residual allocation bridges the gap when attendant lumps non-fuel into fuel meter reading

POS can capture non-fuel sales in real time. If so, `_compute_from_pos` already separates non-fuel POS lines from fuel lines. FMS `_post_sales_journal` should NOT re-post non-fuel if POS already did.  
Current code: `_post_sales_journal` posts all `fc_line_ids`. If POS also posted, double-posting.  
Decision needed: non-fuel sales — FMS-primary or POS-primary.  
Recommendation: POS-primary for non-fuel (POS captures in real time, better UX), FMS posts only fuel.

---

## Section 15 — Refunds, Voids, Reversals

**Void before shift close (same shift):**
- Meter entry: reduce closing reading to exclude voided sale
- No GL entry yet — `_post_sales_journal` not yet run
- POS void: standard Odoo POS void flow, removes from pos.order
- No FMS-specific void mechanism exists currently

**Refund after shift close:**
- Standard Odoo credit note: `account.move` type=out_refund
- Stock reverse move: `stock.move` from customer back to stock
- FMS logs immutable — no reversal of `fms.meter_log` — RTT wizard handles meter correction
- Cash refund: `account.payment` against credit note

**Shift reversal (disputed):**
- `action_dispute()` moves shift to disputed state
- Does NOT auto-reverse GL entries (gap — should reverse via `move.button_draft()` + `move.button_cancel()`)
- RTT correction wizard handles revenue adjustment post-close
- Supervisor must manually reverse GL if full shift reversal needed

Gap: no automated GL reversal on dispute. Recommend: `action_dispute()` should call `sales_journal_entry_id.button_cancel()` if entry posted.

---

## Section 16 — Variance / Shortage / Overage

**Meter variance (G1):** elec_volume vs mech_volume per nozzle. >±1L = gate fail. Suggests pump calibration error or tampering.

**Cash meter variance (G2):** elec_cash vs elec_volume × price. Threshold configurable (stored in site.prefs — see ARCH-02 for config disconnect bug).

**FC cash variance (G6):** fc_captured − fc_collected. Unresolved = shift cannot close. Options:
1. Writeoff to variance expense (accepted loss)
2. Investigate (attendant owes cash)

**Dip variance (G7):** physical_closing − expected_closing. Meniscus default 1000L (BUG-08). Should be 0.5% of tank capacity.

**Disposition of variances:**
- Meter variance: supervisor investigates pump calibration
- Cash variance: supervisor decides — writeoff or recovery from attendant
- Dip variance (within meniscus): normal — posted as GL adjustment (DR/CR COGS)
- Dip variance (outside meniscus): gate fail — supervisor posts explanation or adjustment

---

## Section 17 — RTT / Manual Corrections

**RTT (Road Tanker Time) correction:** adjusts meter readings retroactively for refueling truck fill that crossed shift boundary.

Current architecture:
1. Wizard creates correct journal: DR Revenue | CR Clearing (correct)
2. Wizard updates `fms.meter_log` via raw SQL (incorrect — EPRA violation)

Fix architecture:
1. Keep journal entry (correct)
2. Replace SQL update with: create NEW `fms.meter_log` record with `correction_of_id = original_log.id` and negative delta volume
3. Report view sums original + correction — net volume correct
4. Original record immutable — audit trail preserved
5. `fms.meter_log` needs: `correction_of_id = fields.Many2one('fms.meter_log', 'Corrects')` and `rtt_correction_volume = fields.Float`

This pattern is EPRA-compliant: immutable original + explicit correction record.

---

## Section 18 — Security / Data Integrity

**Group hierarchy:** Attendant ⊂ Supervisor ⊂ Accountant

**Record rule coverage:**
- `fms.shift`: company-scoped for attendant and supervisor
- `fms.shift.meter.entry`: attendants write only on open shifts in own company
- `fms.shift.attendant.cash`: attendants see only own row
- `fms.meter_log` / `fms.dip_log`: attendants read-only

**Gaps:**
1. `fms.pump` has no company_id — not multi-company safe
2. `fms.shift.write()` protects state changes on closed shifts but not field changes — non-state fields on closed shifts writable by anyone with write access
3. RTT SQL bypass circumvents all record rules and ORM guards (BUG-05)
4. `fms.shift.cash.movement` creates `account.payment` via `sudo()` — bypasses payment access rights

**Recommendations:**
1. Add `company_id` to `fms.pump` with record rule
2. Strengthen `write()` protection: if shift is closed, block ALL field writes except those in whitelist (`dispute_note`, `state` transition back to disputed)
3. RTT: replace SQL with correction record pattern (Section 17)
4. Cash movement: payment creation should use `self.env` (not sudo) and require Supervisor group

---

## Section 19 — Configuration Architecture

**Current state — three disconnected config surfaces:**

1. **`fms.site.preferences`** (DB model, company-specific)
   - GL accounts (clearing, writeoff)
   - Threshold fields (`elec_vs_cash_threshold_l`, `default_dip_variance_meniscus`)
   - POS integration flags
   - Pre-assigned attendant mode

2. **`fms.config.settings`** (Odoo Settings UI)
   - GL fields: correctly proxied to site.prefs via compute/inverse ✓
   - Threshold fields: stored in `ir.config_parameter` — NOT read by gates ✗

3. **`ir.config_parameter`** (key-value store)
   - Threshold values written by Settings UI
   - Read by: nobody (gates use site.prefs)

**Fix:** Remove threshold fields from `fms_config_settings.py`. Settings UI should proxy threshold fields to site.prefs same as GL fields.

**Target configuration architecture:**

Single source of truth: `fms.site.preferences` for all FMS config.  
`fms.config.settings` = UI-only proxy (compute/inverse pattern for all fields).  
No config stored in `ir.config_parameter` for fields that gates read.

---

## Section 20 — PTS-2 Future Integration Design

**Current state:** scaffolding exists, matching broken (ARCH-03).

**Missing fields to add:**

On `fms.pump`:
```python
pts_device_id   = fields.Many2one('fms.pts.device', 'PTS Device')
pts_pump_number = fields.Integer('PTS Pump Number')
```

On `fms.pump.nozzle`:
```python
pts_nozzle_number = fields.Integer('PTS Nozzle Number')
```

On `fms.shift.meter.entry`:
```python
pts_transaction_id = fields.Many2one('fms.pts.transaction', 'PTS Transaction', readonly=True)
pts_volume         = fields.Float('PTS Volume (L)', digits=(16, 3), readonly=True)
pts_tc_volume      = fields.Float('PTS TC Volume (L)', digits=(16, 3), readonly=True)
closing_totalizer  = fields.Float('Closing Totalizer (L)', digits=(20, 3), readonly=True)
```

PTS shift state mapping:
- `fms_pts.py` line 185: `('state', 'in', ['open', 'in_progress', 'draft'])` — 'in_progress' is not a valid shift state. Valid states: draft, open, closing, closed, disputed. Remove 'in_progress'.

**PTS data flow (post-fix):**
1. PTS-2 controller pushes `UploadPumpTransaction` via WebSocket
2. `pts_bridge` service calls `fms.pts.transaction.create_from_pts()`
3. `_try_match_shift()` finds open shift, matches pump via `pts_device_id + pts_pump_number`
4. Matches nozzle via `pts_nozzle_number`
5. Finds meter entry for that nozzle in the shift
6. Writes PTS fields to meter entry (for comparison/validation)
7. Supervisor reviews any 'conflict' or 'raw' transactions before close

**PTS vs manual meter entry conflict resolution:**
- G1 extended: if PTS transaction linked, compare `pts_volume` vs `elec_volume − prev_totalizer`. Discrepancy = conflict.
- Supervisor can accept PTS reading or manual reading.

---

## Section 21 — Native Odoo vs Custom Model Decisions

| Domain | Use Native Odoo | Use Custom FMS |
|---|---|---|
| GL journal entries | `account.move` ✓ | Never |
| Payments (cash/bank) | `account.payment` ✓ | Never |
| Inventory moves | `stock.move` ✓ | Never |
| AVCO valuation | `stock.valuation.layer` ✓ | Never |
| Customer invoices | `account.move` (out_invoice) ✓ | Never |
| POS sales | `pos.order` ✓ | Never |
| Employee expenses | `hr.expense` ✓ | Never |
| Shift orchestration | — | `fms.shift` ✓ |
| Meter readings | — | `fms.shift.meter.entry` ✓ |
| Dip readings | — | `fms.shift.dip.entry` ✓ |
| Attendant cash | — | `fms.shift.attendant.cash` ✓ |
| Meter logs (audit) | — | `fms.meter_log` ✓ |
| Dip logs (audit) | — | `fms.dip_log` ✓ |
| Fuel deliveries | — | `fms.fuel.delivery` ✓ |
| Pump/nozzle master | — | `fms.pump` / `fms.pump.nozzle` ✓ |
| PTS device | — | `fms.pts.device` ✓ |
| PTS transactions | — | `fms.pts.transaction` ✓ |
| Price periods | — | `fms.price.period` ✓ |
| Incidents | — | `fms.incident` ✓ |

---

## Section 22 — FMS vs fms_accounting Boundary

**FMS core module (`fms`):**
- Shift lifecycle and orchestration
- Meter/dip entries and logs
- Attendant cash reconciliation
- Hard gates
- Pump/nozzle master
- PTS integration
- Site preferences
- Reports

**fms_accounting module (sibling, not declared in depends):**
- Extends `account.payment` with: `fms_shift_id`, `fms_attendant_id`, `fms_payment_context`
- Extends `account.move` with: `fms_shift_id`, `fms_attendant_id`
- Extends `hr.expense` with: `fms_shift_id`, `fms_attendant_id`
- Defines `fms.fuel.delivery` and `fms.fuel.delivery.line`
- Defines `fms.shift.cash.movement`

**Decision: merge fms_accounting into fms, OR declare explicit dependency.**

Merging is cleaner:
- Eliminates `information_schema` runtime detection
- Eliminates graceful-degradation complexity
- Single module to install, upgrade, test
- `fms.shift.cash.movement` is tightly coupled to shift close anyway

Splitting only makes sense if fms_accounting must be optionally installable. Given the FC cash gate requires payment tracking, fms_accounting is not truly optional.

**Recommendation: merge fms_accounting into fms.**

If merge not feasible immediately: declare `fms_accounting` in `__manifest__.py` `depends` and replace all `information_schema` checks with `'field' in model._fields`.

---

## Section 23 — fms_shift.py Decomposition

At 2762 lines, `fms_shift.py` is a god class. Recommended decomposition:

| New File | Content | Lines (est.) |
|---|---|---|
| `fms_shift.py` | Core model, fields, state machine, `action_*` buttons | ~600 |
| `fms_shift_gates.py` | All 15 gate methods (`_gate_*`) | ~500 |
| `fms_shift_close.py` | Close sequence: `_write_meter_logs`, `_write_dip_logs`, `_sync_stock_quant_from_dips`, `_post_stock_consumption` | ~400 |
| `fms_shift_journal.py` | `_post_sales_journal`, `_post_residual_allocations`, `action_writeoff_fc_variance` | ~400 |
| `fms_shift_compute.py` | All computed fields: `_compute_commercial_summary`, `_compute_dip_variance_data` | ~400 |
| `fms_shift_auto.py` | `_auto_open_next_shift`, `_populate_opening_entries` | ~200 |

Use Odoo mixin pattern — all inherit `fms.shift` and access `self` normally. Or use `_inherit` override files.

Decomposition is refactoring — no behavior change. Do in one commit per file move with full test pass.

---

## Section 24 — OCA Module Verification

Declared dependencies in `__manifest__.py`: `base, mail, account, stock, point_of_sale, hr, web_dark_mode, web_responsive`

`web_dark_mode` and `web_responsive` are OCA modules. Verify before deployment:
- https://github.com/OCA/web — `web_responsive` ✓ (Odoo 18 branch exists)
- `web_dark_mode` — verify Odoo 18 Community compatibility. Some versions are Enterprise-only or not yet ported.

Risk: if `web_dark_mode` not available for Odoo 18 Community, module install fails.  
Mitigation: mark as optional in manifest or remove dependency; dark mode is cosmetic, not functional.

No other OCA modules declared. `fms_accounting` not declared at all.

---

## Section 25 — Performance Analysis

**Hot paths (fire on every shift form load):**

1. `_compute_fc_variance` in `fms_shift_entry.py` — information_schema query per attendant row
2. `_compute_from_payments` — information_schema query per attendant row  
3. `_compute_accounted` in `fms_shift_reconciliation.py` — N+1 POS search per product line

**Estimated impact at scale:**

- 4 attendants per shift, 3 products = 12 rows
- `_compute_accounted`: 12 POS searches × ~10ms = 120ms added to every form load
- `information_schema` queries: 8 queries × ~2ms = 16ms per form load
- Total overhead: ~140ms per load (perceptible but not critical)

**At 10 shifts/day × 30 days = 300 shift records with history:**
- List view: 300 × overhead if all computed — use `store=True` for summary fields
- Gate checks at close: sequential gates, each a separate search — acceptable

**High-priority fixes:**
1. Replace `information_schema` with `'field' in self.env['account.payment']._fields` (zero DB cost)
2. Replace `_compute_accounted` N+1 with single `read_group` aggregation

---

## Section 26 — Target Architecture Diagram

```
FORECOURT
  Pumps (3 meters: elec-vol, elec-cash, mech-vol)
    ↓ manual entry OR PTS-2 auto-push
  fms.shift.meter.entry (per nozzle per shift)

  Tanks (dip gauge)
    ↓ manual entry
  fms.shift.dip.entry (per tank per shift)

  Attendants (cash count)
    ↓ manual entry
  fms.shift.attendant.cash (per person per shift)

FMS ORCHESTRATION LAYER
  fms.shift (state machine + 15 gates)
    |
    ├── fms.shift.product.sales (computed volume/cash per product)
    ├── fms.shift.residual.allocation (greedy volume reallocation)
    ├── fms.shift.fc.line (non-fuel goods/services)
    └── fms.shift.cash.movement (float/drop)

ODOO GL (authoritative)
  account.move — sales journal (FMS posts)
  account.move — residual reallocation (FMS posts)
  account.payment — AR receipts, floats, drops
  hr.expense — attendant expenses

ODOO INVENTORY (authoritative)
  stock.move — fuel consumption (FMS posts via close)
  stock.quant — physical stock (FMS syncs from dips)
  stock.valuation.layer — AVCO cost (Odoo auto-creates)

ODOO POS (payment capture only — FMS-primary for fuel revenue)
  pos.order → data source for payment method breakdown
  pos.session → reconciliation reference for Gates 3/4/8

AUDIT TRAIL (immutable)
  fms.meter_log — one record per nozzle per shift (write-locked)
  fms.dip_log — one record per tank per shift (write-locked)
  fms.pts.transaction — one record per PTS fill (write-locked)

EXTERNAL
  PTS-2 controller ← WebSocket → pts_bridge service → fms.pts.transaction
  EPRA price gazette → fms.price.period
```

---

## Section 27 — Definitive Data Flows (14 Flows)

**Flow 1 — Normal shift open**
1. Supervisor calls `action_open()`
2. `_populate_opening_entries()` reads prior shift's `fms.meter_log` and `fms.dip_log`
3. Creates `fms.shift.meter.entry` records with `opening_elec_volume = prior_log.closing_elec_volume`
4. Creates `fms.shift.dip.entry` records with `opening_volume = prior_log.closing_volume`
5. Shift state: draft → open

**Flow 2 — Attendant records meter reading**
1. Attendant enters `closing_elec_volume`, `closing_elec_cash`, `closing_mech_volume` in meter entry
2. System computes `elec_volume = closing − opening`, `elec_cash = closing_cash − opening_cash`
3. `fms.shift.product.sales` updated via compute

**Flow 3 — Cash sale (no POS)**
1. Attendant records sale in attendant cash: `reported_sales += amount`
2. At shift close: `_post_sales_journal` posts DR Cash Clearing | CR Fuel Revenue

**Flow 4 — Cash sale (with POS)**
1. POS order created: `pos.order` with fuel product
2. POS session close: POS posts DR Cash Clearing | CR [fuel category income account = Cash Clearing] (FMS-primary config)
3. Shift close: `_post_sales_journal` posts DR Cash Clearing | CR Fuel Revenue (FMS is authoritative)
4. POS entry nets to zero (both sides Clearing). FMS entry is real revenue.

**Flow 5 — MPesa sale**
1. POS order with MPesa payment method
2. `_compute_from_pos` aggregates MPesa amount via payment method ilike-name lookup
3. Attendant cash: `mpesa_amount` included in `total_out`
4. GL: DR MPesa Clearing | CR Fuel Revenue (posted by FMS `_post_sales_journal`)

**Flow 6 — Credit/AR sale**
1. Attendant marks sale as AR in attendant cash: `ar_amount`
2. Invoice created: `account.move` out_invoice DR AR-Customer | CR Fuel Revenue
3. Customer pays later: `account.payment` applied to invoice

**Flow 7 — Fuel delivery**
1. `fms.fuel.delivery` created when tanker arrives
2. `fms.fuel.delivery.line` per product with volume received
3. GL: DR Inventory Asset | CR AP Supplier (standard Odoo purchase flow)
4. Dip variance compute: fetches delivery_qty from delivery line for variance formula

**Flow 8 — Residual allocation**
1. `fms.shift.product.sales` detects: `volume_residual = meter_volume − pos_accounted_volume`
2. Negative residual (over-reported fuel): some fuel volume was actually non-fuel
3. `fms.shift.residual.allocation` created: reallocate volume from fuel to non-fuel product
4. GL: DR Diesel COGS | CR Carwash COGS

**Flow 9 — Shift close (happy path)**
1. Supervisor enters closing readings
2. `action_start_close()` → all 15 gates check
3. If all pass: `_write_meter_logs()` → immutable `fms.meter_log`
4. `_write_dip_logs()` → immutable `fms.dip_log`
5. `_post_stock_consumption()` → `stock.move` for meter_sales → `stock.valuation.layer`
6. `_sync_stock_quant_from_dips()` → `stock.quant` sync for variance
7. `_post_sales_journal()` → `account.move` (DR Clearing | CR Revenue per product)
8. State → closed

**Flow 10 — FC cash variance writeoff**
1. FC cash balance ≠ 0 after close attempt
2. Supervisor runs `action_writeoff_fc_variance()` with writeoff account
3. GL: DR Cash Clearing | CR Variance Expense (or reverse if overage)
4. FC balance = 0 → Gate 6 passes

**Flow 11 — Drive-off incident**
1. Supervisor creates `fms.incident`
2. `action_approve()` creates `stock.move` from fuel location to "Incident Losses" virtual location
3. Stock reduced without revenue → variance formula accounts for it

**Flow 12 — RTT correction (post-fix)**
1. Supervisor opens correction wizard, selects meter log and volume
2. Wizard creates `account.move`: DR Revenue | CR Clearing (journal reversal)
3. Wizard creates NEW `fms.meter_log` correction record with `correction_of_id`
4. Reports show net volume: original + correction
5. Original immutable, audit trail complete

**Flow 13 — PTS-2 transaction match**
1. PTS-2 pushes UploadPumpTransaction
2. `pts_bridge` calls `fms.pts.transaction.create_from_pts()`
3. `_try_match_shift()` finds open shift by time window
4. Matches `fms.pump` via `pts_device_id + pts_pump_number`
5. Matches `fms.pump.nozzle` via `pts_nozzle_number`
6. Finds `fms.shift.meter.entry` for that nozzle
7. Writes PTS fields to meter entry
8. State = matched

**Flow 14 — Shift dispute and re-close**
1. Supervisor calls `action_dispute()` → state = disputed
2. System cancels `sales_journal_entry_id` (after fix — currently no auto-cancel)
3. Corrections made (RTT wizard, manual adjustment)
4. Supervisor re-runs `action_close()` → gates re-run
5. New journal entries posted
6. State = closed

---

## Section 28 — Accounting Examples with KES Amounts

**Example 1: Normal shift, fuel only, cash sales**

Data: 200L diesel sold at KES 185/L. AVCO = KES 150/L. Closing dip matches expected (zero variance).

```
GL Entry — Shift Close:
DR  Cash Clearing          KES 37,000
    CR  Diesel Revenue             KES 37,000

Stock Entry:
DR  Diesel COGS (200L × 150)  KES 30,000
    CR  Diesel Inventory            KES 30,000
```

**Example 2: Dip variance — 50L shortage**

Data: Expected closing = 9,800L. Actual dip = 9,750L. AVCO = KES 150/L.

```
Stock Adjustment:
DR  Diesel COGS (50L × 150)  KES 7,500
    CR  Diesel Inventory           KES 7,500

(Posted via stock.quant sync — separate valuation layer from consumption)
```

**Example 3: Residual allocation — attendant lumped carwash into diesel**

Data: Diesel meter shows +100L over POS diesel sales. Carwash shortfall = 100L equivalent.

```
Reallocation Journal:
DR  Diesel COGS (100L × 150)    KES 15,000
    CR  Carwash COGS (100 units × 150)  KES 15,000

Note: Revenue stays on diesel (meter-based). COGS reallocated to carwash.
```

**Example 4: FC cash variance writeoff**

Data: FC captured KES 37,000, FC collected KES 36,800. Shortage KES 200.

```
Writeoff:
DR  Fuel Variance Expense   KES 200
    CR  Cash Clearing              KES 200

Post-writeoff: FC balance = 0. Gate 6 passes.
```

**Example 5: MPesa sale**

Data: 150L diesel sold via MPesa at KES 185/L = KES 27,750.

```
FMS Sales Journal:
DR  MPesa Clearing           KES 27,750
    CR  Diesel Revenue              KES 27,750

MPesa settlement (next business day):
DR  Bank                     KES 27,750
    CR  MPesa Clearing              KES 27,750
```

**Example 6: Credit sale + AR receipt next shift**

Data: Fleet customer, 300L at KES 185/L = KES 55,500.

```
Shift close (invoice):
DR  AR — KenTruck           KES 55,500
    CR  Diesel Revenue              KES 55,500

Next day receipt (separate shift):
DR  Cash Clearing           KES 55,500
    CR  AR — KenTruck               KES 55,500
```

**Example 7: Full shift with AVCO double-count (current bug)**

Data: Opening book stock 10,000L, meter_sales 200L, closing_dip 9,750L, AVCO KES 180/L.

```
CURRENT (WRONG):
_sync_stock_quant (runs first):
  DR  COGS (250L × 180)  KES 45,000
      CR  Inventory           KES 45,000

_post_stock_consumption:
  DR  COGS (200L × 180)  KES 36,000
      CR  Inventory           KES 36,000

Total COGS: KES 81,000. Stock: 9,550L (wrong — should be 9,750L)

CORRECT (after fix):
_post_stock_consumption (runs first):
  DR  COGS (200L × 180)  KES 36,000
      CR  Inventory           KES 36,000

_sync_stock_quant (variance only):
  DR  COGS (50L × 180)   KES 9,000
      CR  Inventory           KES 9,000

Total COGS: KES 45,000. Stock: 9,750L (matches dip).
```

---

## Section 29 — Final Decision Table

| # | Decision | Resolution | Evidence |
|---|---|---|---|
| 1 | Revenue ownership | FMS-PRIMARY for fuel | Revenue duplication confirmed in Section 3 |
| 2 | Non-fuel revenue | POS-PRIMARY | POS captures in real time; FMS not metered |
| 3 | Clearing account type | `asset_current` | BUG-07 — asset_receivable corrupts AR aging |
| 4 | fms_accounting | MERGE into fms | No functional benefit to separation; information_schema cost |
| 5 | Config threshold source | MOVE all to site.prefs | ARCH-02 — ir.config_parameter disconnected from gates |
| 6 | AVCO sequence | Consumption first, then quant sync | BUG-01 — double-count proved in Section 10 |
| 7 | RTT correction | Correction record, no SQL | BUG-05 — EPRA compliance |
| 8 | delivery_qty | Populate in _create_dip_log | BUG-06 — variance formula wrong on delivery days |
| 9 | Meniscus default | 0.5% of tank capacity, not 1000L | BUG-08 — gate effectively disabled |
| 10 | Gate 5 (attendant balance) | Remove POS-session guard | BUG-03 — applies at all stations |
| 11 | Gate 9 (AR receipts) | Scope to customer open balance, not shift | BUG-04 — cross-shift payments blocked |
| 12 | PTS missing fields | Add 9 fields (Section 20) | ARCH-03 — matching entirely broken |
| 13 | MPesa lookup | Add `fms_payment_type` field to payment method | Section 7 — name-ilike fragile |
| 14 | fms.pump company scope | Add `company_id` + record rule | Section 18 — multi-company unsafe |
| 15 | Dispute GL reversal | Auto-reverse sales_journal_entry on dispute | Section 15 — gap in dispute flow |
| 16 | fms_shift.py decomposition | Split into 6 files | Section 23 — 2762-line god class |
| 17 | information_schema queries | Replace with `_fields` dict check | ARCH-04 — schema stable at runtime |
| 18 | web_dark_mode dependency | Verify Odoo 18 Community compat or remove | Section 24 — install risk |
| 19 | write() protection on closed shifts | Block ALL non-whitelisted field writes | Section 18 — current protection incomplete |
| 20 | POS fuel journal config | Configure fuel category to post to Clearing | Section 3 — FMS-primary requires this |

---

## Section 30 — Implementation Roadmap

**Phase 1 — Critical bugs (before any production use)**

| Fix | File | Risk |
|---|---|---|
| BUG-01: swap close sequence | `fms_shift.py` lines 1444–1455 | HIGH — 2-line swap |
| BUG-07: clearing account domain | `fms_site_preferences.py` line 74 | LOW — domain string |
| BUG-08: meniscus default | `fms_site_preferences.py` | LOW — default value |
| BUG-06: populate delivery_qty | `fms_shift_entry.py` `_create_dip_log` | MEDIUM — fetch + write |

**Phase 2 — Gate fixes (before shift operations)**

| Fix | File | Risk |
|---|---|---|
| BUG-03: Gate 5 POS guard | `fms_shift.py` lines 1750–1766 | LOW — remove 2 lines |
| BUG-04: Gate 9 cross-shift | `fms_shift.py` lines 2183–2215 | MEDIUM — logic change |
| BUG-02: writeoff self-cancel | `fms_shift.py` lines 425–488 | MEDIUM — account logic |
| ARCH-02: config disconnection | `fms_config_settings.py` | MEDIUM — proxy pattern |

**Phase 3 — PTS integration (before PTS deployment)**

| Fix | File | Risk |
|---|---|---|
| Add 9 missing fields | `fms_pump.py`, `fms_shift_entry.py` | LOW — field additions |
| Fix state reference | `fms_pts.py` line 185 | LOW — string fix |

**Phase 4 — Security hardening**

| Fix | File | Risk |
|---|---|---|
| Add company_id to fms.pump | `fms_pump.py` + `ir_rule.xml` | MEDIUM — data migration needed |
| Strengthen write() protection | `fms_shift.py` | LOW — guard addition |
| RTT correction record pattern | `fms_shift_correction_wizard.py` + `fms_logs.py` | HIGH — new model field |

**Phase 5 — Architecture consolidation**

| Fix | File | Risk |
|---|---|---|
| Merge fms_accounting into fms | Multiple files | HIGH — module restructure |
| Replace information_schema | `fms_shift_entry.py` | LOW — import + field check |
| Fix N+1 in _compute_accounted | `fms_shift_reconciliation.py` | MEDIUM — query rewrite |

**Phase 6 — Decomposition (code quality)**

| Fix | Files | Risk |
|---|---|---|
| Split fms_shift.py | 6 new files | MEDIUM — Python mixin |

**Phase 7 — Non-fuel revenue boundary**

| Fix | File | Risk |
|---|---|---|
| POS-primary non-fuel config | Site preferences + POS category | MEDIUM — POS config |
| Remove non-fuel from _post_sales_journal if POS present | `fms_shift.py` | HIGH — revenue logic |

---

## Section 31 — Test Strategy

**Minimum test matrix before production:**

| Category | Count | Priority |
|---|---|---|
| AVCO sequence (Phase 1 fix) | 3 | CRITICAL |
| Gate 5 non-POS | 2 | CRITICAL |
| Gate 9 cross-shift | 2 | CRITICAL |
| Revenue duplication | 2 | CRITICAL |
| Clearing account type (domain only — manual) | 1 | HIGH |
| Delivery_qty in dip log | 2 | HIGH |
| RTT correction — no SQL in immutable log | 2 | HIGH |
| PTS match end-to-end | 3 | MEDIUM (before PTS) |
| Config threshold proxy | 2 | HIGH |
| Shift close happy path | 1 | CRITICAL |
| Shift dispute + re-close | 1 | HIGH |
| Multi-attendant FC cash = 0 | 2 | CRITICAL |

Total minimum: 23 tests. Target: 40+ with edge cases.

**Test approach:**
- Odoo `TransactionCase` for all GL-touching tests (rollback after each)
- `SavepointCase` for tests that need real savepoints
- Mock `pos.session` for POS-dependent gate tests
- No mocking of `account.move` or `stock.move` — test real GL

**Coverage target:** 80%+ on `fms_shift.py`, `fms_shift_entry.py`, `fms_shift_reconciliation.py`

---

## Section 32 — Production Readiness Gate

### NOT SAFE FOR PRODUCTION

Current state. All of the following must be resolved:
- BUG-01 (AVCO double-count): every shift posts wrong COGS and wrong stock
- BUG-07 (clearing account type): AR aging corrupted from first shift
- BUG-03 (Gate 5 skip): attendant balance gate disabled at non-POS sites
- ARCH-02 (config disconnect): operators cannot configure gate thresholds

### PILOT READY (single site, supervised)

After Phase 1 + Phase 2 fixes, with:
- AVCO sequence corrected and tested
- Gate fixes in place
- Clearing account domain correct
- Config threshold proxy working
- Manual verification of GL accuracy for 5 shifts before opening to full operations

### PRODUCTION READY

After Phases 1–4 plus:
- PTS integration working (if PTS hardware deployed)
- Security hardening (company_id on pump, write() protection)
- 23+ tests passing
- One full month pilot with zero GL discrepancies
- EPRA audit trail review (meter logs immutable, RTT correction compliant)

---

## Section 33 — 20 Critical Rules

1. Never post revenue from both POS session close AND FMS shift close for fuel products. One source only. Decision: FMS-primary.

2. `_post_stock_consumption` must always run BEFORE `_sync_stock_quant_from_dips`. Order reversal causes AVCO double-count.

3. Cash clearing account must use `asset_current` type. Never `asset_receivable`.

4. `fms.meter_log` and `fms.pts.transaction` are unconditionally immutable. No `env.cr.execute` UPDATE against them, ever.

5. RTT corrections create a new correction log record. They do not modify the original log.

6. All 15 gates are hard gates. No "close anyway" path. Supervisor must resolve, not bypass.

7. Gate 5 (attendant balance) must check ALL stations, with or without POS sessions.

8. Gate 9 (AR receipts) must compare against customer open balance, not shift-scoped invoices.

9. All FMS threshold configuration lives in `fms.site.preferences`. Never read from `ir.config_parameter` in gate logic.

10. Meniscus threshold is expressed as percentage of tank capacity, not absolute litres.

11. `delivery_qty` must be populated in every `fms.dip_log` record at shift close.

12. `fms.pump` must have `company_id` before multi-company deployment.

13. `information_schema` queries are forbidden in compute methods. Use `'field' in model._fields`.

14. PTS shift state search must use only valid states: `draft`, `open`, `closing`, `closed`, `disputed`. Not `in_progress`.

15. Payment method type identification must use explicit field (`fms_payment_type`), not name string matching.

16. `fms_accounting` must either be declared as a dependency in `__manifest__.py` or merged into `fms`.

17. On shift dispute, the `sales_journal_entry_id` entry must be cancelled before corrections are made.

18. Non-fuel revenue posting must be assigned to one authoritative source (FMS or POS) per site configuration. Default: POS-primary for non-fuel.

19. `fms.shift.write()` on a closed shift must block ALL field writes, not just state transitions. Whitelist: `dispute_note`, `state = disputed`.

20. Every architectural decision must be traceable to observed code in the repository or verified Odoo 18 behaviour. No speculative rules.

---

## Section 34 — Final Executive Verdict

### 18 Diagnostic Questions

| # | Question | Answer |
|---|---|---|
| 1 | Is the module safe to deploy today? | NO |
| 2 | What is the single most critical bug? | BUG-01 — AVCO double-count. Every shift overstates COGS and understates stock. |
| 3 | Is the GL architecture sound? | Yes, after BUG-01 fix. FMS-primary revenue ownership is correct pattern. |
| 4 | Are hard gates enforced? | Partially. Gate 5 silently skips non-POS stations. Gate 9 blocks valid cross-shift payments. |
| 5 | Is the audit trail EPRA-compliant? | No. RTT wizard uses raw SQL to update immutable meter logs. |
| 6 | Is PTS integration functional? | No. Matching references 9 non-existent fields. Zero transactions will match. |
| 7 | Is multi-company safe? | No. fms.pump has no company_id. |
| 8 | Are operator-facing configuration controls working? | No. Threshold config UI has zero effect on gate behavior (ARCH-02). |
| 9 | Is opening reading auto-population working? | Yes. `_populate_opening_entries` confirmed correct. |
| 10 | Is residual allocation architecture sound? | Yes. Greedy volume-based approach is correct for the use case. |
| 11 | Is wetstock variance formula correct? | Yes in compute; broken in persistence (delivery_qty never written). |
| 12 | Is the 10-minute shift close achievable? | Yes, after Phase 1 fixes and performance optimizations. |
| 13 | Is AVCO unit cost correct? | Yes. Ratio preserved. Total value and quantity wrong (separate issue). |
| 14 | Is shift dispute flow complete? | No. No auto-reversal of GL entries on dispute. |
| 15 | Is the code maintainable? | No. 2762-line god class. Phase 6 decomposition required. |
| 16 | Does the test suite cover critical paths? | Unknown. No test files reviewed. Minimum 23 tests required before pilot. |
| 17 | Is revenue duplicated with POS? | Yes, for POS-linked stations. Requires FMS-primary POS journal configuration. |
| 18 | Can this reach production quality? | Yes. Phase 1–4 fixes are well-scoped. No architectural rewrites needed. |

### One-Paragraph Architecture Summary

The FMS module is architecturally sound in its overall design — the three-meter shift reconciliation model, FMS-primary revenue ownership, AVCO-based stock valuation via native Odoo models, and immutable audit log pattern are all correct for an EPRA-compliant fuel station management system. However, the module has nine confirmed bugs and six confirmed architectural problems that collectively make it unsafe for production use. The most critical bug (BUG-01) causes every shift to double-post stock consumption, overstating COGS by approximately 1.5–2× and leaving the stock ledger permanently wrong. The most critical architectural problem (ARCH-02) makes gate threshold configuration inert — operators believe they are configuring tolerance levels but the gates read from a different storage location. PTS-2 integration is completely broken due to nine missing fields. With a structured four-phase remediation covering critical bugs, gate fixes, PTS field additions, and security hardening, this module can reach pilot-ready status. No architectural rewrites are required; all identified problems have surgical, localized fixes. The implementation roadmap in Section 30 provides the precise sequence.

---

*Document generated: 2026-09-13*  
*Based on full forensic review of FMS repository at commit 8942e8a*  
*Supersedes: FMS_AUDIT_REPORT.md, FMS_ADVERSARIAL_VALIDATION.md*
