# FMS Task Tracker — Canonical Source of Truth

**Repository:** `/home/niini/fms` + `/home/niini/fms_accounting`
**Odoo:** 18.0
**Last updated:** 2026-08-18

---

## Architecture Principles (Non-Negotiable)

1. FMS is NOT fuel-only — fuel, dry stock, services all reconcile.
2. Native Odoo models first. Extend with `_inherit`, never duplicate.
3. Shift is the accounting boundary — every transaction traces to a shift.
4. Read-only SQL views for all heavy reports. No N+1 ORM in reports.
5. Multi-company: every query scopes to `env.company` / `company_id`.
6. No parallel accounting ledger. One source of truth.
7. Every override audited (role + reason + timestamp + user).

---

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete and verified
- `[!]` Blocked
- `[-]` Intentionally excluded

---

## COMPLETED — Phase A: Audit `[x]`

18 gaps identified and addressed in Phases C1–FIN.

---

## COMPLETED — Phase C1: Critical Business Logic `[x]`

| ID | Task | File |
|----|------|------|
| C1.1 | COGS missing → error (not warning) | `models/fms_setup_check.py` |
| C1.2 | Remove silent fallback in `_get_fms_journal` / `_get_clearing_account` | `models/fms_shift.py` |
| C1.3 | Electronic vs Manual ±1 L gate | `models/fms_shift.py` |
| C1.4 | Electronic vs Cash configurable threshold gate | `models/fms_site_preferences.py`, `models/fms_shift.py` |
| C1.5 | Price period used in meter entry amount | `models/fms_shift_entry.py` |
| C1.6 | Disputed shift concurrency control | `models/fms_shift.py`, `models/fms_site_preferences.py` |
| C1.7 | Failed-close audit log to chatter | `models/fms_shift.py` |
| C1.8 | Emergency override with audit trail | `wizards/fms_emergency_override_wizard.py` |
| C1.9 | Dip capacity validation | `models/fms_shift_entry.py` |
| C1.10 | Security ACL corrections | `security/ir_model_access.xml` |
| C1.11 | Concurrent shift edit protection | `models/fms_shift.py` |

---

## COMPLETED — Phase C2: Sales Integration `[x]`

| ID | Task | File |
|----|------|------|
| C2.1 | Sales workflow runbook | `docs/runbook/10-sales-workflow.md` |
| C2.2 | `account.move` FMS fields | `fms_accounting/models/fms_shift_accounting.py` |
| C2.3 | Vehicle model | `fms_accounting/models/fms_vehicle.py` |
| C2.4 | Driver model | `fms_accounting/models/fms_driver.py` |
| C2.5 | `res.partner` FMS fleet fields | `fms_accounting/models/fms_credit_customer.py` |
| C2.10 | Meter vs Invoice+Receipt gate (Gate 6) | `models/fms_shift.py` |
| C2.12 | Prevent sales outside active shift | `fms_accounting/models/fms_shift_accounting.py` |

---

## COMPLETED — Phase C3: Attendant Assignment `[x]`

Pre-assigned mode and per-nozzle mode both implemented.

---

## COMPLETED — Phase H8: Security Audit `[x]`

- `account.move` record rules (company-scoped)
- Closed-shift write protection
- 14 non-superuser security tests (`tests/test_h8_security.py`)
- `fms.shift.create()` constraint reads company from `vals`, not `env.company`

---

## COMPLETED — FIN Series: Native Odoo Accounting Integration `[x]`

| ID | Task | File |
|----|------|------|
| FIN-001 | `account.move` FMS fields (shift, attendant, vehicle, driver, station) | `fms_accounting/models/fms_shift_accounting.py` |
| FIN-002 | `account.payment` FMS fields + context types | `fms_accounting/models/fms_payment_extension.py` |
| FIN-003 | Expense via `fms_payment_context='expense'` | `models/fms_shift_entry.py` |
| FIN-004 | Vendor payment via `fms_payment_context='vendor_payment'` | `fms_accounting/models/fms_payment_extension.py` |
| FIN-005 | Cash float via `fms_payment_context='cash_float'` | `models/fms_shift_entry.py` |
| FIN-006 | Full cash reconciliation formula (SQL, no N+1) | `models/fms_shift_entry.py` |
| FIN-007 | Dry-stock invoice lines in `_refresh_product_sales` | `models/fms_shift.py` |
| FIN-008 | Attendant cash breakdown SQL view (R27) | `models/fms_report_views.py` |
| FIN-009 | 14-gate shift close pipeline | `models/fms_shift.py` |
| FIN-010 | Composite indexes + stored fields | `models/fms_shift.py`, `fms_accounting/models/` |
| FIN-011 | Menu shortcuts (receipts, vendor payments, floats, drops, expenses) | `fms_accounting/views/fms_accounting_menus.xml` |
| FIN-012 | Record rules for `account.payment` (company isolation) | `fms_accounting/security/ir_rule.xml` |
| FIN-013 | `test_fin_series.py` — 25 tests | `tests/test_fin_series.py` |

