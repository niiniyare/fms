# FMS Comprehensive Audit Report

**Date:** 2026-09-13
**Auditor:** Claude Code (claude-sonnet-4-6)
**Scope:** Full repository read — all Python models, XML views, security, reports, wizards, hooks
**Directive:** Read everything first. Understand the system. Trace the connections. Then audit it. Do not modify anything.

---

## 1. Executive Summary

The FMS is a genuine, working Odoo 18 module with real business logic. The domain model is conceptually sound and solves a real problem. However, the implementation has accumulated significant structural debt, several financially dangerous accounting decisions, a partially broken PTS integration, and documentation that is materially incorrect in multiple places.

**Overall score: 5.5 / 10**

| Dimension | Score | Reason |
|---|---|---|
| Domain correctness | 6/10 | Core concepts right; some gate logic wrong |
| Accounting | 5/10 | Manual GL posting works but clearing account domain wrong; AVCO corruption risk |
| Inventory/Wetstock | 5/10 | Formula correct; stock quant sync bypasses Odoo costing |
| Security | 7/10 | Solid ACL + record rules; one bypass via direct SQL |
| UI/UX | 6/10 | Well-designed menus; 15-gate overhead at close is heavy |
| Maintainability | 3/10 | 2763-line god class; constant schema introspection |
| Documentation | 3/10 | CLAUDE.md is significantly outdated |

---

## 2. What Is Done Well

1. **State machine and audit trail** — `draft → open → closing → closed → disputed` is clean. Immutable `fms.meter_log` / `fms.dip_log` with ORM-level write/unlink guards is a good EPRA compliance pattern.

2. **Gate status panel** — `_compute_gate_status_html` live progress indicator is excellent UX for the supervisor.

3. **Batch SQL aggregation** — `_compute_fc_variance`, `_compute_from_payments`, `_compute_commercial_summary` all batch queries across record sets rather than running one query per record. Good performance engineering.

4. **Company isolation** — Record rules scoping all models to `company_ids` are complete and correct.

5. **Emergency override with audit log** — `fms.shift.override.log` is immutable, records all bypassed gates, and requires approver name + reason. Correct auditing.

6. **`fms.site.preferences.get_for_company()`** — Defensive `savepoint + retry on UNIQUE` handles concurrent creation race cleanly.

7. **Non-fuel FC lines (`fms.shift.fc.line`)** — `opening_qty + delivery_qty - closing_qty = qty_sold` formula mirrors fuel dip reconciliation, making the mental model consistent.

8. **`fms_setup_check.py`** — Proactive GL configuration validation before shift close prevents silent failures. The "fix product accounts" button is practical.

9. **`_safe_query()` in dashboard** — Wrapping every optional SQL view query in a savepoint is the correct pattern for optional module queries.

10. **Price period model** — `fms.price.period` with EPRA gazette reference, overlap constraint, and `current_period()` helper is domain-appropriate.

---

## 3. Critical Problems

### [CRITICAL-1] `fms_shift.py` is a 2763-line god class

One file handles state transitions, 15 gate checks, GL posting, stock moves, audit log snapshots, product sales aggregation, residual allocation, dip variance calculation, dashboard HTML generation, report data methods, auto-scheduling, emergency override, and more.

**Why it matters:** Untestable in isolation, impossible to reason about, any change risks breaking unrelated functionality.

**Recommendation:** Split into `fms_shift_state.py`, `fms_shift_gate.py`, `fms_shift_service.py`.

---

### [CRITICAL-2] Stock quant sync corrupts AVCO valuation

`_sync_stock_quant_from_dips()` writes `inventory_quantity` and calls `action_apply_inventory()` to force physical dip volumes into Odoo stock. This creates **inventory adjustment moves** rather than consumption moves, which breaks AVCO costing.

**Evidence:** `fms_shift.py`:
```python
quant.sudo().write({'inventory_quantity': entry.closing_volume})
quant.sudo().action_apply_inventory()
```

For AVCO-costed fuel products, `action_apply_inventory()` posts a stock adjustment at the current AVCO cost. Fuel variance (spillage, meter error, temperature expansion) is not a purchase — it has no landed cost. The AVCO will shift incorrectly on every shift close, corrupting COGS and inventory valuation permanently.

**Fix:** Remove `_sync_stock_quant_from_dips()`. The `_post_stock_consumption()` stock moves already consume fuel from tanks. Post a variance stock.move only when `abs(shift_variance) > tolerance`. The dip log is the physical verification record; the accounting record is the meter-based consumption.

---

### [CRITICAL-3] Clearing account domain is wrong

**Evidence:** `fms_site_preferences.py:72`:
```python
clearing_account_id = fields.Many2one(
    'account.account', 'Cash Clearing Account',
    domain=[('account_type', '=', 'asset_receivable')],
```

A cash clearing account for fuel sales is NOT a receivable. Posting `DR Cash Clearing (AR) / CR Revenue` on every shift close will create outstanding AR — your entire debtors balance will be polluted with all fuel sales as uncollected receivables. The AR aging report becomes meaningless.

