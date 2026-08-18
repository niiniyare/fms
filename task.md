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
- [ ] Update docs/runbook/10-sales-workflow.md — native invoice auto-populate, block-if-no-shift, vehicle/driver onchange
- [ ] Update docs/runbook/03-daily-shift.md — Shift Sheet as primary UX, reporting separation

## Phase B — Native Invoice (account.move extension cleanup)

### B1 — Remove duplicate/broken fields on account.move
- [ ] `fms_vehicle` (Char) in fms_credit_customer.py conflicts with `fms_vehicle_id` (M2o) in fms_shift_accounting.py — remove `fms_vehicle` (Char), keep Many2one
- [ ] Fix broken `_onchange_fms_vehicle_id` — references `fms_vehicle_reg` which doesn't exist on account.move
- [ ] Add `fms_odometer` Float field to account.move
- [ ] Update view: fms_credit_customer_views.xml — remove old `fms_vehicle`/`fms_driver` Char fields, add `fms_vehicle_id`, `fms_driver_id`, `fms_odometer`

### B2 — Auto-populate shift on invoice creation
- [ ] Override `default_get` on account.move: when `fms_invoice_context=True` in context, auto-find active shift for company, set `fms_shift_id` + `invoice_date`
- [ ] Block invoice creation if no active shift (when `fms_invoice_context=True`)
- [ ] Update `action_fms_customer_invoices` to pass `fms_invoice_context=True` in context

### B3 — Vehicle ↔ Customer ↔ Driver auto-resolution
- [ ] `@api.onchange('fms_vehicle_id')`: auto-set `partner_id` from vehicle.partner_id if not set; auto-set `fms_driver_id` if vehicle has exactly one driver
- [ ] `@api.onchange('fms_driver_id')`: auto-set `partner_id` from driver.partner_id if not set; auto-set `fms_vehicle_id` if driver has exactly one vehicle
- [ ] `@api.constrains('fms_vehicle_id', 'partner_id')`: vehicle.partner_id must match invoice partner
- [ ] `@api.constrains('fms_driver_id', 'partner_id')`: driver.partner_id must match invoice partner

### B4 — Test results
- Tests run: N/A (run after implementation)
- Result: pending

---

## Phase C — hr.expense Extension (optional)

**Decision:** The existing `account.payment` with `fms_payment_context='expense'` already handles shift cash expenses and participates in reconciliation. Extending `hr.expense` would require adding `hr_expense` as a module dependency. Defer unless explicitly required. Mark as design decision.

- [-] Extend hr.expense — deferred; using account.payment/fms_payment_context='expense' instead
- [x] account.payment already extended with fms_shift_id, fms_attendant_id, fms_station_id, fms_payment_context
- [x] Expense payments link to shift and participate in cash reconciliation formula

---

## Phase D — Menu Restructuring

Target structure (from task spec):
```
Forecourt
├── Overview
├── Shifts (Operations → Shifts, Shift History)
├── Sales (Customer Invoices, Sales Receipts, Customer Payments)
├── Cash (Cash Movements, Expenses, Vendor Payments)
├── Inventory (Fuel Deliveries, Stock, Adjustments)
├── Customers & Fleet (Customers, Vehicles, Drivers)
└── Reports (Shift Reconciliation, Wetstock, Meter, Cash, Tank Loss, Sales, Customer Statements)
```

- [ ] Add `menu_fms_cash` structural menu (Cash section)
- [ ] Add `menu_fms_customers_fleet` structural menu (Customers & Fleet section)
- [ ] Move Credit Customers from Sales to Customers & Fleet
- [ ] Move Fleet Vehicles from Sales to Customers & Fleet
- [ ] Move Drivers from Sales to Customers & Fleet
- [ ] Move Shift Expenses, Vendor Payments, Cash Movements into Cash section
- [ ] Add Customers shortcut (res.partner filtered to fleet customers) under Customers & Fleet
- [ ] Remove `menu_fms_operations` cash-related items (moved to Cash section)
- [ ] Ensure Operations only contains: Shifts, Active Shift, Meter Readings, Dip Readings, Fuel Deliveries

---

## Phase E — Shift Sheet UX

- [ ] Audit existing view tabs for "orphan" operational forms
- [ ] Wetstock Summary tab: move to Reports, show only KPI summary on shift form
- [ ] Meter Reconciliation tab: move to Reports
- [ ] Keep meter_entry_ids and dip_entry_ids directly inside shift form (tab)
- [ ] Attendant Cash tab: stays (operational input)

---

## Phase F — Reporting Separation

Existing reports (read-only SQL views) already in fms_report_views.py:
- [x] R1 Shift Overview, R2 Tank Loss, R3 Wetstock, R4 Meter Reconciliation (SQL views)
- [x] R27 Attendant Cash Breakdown (SQL view, FIN-008)
- [ ] Confirm all reports are in Reports menu, not mixed with operational forms
- [ ] Add Customers & Fleet → Customer Statements menu (already has action_fms_ar_statement_report or similar)

---

## Phase G — Security & Performance
- [x] Company isolation on account.payment (IR rules — FIN-012)
- [x] Company isolation on fms.shift (record rules)
- [x] Composite index on account_payment (FIN-010)
- [ ] Confirm account.move FMS fields have company isolation (record rule or domain)
- [ ] Confirm fms.vehicle and fms.driver have company_id record rules

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