---

## COMPLETED — Phase E5.4: Tank Loss Analysis SQL View `[x]`

`fms.report.tank.loss` SQL view with CTEs for dip, meter, residuals, prefs.

---

## COMPLETED — Phase 8: Gate Status Panel `[x]`

`gate_status_html` field on shift form — dry-run all 14 gates, show pass/fail + fix hints.

---

## IN PROGRESS — Test Suite Stabilisation `[~]`

**Root cause resolved:** Fresh DB (`dropdb --if-exists` + `--without-demo=all`) added to `make odoo-test`. Pump `code` field added to fixtures. H8 date conflict fixed. Last run still shows failures — needs one clean run.

**Pending:** Run `make odoo-test` and confirm 0 errors.

---

## OPEN TASKS — New Spec (2026-08-18)

Implementation order: SR-001 → SR-004 → REC-001 → REC-002 → MENU-001 → INV-002 → WET-001 → WET-002 → REC-003 → REC-004 → GATE-002 → SEC-001 → TEST

---

### SR-001 — `fms_nozzle_id` on `account.move.line` `[ ]`

- **Why:** Ties a receipt/invoice line to a pump nozzle → enables per-nozzle meter vs sales reconciliation (R10, REC-004).
- **Files:** `fms_accounting/models/fms_sales_receipt.py`
- **Model:** `account.move.line` `_inherit` → `fms_nozzle_id = Many2one('fms.pump.nozzle')`
- **Constraint:** if `line.product_id.fms_is_fuel` and no `fms_nozzle_id` → log warning (not block; attendant cover allowed).
- **View:** Add optional `fms_nozzle_id` column to receipt line list in `fms_sales_receipt_views.xml`.
- **Index:** Add DB index on `account_move_line.fms_nozzle_id`.
- **Tests:** `test_sr_001` — nozzle saved on line; queryable in SQL.

---

### SR-004 — `fms_vehicle_id` M2O on `account.move` `[ ]`

- **Why:** Proper fleet attribution (not free-text `fms_vehicle_reg`). `fms.vehicle` model already exists.
- **Files:** `fms_accounting/models/fms_sales_receipt.py` (already has `FMSAccountMoveExtension` in `fms_shift_accounting.py` — add there)
- **Change:** Add `fms_vehicle_id = Many2one('fms.vehicle')` to `FMSAccountMoveExtension`. `@api.onchange('fms_vehicle_id')` → populate `fms_vehicle_reg` from `vehicle.plate_no`.
- **View:** Add `fms_vehicle_id` field to receipt form (replaces or sits alongside `fms_vehicle_reg`).
- **Tests:** `test_sr_004` — vehicle_id auto-fills vehicle_reg.

---

### REC-001 — Service products in `_refresh_product_sales` `[ ]`

- **Why:** Spec §2.D — service sales (carwash, tyre, mechanical) must be in shift reconciliation. Currently only dry-stock (storable/consumable) invoice lines are aggregated.
- **Files:** `fms/models/fms_shift.py` (`_refresh_product_sales`)
- **Current:** `if line.product_id.fms_is_fuel: continue` — dry-stock included, but service products also have `fms_is_fuel=False` so they may already be included.
- **Check:** Verify service-type products (`product_id.type == 'service'`) appear in `by_product` from invoice loop. If already included → mark `[x]`.
- **If not:** Ensure `product_id.type in ('service', 'consu', 'product')` all captured.
- **Tests:** `test_rec_001` — post a receipt with Car Wash service line → appears in `shift.product_sales_ids`.

---

### REC-002 — Shift summary computed fields (full reconciliation) `[ ]`