**Fix:** Change domain to `[('account_type', 'in', ('asset_cash', 'asset_current', 'asset_prepayments'))]`.

---

### [CRITICAL-4] PTS integration is non-functional

`fms.pts.transaction._try_match_shift()` references fields that do not exist in any model in this repository.

**Evidence:** `fms_pts.py:184–235`:
```python
# fms.pump has no pts_device_id field:
pump = self.env['fms.pump'].search([
    ('pts_device_id', '=', self.pts_device_id.id),   # NOT DEFINED
    ('pts_pump_number', '=', self.pump_number),        # NOT DEFINED
])
# fms.pump.nozzle has no pts_nozzle_number field:
nozzle = pump.nozzle_ids.filtered(
    lambda n: n.pts_nozzle_number == self.nozzle       # NOT DEFINED
)
# fms.shift has no date_start field:
shift = self.env['fms.shift'].search([
    ('state', 'in', ['open', 'in_progress', 'draft']),
    ('date_start', '<=', self.date_end),               # NOT DEFINED
])
```

Also: `fms.pts.device.pump_ids = One2many('fms.pump', 'pts_device_id', ...)` but `fms.pump` has no `pts_device_id` field.

Any PTS transaction received will always stay in `state='raw'` or raise an AttributeError. The real-time pump integration is 100% broken.

---

### [CRITICAL-5] Correction wizard bypasses immutable log via direct SQL

**Evidence:** `fms_shift_correction_wizard.py:211–215`:
```python
self.env.cr.execute(
    "UPDATE fms_meter_log SET rtt_volume = COALESCE(rtt_volume,0) + %s WHERE id = %s",
    (self.rtt_volume, self.meter_log_id.id),
)
```

`fms.meter_log.write()` raises `ValidationError("Meter logs are immutable")`. This SQL call silently bypasses that guard. The audit trail is no longer tamper-proof. Any supervisor can change meter readings post-close via the correction wizard with `correction_type='rtt'`.

**Fix:** The RTT correction should post a correcting journal entry only (which it does) and NOT modify the immutable meter log. The correction is a separate accounting adjustment — not a retroactive change to raw meter data.

---

### [CRITICAL-6] Residual allocation GL is never posted

`_post_residual_allocation_journals()` is defined but never called in `action_close_shift()`.

The close sequence comment says:
```python
# Residual allocation journals removed — FC-line multi-product entries
# handle the money side.
```

But `_calculate_residuals()` still fires inside `action_start_closing()`. Residual records are created but never journalized — phantom allocations with no GL backing. `fms.shift.residual.allocation.journal_entry_id` will always be empty. Either call the method or delete it and document the decision.

---

### [CRITICAL-7] Gate 9 (Customer Receipts) logic is wrong

**Evidence:** `fms_shift.py` Gate 9:
```python
invoiced = sum(self.env['account.move'].search([
    ('fms_shift_id', '=', self.id), ...
]).mapped('amount_total'))
receipts = sum(self.env['account.payment'].search([
    ('fms_shift_id', '=', self.id), ...
]).mapped('amount'))
if receipts > invoiced + 0.01:
    raise ValidationError(...)
```

Customers routinely pay previous shifts' invoices during the current shift. This gate will falsely block close at any station with active credit customers. In practice, this gate would fail daily.

---

## 4. Domain Logic Audit

**Shift lifecycle:** Correct. `draft → open → closing → closed`. Single-open-shift constraint correctly enforced.

**Three-meter system:** Electronic volume, electronic cash, mechanical — industry-correct for petrol stations. RTT deduction from qty_sold_elec is correct.

**Formula:**
```
qty_sold_elec = (closing_elec_volume - opening_elec_volume) - rtt_volume  ✓
elec_cash_sold = closing_elec_cash - opening_elec_cash                     ✓
```

RTT correctly not deducted from elec_cash_sold (meter shows gross — industry standard).

**Attendant assignment:** Two modes (per_nozzle, pre_assigned) correct for different station configurations.

**Residual allocation:** Conceptually sound. Algorithm correctly identifies over-invoiced vs under-invoiced products and allocates volumes. Problems:
- No product-type compatibility check (can allocate diesel volume to carwash)
- COGS journal entries never posted (see CRITICAL-6)
- Greedy largest-to-largest matching is arbitrary

**Incident register:** `draft → reported → approved → closed` workflow with stock write-off on approve is correct domain modeling.

**Non-fuel sales:** `qty_sold = opening + received - closing` mirrors fuel dip math.

**Cash movement:** `fms.shift.cash.movement` auto-creating and posting `account.payment` is reasonable design. Float/drop pattern is correct.

**Missing domain concepts:**
- No vehicle/fleet tracking (RFID, plate-to-customer lookup)
- No fuel delivery workflow (purchase order → delivery → tank receipt)
- No customer credit limit enforcement
- No price change audit trail

---

## 5. Wetstock & Inventory Calculation Audit

