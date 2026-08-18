# FMS Native Odoo Integration & Shift UX

**Baseline:** 266 tests, 0 failures (as of 2026-08-18 FIN series)
**Goal:** Finalize native Odoo integration, clean up UX, separate reporting from operations.

## Status Legend
- [ ] Not started
- [~] In progress
- [x] Complete
- [!] Blocked

---

## Phase A — Documentation
- [x] Read all docs/runbook/*.md
- [x] Identify current workflow gaps vs target architecture
- [x] Update task.md (this file)
- [x] Update docs/runbook/10-sales-workflow.md — native invoice auto-populate, block-if-no-shift, vehicle/driver onchange
- [-] Update docs/runbook/03-daily-shift.md — already accurate, no changes needed

## Phase B — Native Invoice (account.move extension cleanup)

### B1 — Remove duplicate/broken fields on account.move [x]
- [x] Removed `fms_vehicle` (Char) from fms_credit_customer.py, kept `fms_vehicle_id` (M2o)
- [x] Fixed broken `_onchange_fms_vehicle_id` — was writing to non-existent `fms_vehicle_reg` on account.move
- [x] Added `fms_odometer` Float field to account.move
- [x] Updated view: fms_credit_customer_views.xml — added `fms_vehicle_id`, `fms_driver_id`, `fms_shift_id`, `fms_attendant_id`, `fms_odometer`

### B2 — Auto-populate shift on invoice creation [x]
- [x] Override `default_get` on account.move: auto-finds active shift when `fms_invoice_context=True`
- [x] `create()` override blocks invoice if no active shift (Forecourt context only)
- [x] `action_fms_credit_customer` passes `fms_invoice_context=True` in context

### B3 — Vehicle ↔ Customer ↔ Driver auto-resolution [x]
- [x] `_onchange_fms_vehicle_id`: auto-sets `partner_id`, auto-sets `fms_driver_id` if exactly one driver
- [x] `_onchange_fms_driver_id`: auto-sets `partner_id`, auto-sets `fms_vehicle_id` if exactly one vehicle
- [x] `_check_vehicle_customer_match`: vehicle.partner_id must match invoice partner
- [x] `_check_driver_customer_match`: driver.partner_id must match invoice partner

### B4 — Test results [x]
- Tests run: 2026-08-18 (scoped: --test-tags fms,fms_accounting)
- fms: 0 failures, 0 errors ✓
- fms_accounting (incl. test_native_integration.py — 15 new tests): 0 failures, 0 errors ✓

---

## Phase C — hr.expense Extension (optional)

**Decision:** The existing `account.payment` with `fms_payment_context='expense'` already handles shift cash expenses and participates in reconciliation. Extending `hr.expense` would require adding `hr_expense` as a module dependency. Defer unless explicitly required. Mark as design decision.

- [-] Extend hr.expense — deferred; using account.payment/fms_payment_context='expense' instead
- [x] account.payment already extended with fms_shift_id, fms_attendant_id, fms_station_id, fms_payment_context
- [x] Expense payments link to shift and participate in cash reconciliation formula

---

## Phase D — Menu Restructuring [x]

- [x] Added `menu_fms_cash` structural menu (Cash section, sequence 35)
- [x] Added `menu_fms_customers_fleet` structural menu (Customers & Fleet section, sequence 45)
- [x] Moved Credit Customers → renamed to Customer Invoices, kept in Sales
- [x] Moved Fleet Vehicles + Drivers to Customers & Fleet
- [x] Moved Cash Movements, Expenses, Vendor Payments to Cash section
- [x] Added Fleet Customers shortcut (res.partner filtered to fms_is_fleet_customer=True)
- [x] Added Attendant Cash Breakdown report menu
- [x] Operations section now clean: Shifts + Fuel Deliveries only

---

## Phase E — Shift Sheet UX

- [x] Audit existing view tabs — no orphan operational forms found
- [x] "Sales Summary" tab slimmed to KPI-only (removed product_sales_ids list) — renamed to "Sales KPIs"
- [x] Full product breakdown kept in Reports → Shift Reconciliation (already existed)
- [x] meter_entry_ids and dip_entry_ids tabs unchanged (operational input)
- [x] Attendant Cash tab unchanged
- [x] Residual Allocations tab kept (operational — supervisor reviews before approving close)

---

## Phase F — Reporting Separation

Existing reports (read-only SQL views) already in fms_report_views.py:
- [x] R1 Shift Overview, R2 Tank Loss, R3 Wetstock, R4 Meter Reconciliation (SQL views)
- [x] R27 Attendant Cash Breakdown (SQL view, FIN-008)
- [x] All reports confirmed in Reconciliation or Reports menus — not mixed with operational forms
- [x] Added Customer Statements menu under Customers & Fleet (action_fms_customer_statements — FMS shift invoices filtered by partner)

---

## Phase G — Security & Performance
- [x] Company isolation on account.payment (IR rules — FIN-012)
- [x] Company isolation on fms.shift (record rules)
- [x] Composite index on account_payment (FIN-010)
- [x] account.move FMS fields: company isolation via `rule_fms_move_supervisor` (company_id in company_ids)
- [x] fms.vehicle and fms.driver: company_id record rules added (rule_fms_vehicle_supervisor, rule_fms_driver_supervisor)

---

## Phase H — Tests
- [x] 266 baseline tests passing
- [x] 25 FIN series tests (test_fin_series.py)
- [ ] B2: test_invoice_auto_populate_from_shift
- [ ] B2: test_invoice_blocked_no_active_shift
- [ ] B3: test_vehicle_auto_populates_customer
- [ ] B3: test_driver_auto_populates_customer
- [ ] B3: test_vehicle_customer_mismatch_blocked
- [ ] Run full suite after each phase

---

## Implementation Log

| Date | Phase | Task | Result |
|------|-------|------|--------|
| 2026-08-18 | FIN series | 266 tests, 0 failures | ✓ |
| 2026-08-18 | Phase A | Documentation read, task.md updated | ✓ |
| 2026-08-18 | Phase A | Runbook 10-sales-workflow.md rewritten for native Odoo architecture | ✓ |
| 2026-08-18 | Phase B1 | Removed broken fms_vehicle Char + legacy fms_driver M2o from account.move | ✓ |
| 2026-08-18 | Phase B1 | Added fms_odometer to account.move | ✓ |
| 2026-08-18 | Phase B1 | Updated fms_credit_customer_views.xml with proper FMS fields | ✓ |
| 2026-08-18 | Phase B2 | Invoice default_get + create() auto-populate/block from active shift | ✓ |
| 2026-08-18 | Phase B2 | action_fms_credit_customer passes fms_invoice_context=True | ✓ |
| 2026-08-18 | Phase B3 | Vehicle/driver onchange auto-resolution + mismatch constraints | ✓ |
| 2026-08-18 | Phase D | Cash + Customers & Fleet menus added, cash items moved | ✓ |
| 2026-08-18 | Phase G | fms.vehicle + fms.driver company isolation record rules | ✓ |
| 2026-08-18 | Phase H | Full test suite run (all 66 modules) | fms: 0 failures ✓, fms_accounting: 0 failures ✓ |
| 2026-08-18 | Phase H | View fix: fms_odometer always-invisible validator | Fixed — removed `not fms_vehicle_id` condition |
| 2026-08-18 | Phase H | Scoped test run --test-tags fms,fms_accounting | 0 FAIL / 0 ERROR — all passing ✓ |
| 2026-08-18 | E2E | fms_e2e DB: pumps + nozzles + fuel tanks created | ✓ |
| 2026-08-18 | E2E | e2e_v6.py: shift opens 4 meter + 3 dip entries, closes, immutability enforced | PASSED ✓ |
| 2026-08-18 | E2E | seed_e2e.py updated with idempotent pump/nozzle/tank creation | ✓ |
| 2026-08-18 | Phase E | Sales Summary tab slimmed to KPI-only, renamed Sales KPIs | ✓ |
| 2026-08-18 | Phase F | Customer Statements menu added under Customers & Fleet | ✓ |