- **Why:** Spec §8 — supervisor must see complete position without manual calculation.
- **Files:** `fms/models/fms_shift.py`
- **New stored computed fields on `fms.shift`:**
  - `total_fuel_sales` — sum of `product_sales_ids` where `is_fuel=True`, `elec_cash_sold`
  - `total_drystock_sales` — sum of `product_sales_ids` where `is_fuel=False`, `allocated_amount`
  - `total_service_sales` — sum of service product invoice lines linked to shift (SQL aggregated)
  - `total_all_sales` — sum of above three
  - `total_cash_received` — payments with `fms_payment_context='customer_receipt'` (cash journal)
  - `total_digital_received` — payments digital journal
  - `total_credit_sales` — invoice lines on credit (AR) linked to shift
  - `expected_cash_position` — opening_float + total_cash_received + total_fuel_cash - cash_drops - expenses - vendor_payments
  - `declared_cash_total` — sum of `attendant_cash_ids.cash_collected`
  - `cash_variance` = `expected_cash_position - declared_cash_total`
- **Use SQL aggregation** — no N+1. Use `self.env.cr.execute()` with shift_id param.
- **View:** Add "Reconciliation Summary" tab to shift form showing all fields read-only.
- **Tests:** `test_rec_002` — create shift with meter entries + receipts + payments → summary fields compute correctly.

---

### MENU-001 — Menu architecture per spec §14 `[ ]`

- **Why:** Current menu (Overview | Operations | Sales & Cash | Reporting | Configuration) doesn't match spec. Missing: Reconciliation section, Inventory section, Sales separate from Cash.
- **Target structure:**
  ```
  Forecourt
  ├── Dashboard
  ├── Active Shift
  ├── Shifts
  ├── Sales                     ← new top-level section
  │   ├── Sales Receipts
  │   ├── Customer Invoices     ← native Odoo shortcut
  │   └── Customer Payments     ← native Odoo shortcut
  ├── Operations
  │   ├── Meter Readings
  │   ├── Dip Readings
  │   ├── Fuel Deliveries
  │   └── Cash Movements        ← grouped: floats, drops, expenses, vendor payments
  ├── Inventory                 ← new section (Odoo shortcuts)
  │   ├── Products
  │   ├── Stock Receipts
  │   └── Stock Adjustments
  ├── Reconciliation            ← new section
  │   ├── Shift Reconciliation
  │   ├── Meter Reconciliation
  │   ├── Wetstock
  │   ├── Cash Reconciliation
  │   └── Tank Loss Analysis
  ├── Reports
  │   ├── Shift Summary
  │   ├── Sales Report
  │   ├── Attendant Report
  │   └── Customer Statements
  └── Configuration
      ├── Station Setup
      ├── Products & Prices
      ├── Payment Methods
      └── Preferences
  ```
- **Files:** `fms/views/fms_menu_structure.xml`, `fms/views/fms_menus.xml`, `fms_accounting/views/fms_accounting_menus.xml`
- **Use `ir.actions.act_window`** pointing to native Odoo models (product.template, stock.picking, stock.inventory.line) for Inventory shortcuts.
- **Tests:** Module loads without XML error; all menu actions resolve.

---

### INV-002 — Customer Invoice action with FMS context `[ ]`

- **Files:** `fms_accounting/views/fms_accounting_menus.xml`, new action record
- **Action:** Opens `account.move` list filtered `move_type=out_invoice`, with `default_fms_shift_id` from active shift context.
- **Tests:** Action resolves; domain applied.

---

### WET-001 — Complete Wetstock SQL report `[ ]`

- **Requirement:** Per spec §2.J: Opening + Deliveries - Meter Sales ± Adjustments = Theoretical vs Actual Dip. Variance %. Loss category.
- **Check current:** Does `fms.report.wetstock` exist? Does it have all components?
- **Files:** `fms/models/fms_report_views.py`
- **Required columns:** `shift_id`, `shift_date`, `location_id`, `product_id`, `opening_dip`, `deliveries`, `meter_sold`, `adjustments`, `theoretical_closing`, `actual_closing_dip`, `variance_l`, `variance_pct`, `loss_category`
- **company_id scoped** — join to `fms_shift` for company.
- **Tests:** `test_wet_001` — verify view returns correct variance for known test data.

---

### WET-002 — Tank Loss Source Correlation `[ ]`