**Primary formula:**
```
Expected closing = opening_volume + delivery - meter_sales
Variance = closing_dip - expected_closing
```
Implemented correctly in `_compute_dip_variance_data()`.

**Delivery quantity:** Always 0 because `fms_fuel_delivery_line` table does not exist in this module. Formula is structurally correct but operationally incomplete — every variance calculation ignores deliveries.

**AVCO corruption:** `_sync_stock_quant_from_dips()` forces Odoo book stock to equal the physical dip. See CRITICAL-2.

**Month variance calculation:** `dl.delivery_qty` is never populated in `_create_dip_log()`. `SUM(dl.delivery_qty)` always returns 0. Month variances underestimate actual losses for months with deliveries.

**Meniscus default:** 1000L absolute. For a 10,000L tank this is ±10% — far too loose for EPRA compliance (typically ±0.5%). Must be changed before production.

**Dip variance percentage:** `variance_pct = |closing - opening| / closing × 100`. Using closing as denominator is non-standard — EPRA usually uses opening as base. Minor issue, not incorrect.

**Capacity constraint:** `_check_closing_volume_capacity()` correctly prevents closing dip > tank capacity.

---

## 6. Accounting Audit

### Shift close GL entry (`_post_sales_journal`)

**Posts:**
```
DR  Cash Clearing account        (total meter cash sales)
CR  Product Revenue account      (per product, net of tax)
CR  Tax account                  (per tax if price_include)
```

**Problems:**

1. `DR Cash Clearing` uses an `asset_receivable` account — wrong domain. Creates fake AR on every shift close.
2. Products lacking `fms_revenue_account_id` are silently skipped; DR is rebalanced down. Cash collected but not journalized = unbalanced books.
3. Uses `fms_revenue_account_id` on `product.product` instead of Odoo's standard `property_account_income_id`. Bypasses standard product income account mechanism.
4. Single DR line — no per-attendant or per-payment-mode GL breakdown. Payment mode breakdown lives only in attendant cash fields, not in the closing journal entry.

### FC Cash write-off (`action_writeoff_fc_variance`)

If `journal.default_account_id` is None, both debit and credit use `writeoff_account` — a zero-effect self-cancelling entry. No error is raised. Silent accounting failure.

### Variance resolution wizard

```
Advance: DR Staff Advances | CR Clearing   ✓
Writeoff: DR Variance Write-Off | CR Clearing  ✓
```

Conceptually correct. But wizard sets `'fms_shift_id': shift.id` on `account.move` — this field doesn't exist in this module (from `fms_accounting`). Will fail if `fms_accounting` not installed.

### Residual allocation journals

Never posted (see CRITICAL-6). Residual COGS reclassification not in GL.

### Stock consumption (`_post_stock_consumption`)

Creates `stock.move` records directly without `stock.picking`. These moves don't appear in any picking list. No FK link to picking.

### What is NOT accounting for

- Non-fuel FC line sales (no GL entry unless `fms_accounting` installed)
- Expense payments (relies on account.payment from `fms_accounting`)
- M-Pesa/card settlement (relies entirely on POS session close)

---

## 7. Payment Architecture Audit

**Two layers:**

Layer 1 — FMS-native: `fms.shift.cash.movement` → `account.payment` (floats, drops). Clean.

Layer 2 — POS-integrated: M-Pesa, card, AR via `pos.payment` on linked `pos.session`. Attendant cash computation reads these via `_compute_from_pos` using name-based payment method lookup.

**Problems:**

1. **Name-based payment method detection is fragile:**
   ```python
   mpesa_methods = PayMethod.search([('name', 'ilike', 'mpesa')])
   card_methods  = PayMethod.search([('name', 'ilike', 'card')])
   ```
   If method named "M-Pesa KE" or "Safaricom Pay" it won't match. A flag field `is_mpesa`, `is_card`, `is_ar` on `pos.payment.method` is the correct fix.

2. No `account.payment` for M-Pesa. M-Pesa settlement implicitly handled by POS session close only.

3. Credit sales: AR from POS creates receivable. FMS closing journal posts to clearing. Possible duplicate revenue recognition depending on POS accounting config.

4. No explicit refund handling. POS refunds appear as negative amounts; attendant cash compute doesn't handle them explicitly.

5. `_compute_from_receipts` depends only on `('shift_id', 'attendant_id')`. Changes to invoices posted after initial compute won't trigger recompute.

---

## 8. Shift Management Audit

**Opening:** Auto-populates meter entries from last shift's closing nozzle positions. Correct. No re-entry required.

**Start Closing:** Checks FC Cash variance. Opens `FmsShiftReconWizard` if variance exists. Good UX.

**Close process:** 15 gate checks run sequentially, failing-fast on first failure. UX problem: supervisor gets one error at a time, must fix and retry. Gate status panel shows all failures simultaneously — but the close button still fails on the first gate. Better: run all gates, collect all failures, show everything at once.

**Disputed state:** Good safety valve. One-disputed-shift-at-a-time default is correct.

**Auto-open next shift:** Well-implemented and practical.

---

## 9. Odoo Native Integration Audit

**Using native Odoo correctly:**
- `stock.location` extension — correct and minimal
- `product.product` extension — correct
- `hr.employee` extension — correct
- `pos.session` Many2many link — correct
- `pos.payment` / `pos.order` queries — reading native POS data without modifying it

**Should use native Odoo instead:**

1. **Stock consumption:** Direct `stock.move` creation without `stock.picking` produces orphan moves. Use a dedicated "Fuel Consumption" picking type.

2. **GL posting:** FMS creates parallel accounting entries. If both FMS GL and POS session GL run, revenue may be double-counted. Must choose one: FMS accounting or POS accounting.

3. **Incident stock write-off:** Consider using `stock.scrap` (Odoo's native scrap order) instead of custom location creation.

**Can stay custom:**
- `fms.price.period` — EPRA region-specific pricing is beyond what `product.pricelist` supports without extension
- Shift management — no Odoo module covers fuel station shifts
- Wetstock/dip — no Odoo module covers this

---

## 10. OCA Integration Audit

Declared OCA dependencies: **none**. Only `web_dark_mode`, `web_responsive` (OCA UI modules).

**Potentially useful OCA modules:**

| FMS Feature | OCA Module | Assessment |
|---|---|---|
| Kenya VAT/eTIMS | `l10n_ke` | Should check for eTIMS integration — highest priority |
| Approval workflows | `approval` | Could replace manual supervisor approval on incidents |
| Audit trail | `base_audit_trail` | Could supplement immutable log for non-locked fields |

**Should NOT replace FMS custom code:**
- Shift management, wetstock/dip, EPRA price periods, PTS hardware — no OCA equivalents.

---

## 11. Model-by-Model Review

| Model | Purpose | Verdict | Key Problems |
|---|---|---|---|
| `fms.shift` | Main orchestrator | KEEP, SPLIT | 2763 lines; god class |
| `fms.pump` | Pump master data | KEEP | No company_id; PTS fields missing |
| `fms.pump.nozzle` | Nozzle master | KEEP | PTS fields missing |
| `fms.shift.meter.entry` | Nozzle readings | KEEP | PTS fields referenced but missing |
| `fms.shift.dip.entry` | Tank dip readings | KEEP | OK |
| `fms.shift.attendant.cash` | Cash reconciliation | KEEP | Two parallel balance systems (balance vs fc_variance) |
| `fms.shift.product.sales` | Aggregation helper | SIMPLIFY | Not a real record; deleted/recreated on every refresh |
| `fms.shift.residual.allocation` | Residual records | KEEP | GL never posted |
| `fms.meter_log` | Immutable meter log | KEEP | RTT bypass via direct SQL in correction wizard |
| `fms.dip_log` | Immutable dip log | KEEP | `delivery_qty` never set; context key bypass |
| `fms.incident` | Incident register | KEEP | No fleet.vehicle FK |
| `fms.price.period` | EPRA price period | KEEP | OK |
| `fms.price.period.line` | Price lines | KEEP | Missing UNIQUE on (period_id, product_id) |
| `fms.site.preferences` | Config | KEEP | Clearing account domain wrong |
| `fms.shift.cash.movement` | Floats/drops | KEEP | OK |
| `fms.shift.fc.line` | Non-fuel sales | KEEP | Closing state not blocked in write() |
| `fms.pts.device` | PTS controller | FIX | pump_ids backlink points to non-existent field |
| `fms.pts.transaction` | PTS transactions | FIX | Non-functional; missing pump/nozzle fields |
| `fms.overview` | Dashboard | KEEP | Queries non-existent views gracefully |
| `fms.setup.check` | GL config check | KEEP | Remove hardcoded account codes/amount |
| `fms.shift.recon.wizard` | Variance resolution | KEEP | References fms_accounting fields that may not exist |
| `fms.emergency.override.wizard` | Emergency close | KEEP | OK |
| `fms.shift.correction.wizard` | Post-close correction | FIX | Direct SQL on immutable log |
| `fms.shift.override.log` | Override audit | KEEP | OK |
| SQL view report models (R2–R29) | Reporting | KEEP | `amount_kes` columns hardcode currency |

---

## 12. Architecture Audit

### Module boundary problem

This module (`fms`) has implicit runtime dependency on `fms_accounting` (not in this repo, not declared in manifest). `fms_accounting` extends `account.payment`, `account.move`, `hr.expense` with FMS fields. The `fms` module detects these extensions via `information_schema.columns` queries at runtime.

This creates:
- Constant schema introspection on hot paths
- Conditional logic spread across 7+ methods
- Invisible feature degradation
- Impossible to know what state the system is in without checking the DB

**Fix:** Declare `fms_accounting` as a dependency, or replace schema introspection with a module-presence check (`self.env['ir.module.module'].search([('name','=','fms_accounting'),('state','=','installed')])`).

### Dual configuration system

`fms.site.preferences` (DB record, per company) and `res.config.settings` extension (`ir.config_parameter`, global key-value). The gates read exclusively from `site.preferences`. The config settings panel writes to `ir.config_parameter`. These two systems are disconnected. **The config settings panel changes have no effect on gate behavior.**

### `fms.shift.product.sales` design flaw

This is a computed aggregation table (not a real business record) that is deleted and recreated on every `_refresh_product_sales()` call. Any FK reference to its records will break after the next refresh.

---

## 13. Code Quality Audit

**God class:** `fms_shift.py` at 2763 lines is the single biggest maintainability problem.

**Schema introspection in hot paths:** `_compute_fc_variance` runs `information_schema.columns` queries on every field recompute. Runs hundreds of times per shift open. Cache the result per model load.

**Dead/broken code:**
- `_post_residual_allocation_journals()` — defined but never called in close sequence
- `FmsPtsDevice.pump_ids` — backlink field pointing to non-existent forward field on `fms.pump`
- `_try_match_shift()` — references `date_start`, `pts_device_id`, `pts_pump_number`, `pts_nozzle_number` — all non-existent

**Hardcoded values (should be in site preferences):**
- `tolerance_KES = 100.0` in Gate 2
- `_FLOAT_TOLERANCE = 1.0` in Gate 10
- Account codes `301000`, `101401` in `fms_create_opening_equity`
- Opening amount `500_000.0` in `fms_create_opening_equity` — station-specific, should not exist in a general module

**Dual balance fields:**
- `fc_cash_balance` (old system: sum of attendant `balance` field)
- `fc_cash_balance_total` (new system: sum of attendant `fc_variance`)
- Gate 4 uses new system; overview dashboard uses old system. One should be removed.

---

## 14. Database / ORM Audit

**Missing constraints:**
- `fms.price.period.line`: no UNIQUE on `(period_id, product_id)` — duplicate prices per product per period
- `fms.pump` name/code UNIQUE: not scoped to company — multi-company name conflicts
- `fms.meter_log.shift_id` has `ondelete='cascade'` — deleting a shift deletes EPRA compliance logs. Should be `ondelete='restrict'`

**N+1 risks:**
- `_compute_dip_variance_data`: called per dip entry, each runs 2–3 SQL queries. 4 tanks × 15 gates = 60+ queries per close attempt.
- `_compute_accounted` in `fms.shift.product.sales`: one `pos.order.line.search` per product sales line — not batched.

**Stored computed fields with incomplete depends:**
- `_compute_commercial_summary` stored despite doing raw SQL on `account_payment` and `account_move`. The `depends` only includes FMS-native fields. Changes to payments won't trigger recompute.

**`fms.dip_log.delivery_qty`:** Field defined in model. Never populated by `_create_dip_log()`. SQL queries reading `dl.delivery_qty` always get 0.

---

## 15. Security Audit

**Strengths:**
- Three-tier group hierarchy (Attendant ⊂ Supervisor ⊂ Accountant) with `implied_ids` is correct
- Company-scoping record rules on all main models
- Immutable log models block write/unlink at ORM level
- Emergency override requires Accountant group + mandatory reason + approver

**Weaknesses:**

1. **`fms.shift.write()` doesn't block field changes on closed shifts:**
   Only blocks state field changes. A supervisor can change `date`, `label`, `supervisor_id`, `notes` on a closed shift without restriction. Should raise ValidationError for any write on closed shift.

2. **Direct SQL bypass in correction wizard** — see CRITICAL-5.

3. **`fms.dip_log` context bypass:** Any code path can set `fms_delivery_update` context to write to immutable dip logs. The context key itself is not protected — only the group check inside is.

4. **Attendants can write other attendants' FC lines:** No record rule scoping `fms.shift.fc.line` to the creating attendant.

5. **`fms.pump` has no company_id:** All attendants from all companies read all pumps. Data leakage risk in multi-company setups.

6. **`fms.incident` has no attendant-scoped rule:** An attendant could create an incident attributing liability to another attendant.

---

## 16. UI/UX Audit

**Strengths:**
- Gate status panel (`gate_status_html`) is excellent — live readiness indicator
- Smart buttons on shift form for quick navigation

**Weaknesses:**

1. **15-gate sequential close:** Supervisor gets one error at a time. Gate status panel shows all failures but close button fails on the first. Fix: make the gate panel actionable or only show "Close Shift" button when all gates are green.

2. **Two FC Cash fields visible in UI:** `fc_cash_balance` (old) and `fc_cash_balance_total` (new). Confusing which one matters for close.

3. **Config settings panel is a trap:** `fms_config_settings.py` writes to `ir.config_parameter`. Gates read from `fms.site.preferences`. Changes in Settings → Forecourt have no effect on gate behavior. The UI lies to the user.

4. **No mobile-optimized transaction entry form** beyond included responsive CSS.

---

## 17. Naming Audit

**Good:** All custom models use `fms.` prefix. Python classes use `FMS` prefix. File names match model names.

**Problems:**
- `fms.meter_log` — should be `fms.meter.log` (underscore vs dot inconsistency)
- `fms.dip_log` — should be `fms.dip.log`
- `elec_cash_sold` — "elec" is unclear. Better: `cash_meter_amount`
- `amount_kes` in SQL views — hardcodes currency in column name
- `fc_line_ids` — "fc" = forecourt, not obvious. Better: `nonfuel_sale_ids`
- `fms_is_forecourt` on `stock.location` — unclear. Better: `fms_is_nonfuel_store`

---

## 18. Remove / Merge / Simplify / Replace List

| Item | Action | Reason |
|---|---|---|
| `fms_create_opening_equity()` in setup check | DELETE | Hardcodes account codes 301000/101401 and amount 500,000 — station-specific |
| `tolerance_KES = 100.0` in Gate 2 | MOVE to site.preferences | Hardcoded threshold |
| `fc_cash_balance` field on shift | REMOVE | Superseded by `fc_cash_balance_total`; dashboard uses wrong field |
| `balance` field in attendant cash | DEPRECATE | The fc_variance system supersedes it; both coexist confusingly |
| `_post_residual_allocation_journals()` | FIX or DELETE | Never called on close; residual GL orphaned |
| `_sync_stock_quant_from_dips()` | REPLACE | Overwrites AVCO quants; use variance stock.move only |
| Schema introspection in `_compute_fc_variance` | CACHE | Runs information_schema query on every field recompute |
| PTS fields missing from `fms.pump` | ADD | PTS integration broken without them |
| Direct SQL in correction wizard | REPLACE | Bypasses immutable log ORM guard |
| `fms.shift.write()` state guard | STRENGTHEN | Block all field edits on closed shifts, not just state |
| `clearing_account_id` domain | FIX | Change from `asset_receivable` to current asset types |
| Gate G14 (no unresolved exceptions) | REMOVE | Redundant — `state='closing'` already guarantees no disputed |
| Gate G9 (customer receipts) | FIX or REMOVE | Cross-shift receipt matching logic is wrong |
| `fms.config.settings` dual storage | MERGE into site.preferences | Two-system configuration disconnected; config UI has no effect |
| `fms.meter_log` / `fms.dip_log` naming | RENAME to `fms.meter.log` / `fms.dip.log` | Convention inconsistency |
| `amount_kes` column names in SQL views | RENAME to `amount` | Currency should not be in column names |
| `_post_residual_allocation_journals` | CALL or DELETE | Currently dead code |

---

## 19. Documentation vs Code

| Documentation says | Code actually does | Status |
|---|---|---|
| "FC Cash must = 0 exactly (GATE 1)" | Gate 4 is FC Cash; Gate 1 is Volume Reconciliation | OUTDATED |
| "3 hard gates (FC Cash, Attendants, Stock Variance)" | 15 gates implemented | SIGNIFICANTLY OUTDATED |
| "Meniscus ±0.5% per tank" | Default is 1000L absolute (±10% for 10,000L tank) | INCORRECT |
| "Residual reallocation posts DR Diesel COGS / CR Carwash COGS" | Residual GL journals never called on close | NOT IMPLEMENTED |
| "Meter/dip logs immutable after close" | Correct for ORM; RTT correction wizard uses direct SQL bypass | PARTIALLY INCORRECT |
| "Opening Readings Auto-Fetch from previous shift" | Uses `nozzle.current_*` positions (set on shift close) | ACCURATE |
| "Residuals Always Allocated — No unaccounted category" | Residuals calculated; GL never posted | PARTIALLY IMPLEMENTED |
| "8 tasks, ~16 hours" | Significantly more features implemented beyond the 8-task plan | OUTDATED |

---

## 20. Testing Gaps

Critical missing test coverage (based on code review):

1. Accounting correctness — does shift close produce correctly balanced journal entries (DR = CR always)?
2. AVCO corruption — does `_sync_stock_quant_from_dips` with AVCO-costed products corrupt valuation?
3. Gate 9 false positives — does Gate 9 block close when a customer pays last shift's invoice?
4. Clearing account domain — does setup check catch when a receivable account is used as clearing?
5. PTS integration matching — all paths in `_try_match_shift` (matched, conflict, raw)
6. Concurrent shift open — does single-open-shift constraint hold under concurrent requests?
7. Emergency override completeness — does override log record all gate failures at override time?
8. Direct SQL immutability bypass — can the correction wizard successfully bypass the ORM guard?
9. Residual allocation consistency — same inputs always produce same output?
10. Multi-company isolation — can Company A see Company B's shifts?
11. Gate 2 tolerance edge cases — what happens at exactly 100 KES variance vs 100.01?
12. FC variance write-off null journal — does silent zero-effect entry actually get caught?

---

## 21. Recommended Target Architecture

```
fms (core — this module)
├── Master data
│   ├── fms.pump                 (custom — no Odoo equiv)
│   ├── fms.pump.nozzle          (custom)
│   └── fms.price.period         (custom — EPRA-specific)
│
├── Shift orchestration (SPLIT fms_shift.py into 3 files)
│   ├── fms_shift_state.py       — identity, state machine, ORM overrides
│   ├── fms_shift_gate.py        — all 15 gate checks
│   └── fms_shift_service.py     — GL posting, stock, residuals, auto-open
│
├── Shift child models
│   ├── fms.shift.meter.entry    (custom)
│   ├── fms.shift.dip.entry      (custom)
│   ├── fms.shift.attendant.cash (custom — unify balance/fc_variance)
│   ├── fms.shift.fc.line        (custom)
│   └── fms.shift.cash.movement  (custom)
│
├── Reconciliation
│   ├── fms.shift.product.sales  (SIMPLIFY — mark clearly as transient aggregation)
│   └── fms.shift.residual.allocation (custom — FIX: actually post GL)
│
├── Audit logs (immutable)
│   ├── fms.meter.log            (RENAME from fms.meter_log)
│   ├── fms.dip.log              (RENAME from fms.dip_log)
│   └── fms.shift.override.log   (keep)
│
├── Incidents
│   └── fms.incident             (custom — ADD fleet.vehicle FK)
│
├── PTS integration
│   ├── fms.pts.device           (custom — ADD missing pump fields)
│   └── fms.pts.transaction      (custom — FIX matching logic)
│
├── Configuration (MERGE — single source of truth)
│   └── fms.site.preferences     (remove ir.config_parameter dual storage)
│
└── Reports (SQL views)
    └── fms.report.*             (keep — rename amount_kes columns)

fms_accounting (separate module — DECLARE as dependency or cut the cord cleanly)
├── extends account.payment      (fms_shift_id, fms_attendant_id, fms_payment_context)
├── extends account.move         (fms_shift_id, fms_attendant_id)
├── extends hr.expense           (fms_shift_id)
└── fms.fuel.delivery            (fuel delivery workflow)

Native Odoo (use as-is):
├── stock.picking + stock.move   (fuel consumption — use picking type, not orphan moves)
├── pos.session / pos.order      (POS sales capture)
├── account.move                 (GL via fms_accounting extension)
└── hr.employee                  (attendant base)
```

---

## 22. Refactoring Roadmap

### PHASE 0 — Financial correctness (fix before any production use)

1. Fix `clearing_account_id` domain: change `asset_receivable` → `asset_current` (one line in fms_site_preferences.py)
2. Fix `_sync_stock_quant_from_dips`: remove quant overwrite; post variance stock.move only for material variances above meniscus
3. Fix `action_writeoff_fc_variance` null clearing account fallback (silent zero-effect entry)
4. Remove direct SQL in `fms_shift_correction_wizard._post_rtt_correction`; add a separate correction record
5. Fix Gate 9 (Customer Receipts) — compare against outstanding receivables, not shift-scoped invoices

### PHASE 1 — Data integrity

1. Add UNIQUE SQL constraint on `fms.price.period.line(period_id, product_id)`
2. Strengthen `fms.shift.write()` to block all field edits on closed shifts
3. Fix `fms.dip_log` context bypass — document it clearly or change to a proper supervisor-token pattern
4. Add `delivery_qty` population in `_create_dip_log()` (or remove the field if delivery workflow is not in scope)
5. Fix `fms.shift.fc.line.write()` to block edits in `closing` state (not just `closed`)
6. Change `fms.meter_log.shift_id` from `ondelete='cascade'` to `ondelete='restrict'`

### PHASE 2 — PTS integration fix

1. Add `pts_device_id` (Many2one fms.pts.device) and `pts_pump_number` (Integer) to `fms.pump`
2. Add `pts_nozzle_number` (Integer) to `fms.pump.nozzle`
3. Add `pts_transaction_id`, `pts_volume`, `pts_tc_volume`, `closing_totalizer` to `fms.shift.meter.entry`
4. Fix `_try_match_shift` to use `shift.date` instead of nonexistent `shift.date_start`
5. Fix `shift.state` reference — remove `'in_progress'` (non-existent state)

### PHASE 3 — Model consolidation

1. Merge `fms.config.settings` storage into `fms.site.preferences` as single source
2. Remove `fc_cash_balance` (old system); unify on `fc_cash_balance_total`/`fc_variance`
3. Remove or deprecate `balance` in attendant cash
4. Delete `fms_create_opening_equity()` from setup check

### PHASE 4 — Accounting and GL cleanup

1. Call `_post_residual_allocation_journals()` in `action_close_shift()` or delete it and document the decision
2. Replace direct `stock.move` creation with `stock.picking` using a dedicated "Fuel Consumption" picking type
3. Declare `fms_accounting` as explicit optional dependency; replace runtime schema introspection with module-presence check

### PHASE 5 — Architecture split

1. Split `fms_shift.py` into `fms_shift_state.py`, `fms_shift_gate.py`, `fms_shift_service.py`
2. Move report data methods (`get_sales_register_data`, `get_meter_attendant_summary`) out of `fms.shift` into a dedicated report model

### PHASE 6 — Code cleanup

1. Replace name-based payment method detection with flag fields on `pos.payment.method`
2. Cache schema introspection results (information_schema queries) per model/request — not per compute call
3. Batch `_compute_dip_variance_data` — currently called per entry in a loop
4. Move hardcoded tolerances (Gate 2: 100 KES, Gate 10: 1.0) to site preferences
5. Remove Gate G14 (redundant)

### PHASE 7 — Testing

1. Accounting correctness tests (journal entry balance, account types, no fake AR)
2. AVCO valuation tests (shift close with AVCO-costed product)
3. Concurrent shift open tests
4. Multi-company isolation tests
5. Gate edge-case tests (Gate 9 cross-shift receipts, Gate 2 tolerance boundary)
6. PTS matching tests (all three outcomes: matched, conflict, raw)

### PHASE 8 — Documentation

1. Update CLAUDE.md: correct gate count (15 not 3), meniscus default (1000L not 0.5%), residual GL status (not implemented)
2. Document the two-module architecture (fms + fms_accounting) and what breaks without it
3. Add inline formula documentation to `_compute_dip_variance_data`

### PHASE 9 — Final hardening

1. Add `company_id` to `fms.pump` for multi-site support
2. Add attendant-scoped record rule to `fms.shift.fc.line`
3. Add attendant-scoped record rule to `fms.incident`
4. Add `fleet.vehicle` FK to `fms.incident`
5. Rename `fms.meter_log` → `fms.meter.log` and `fms.dip_log` → `fms.dip.log`
6. Rename `amount_kes` columns in SQL views to `amount`

---

## 23. Final Assessment

**1. Is the FMS domain model fundamentally sound?**
Yes. Pump → nozzle → meter reading → shift → dip → reconciliation → GL is the correct structure for a petrol station. The model correctly represents real operations.

**2. Is the accounting architecture fundamentally sound?**
No. The clearing account domain is wrong (receivable instead of current asset), stock quant overwrite corrupts AVCO, and residual GL is never posted. These three issues make the accounting unreliable for financial reporting.

**3. Are the wetstock calculations correct?**
The formula (`closing - (opening + delivery - meter_sales)`) is correct. But delivery is always 0 because the delivery table doesn't exist in this module. Structurally correct; operationally incomplete.

**4. Is the shift model correct?**
Yes, with exceptions. State machine is sound. Gate 9 logic is wrong. Gate 14 is redundant. Two parallel attendant balance implementations create confusion.

**5. Is the payment architecture correct?**
Partially. Floats/drops via account.payment are correct. M-Pesa/card relying on POS session is correct. Name-based payment method detection is fragile. No explicit refund handling.

**6. Is the system over-engineered anywhere?**
Yes. 15 gates at close — several are weak or redundant (G13, G14). Dual configuration system is unnecessary complexity.

**7. Is it under-engineered anywhere?**
Yes. PTS integration is broken. Delivery workflow missing. Fleet/vehicle tracking missing. Multi-company pump support missing.

**8. Which models should disappear?**
`fms_create_opening_equity()` function (not a model). No full models should be deleted. `fms.shift.product.sales` should be reconsidered — it pretends to be a stable record but is deleted on every refresh.

**9. Which models should merge?**
`fms.config.settings` storage into `fms.site.preferences`. The `balance` and `fc_variance` fields on `fms.shift.attendant.cash` should be unified.

**10. Which models should extend native Odoo?**
Stock consumption should create `stock.picking` not orphan `stock.move`. Incidents could extend `stock.scrap`.

**11. Which OCA modules should be considered?**
`l10n_ke` for eTIMS VAT compliance. Possibly OCA approval for incidents.

**12. Biggest architectural mistake:**
Implicit, undeclared dependency on `fms_accounting` detected only via runtime schema introspection. Makes module behavior unpredictable and prevents static analysis.

**13. Biggest business-logic risk:**
Gate 9 incorrectly blocks shifts when customers pay previous shifts' invoices. Will cause daily operational failures at any station with active credit customers.

**14. Biggest accounting risk:**
`clearing_account_id` domain of `asset_receivable` will pollute the AR balance with all fuel sales. Every shift close creates phantom receivables. Financial statements wrong from day one.

**15. Biggest maintainability problem:**
`fms_shift.py` at 2763 lines. Any change anywhere risks breaking anything.

**16. Biggest UX problem:**
15 sequential gate failures at close. Supervisor must fix and retry one gate at a time. For a 10-minute close target this is unworkable when gates fail.

**17. Fix FIRST:**
The clearing account domain (`asset_receivable` → current asset type). One-line change in `fms_site_preferences.py:74`. Prevents the most catastrophic accounting failure. Do this before any shift is closed in production.

**18. Do NOT waste time fixing yet:**
PTS integration field additions. Hardware integration can wait until the core station workflow is financially correct and stable.

---

*Report generated: 2026-09-13. Read-only audit — no files modified.*