- **Requirement:** Per spec §16 — correlate variance with likely cause (meter drift, missing sale, delivery variance, evaporation, etc.)
- **Current:** `fms.report.tank.loss` exists (E5.4) but may not have cause-correlation logic.
- **Enhancement:** Add `loss_source` computed column:
  - `'meter_drift'` — if electronic vs manual variance > threshold
  - `'missing_sale'` — if meter sold > invoice/receipt volume > tolerance
  - `'delivery_variance'` — if delivery dip variance is large
  - `'within_tolerance'` — if variance < meniscus
  - `'unknown'` — else
- **Files:** `fms/models/fms_report_views.py` (update `FMSReportTankLoss.init()` SQL)
- **Tests:** `test_wet_002` — known meter drift scenario → `loss_source = 'meter_drift'`.

---

### REC-003 — Cash Reconciliation SQL report (complete) `[ ]`

- **Requirement:** Per spec §11: Opening Float + Cash Sales + Customer Receipts + Cash Pickups - Cash Drops - Cash Expenses - Vendor Payments - Refunds = Expected Cash; compare vs Declared Cash.
- **Check current:** `fms.report.receipt.reconciliation` exists — review SQL; is it complete?
- **Files:** `fms_accounting/models/fms_receipt_reconciliation.py`
- **Required columns:** `shift_id`, `attendant_id`, `company_id`, `opening_float`, `fuel_cash`, `drystock_cash`, `service_cash`, `customer_receipts`, `cash_pickups`, `cash_drops`, `expenses`, `vendor_payments`, `refunds`, `expected_cash`, `declared_cash`, `variance`, `variance_pct`
- **Tests:** `test_rec_003` — totals match manual calculation.

---

### REC-004 — Meter vs Receipt gate: per-nozzle check `[ ]`

- **Current:** `_gate_check_meter_vs_sales` compares total fuel volume sold (meter) vs total invoice/receipt lines — crude.
- **Enhancement:** After SR-001 (nozzle on line), compare per nozzle: `meter_entry.qty_sold_elec` vs `sum(invoice_line.quantity where fms_nozzle_id = nozzle)`. Block if any nozzle exceeds tolerance.
- **Files:** `fms/models/fms_shift.py`
- **Tests:** `test_rec_004` — nozzle with 50 L meter vs 45 L receipts (above tolerance) → gate blocks.

---

### GATE-002 — Gate: dry-stock/service reconciliation at close `[ ]`

- **Requirement:** Before shift close — total dry-stock + service sales declared must reconcile with posted invoices/receipts linked to shift.
- **Files:** `fms/models/fms_shift.py` — new method `_gate_check_nonf uel_sales_posted`
- **Logic:** Check all `product_sales_ids` where `is_fuel=False` have `allocated_amount > 0` OR have matching posted invoice lines.
- **Tests:** `test_gate_002` — unposted dry-stock receipt blocks close.

---

### SEC-001 — Company scope audit on all `search()` calls `[ ]`

- **Files:** `fms/models/fms_shift.py`, `fms_accounting/models/*.py`
- **Check:** Every `search([...])` that returns shift-related records must include `('company_id', 'in', self.env.companies.ids)` or equivalent.
- **Fix:** Add company filter where missing.
- **Tests:** Test with two-company setup — user of company B cannot see company A records.

---

### TEST-SUITE — Full clean run `[ ]`

- Run `make odoo-test` (fresh DB, no demo).
- Target: 0 failures, 0 errors in `fms` module tests.
- Fix any remaining failures before marking complete.

---

## Implementation Log

| Date | Task | Result | Notes |
|------|------|--------|-------|
| 2026-08-18 | Phase A audit | `[x]` | 18 gaps identified |
| 2026-08-18 | C1 (11 tasks) | `[x]` | COGS gate, 3-meter, emergency override, chatter, disputed, etc. |
| 2026-08-18 | C2 (8 tasks) | `[x]` | Vehicle/Driver/Gate 6/account.move fields |
| 2026-08-18 | C3 (4 tasks) | `[x]` | Attendant assignment modes |
| 2026-08-18 | FIN-001–014 | `[x]` | Full native accounting integration |
| 2026-08-18 | H8 security | `[x]` | 14 non-superuser tests; closed-shift write guard |
| 2026-08-18 | E5.4 tank loss SQL | `[x]` | fms.report.tank.loss |
| 2026-08-18 | Phase 8 gate panel | `[x]` | gate_status_html on shift form |
| 2026-08-18 | Test DB: fresh + no-demo | `[x]` | Makefile updated (f93e341) |
| 2026-08-18 | task.md v2 merged | `[x]` | This file |
