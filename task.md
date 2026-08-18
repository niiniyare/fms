# FMS Implementation Task Tracker

**Started:** 2026-08-18  
**Repository:** /home/niini/fms (+ /home/niini/fms_accounting)  
**Odoo version:** 18.0  

---

## Status Legend

- [ ] Not started
- [~] In progress
- [x] Implemented and verified
- [!] Blocked
- [-] Not applicable / intentionally rejected

---

## Phase A — Audit [x]

Audit report generated from all models, security, reports, SQL views, docs, tests.

Key findings (18 gaps):
1. COGS missing = WARNING not ERROR
2. Silent fallback in _get_fms_journal / _get_clearing_account
3. No Electronic vs Manual ±1L gate
4. No Electronic vs Cash configurable threshold gate
5. Meter entry amount uses list_price not price period
6. No disputed shift concurrency control
7. No failed-close audit logging
8. No emergency override mechanism
9. No dip capacity validation
10. ACL: supervisor create on meter_log was wrong
11. No concurrent shift edit protection
12. No Sales workflow runbook
13. account.move missing FMS fields
14. No Vehicle or Driver model
15. No two-mode attendant assignment
16. No meter vs invoice+receipt reconciliation gate
17. Tank loss source analysis missing
18. Wetstock/cash reconciliation not proper read-only reports

---

## Phase B — Gap Matrix [x]

Gaps prioritized in Phases C-I below.

---

## Phase C-1 — Critical Business Logic [x]

### C1.1 — Elevate COGS missing from warning to error [x]
- **Files:** models/fms_setup_check.py (line 258-265)

### C1.2 — Remove silent fallback in _get_fms_journal / _get_clearing_account [x]
- **Files:** models/fms_shift.py

### C1.3 — Three-meter reconciliation: Electronic vs Manual ±1L gate [x]
- **Files:** models/fms_shift.py (_gate_check_meter_elec_vs_manual)

### C1.4 — Electronic vs Cash configurable threshold gate [x]
- **Files:** models/fms_site_preferences.py (elec_vs_cash_threshold_l), models/fms_shift.py

### C1.5 — Price period usage in meter entry amount calculation [x]
- **Files:** models/fms_shift_entry.py (_get_shift_price, _compute_amount)

### C1.6 — Disputed shift concurrency control [x]
- **Files:** models/fms_shift.py (disputed state), models/fms_site_preferences.py (allow_multiple_disputed)

### C1.7 — Failed close audit logging to chatter [x]
- **Files:** models/fms_shift.py (gate loop logs to chatter)

### C1.8 — Emergency override with audit trail [x]
- **Files:** wizards/fms_emergency_override_wizard.py, models/fms_shift.py

### C1.9 — Dip capacity validation [x]
- **Files:** models/fms_shift_entry.py (_check_closing_volume_capacity)

### C1.10 — Security ACL corrections [x]
- **Files:** security/ir_model_access.xml

### C1.11 — Concurrent shift edit protection [x]
- **Files:** models/fms_shift.py (write_date optimistic locking)

---

## Phase C-2 — Sales Integration [x]

### C2.1 — Sales workflow runbook [x]
- **Files:** docs/runbook/10-sales-workflow.md

### C2.2 — Extend account.move with FMS fields [x]
- **Files:** fms_accounting/models/fms_shift_accounting.py (FMSAccountMoveExtension)

### C2.3 — Vehicle model [x]
- **Files:** fms_accounting/models/fms_vehicle.py

### C2.4 — Driver model [x]
- **Files:** fms_accounting/models/fms_driver.py

### C2.5 — Extend res.partner with FMS fields [x]
- **Files:** fms_accounting/models/fms_credit_customer.py (fms_is_fleet_customer)

### C2.6 — Sales Receipt model [~]
- **Files:** fms_accounting/models/fms_sales_receipt.py (stub exists, incomplete)
- **Note:** Auto-post to account.move on confirm not yet wired

### C2.7-C2.9 — Sales linked to shift/attendant/vehicle/driver [x]
- **Files:** fms_accounting/models/fms_shift_accounting.py

### C2.10 — Meter vs Invoice+Receipt reconciliation gate (Gate 6) [x]
- **Files:** models/fms_shift.py (_gate_check_meter_vs_sales)

### C2.11 — Dry-stock sales in reconciliation [~]
- **Note:** Gate applies to fuel products only — dry-stock aggregation not yet separated (FIN-007)

### C2.12 — Prevent sales outside active shift [x]
- **Files:** fms_accounting/models/fms_shift_accounting.py

---

## Phase C-3 — Attendant Assignment [x]

### C3.1 — Document both assignment modes [x]
- **Files:** docs/runbook/ (updated shift docs)

### C3.2 — Add assignment-mode config to site preferences [x]
- **Files:** models/fms_site_preferences.py (attendant_assignment_mode)

### C3.3 — Pre-assigned mode [x]
- **Files:** models/fms_pump.py (default_attendant_id), models/fms_shift.py (_populate_opening_entries)

### C3.4 — Per-nozzle attendant mode [x]
- **Files:** models/fms_shift.py (gate checks attendant assigned before close)

---

## Phase D — Operational UX

### D4.1 — Hide opening readings in meter view [x]
- **Note:** Opening fields are read-only, not editable in meter entry form

### D4.2-D4.3 — Auto-load running meter/dip balances [x]
- **Note:** Already implemented in _populate_opening_entries

### D4.4-D4.10 — UX cleanup [ ]
- **Fix:** Shift close blocker panel listing all gate failures with direct links

---

## Phase E — Reporting

### E5.1 — Wetstock read-only report (SQL view) [ ]

### E5.2 — Cash reconciliation read-only report (SQL view) [ ]

### E5.3 — Meter reconciliation report [ ]

### E5.4 — Tank loss source report [ ]

### E5.5-E5.9 — Remaining reports + company scoping [ ]

---

## Phase F — Native Odoo Integration

### F6.1-F6.10 — Model extensions [~]
- account.move, account.payment extended (FIN-001/002)
- hr.employee extended (fms_is_attendant)
- res.partner extended (fms_is_fleet_customer)
- Remaining: product, stock.location, stock.move extensions

---

## Phase G — Performance

### G7.1 — Index audit and addition [~]
- shift company_id, state indexed
- FK indexes added on all child model shift_id fields
- Remaining: composite indexes on heavy query patterns

---

## Phase H — Security & Compliance

### H8.1-H8.10 — Full security audit and hardening [ ]

---

## Phase I — Testing

### I9.1-I9.13 — Full test suite [ ]

---

## FIN Series — Native Odoo Accounting Integration

Spec: 23-section "Native Odoo Accounting Integration" (received 2026-08-18).  
Constraint: extend Odoo native models, no parallel FMS accounting models.

### FIN-001 — Native Invoice Integration [x]
- account.move extended: fms_shift_id, fms_attendant_id, fms_vehicle_id, fms_driver_id, fms_station_id
- **Files:** fms_accounting/models/fms_shift_accounting.py, fms_accounting/models/fms_credit_customer.py
- **Date:** 2026-08-18

### FIN-002 — Customer Payment / Receipt Integration [x]
- account.payment extended: fms_shift_id, fms_attendant_id, fms_station_id, fms_payment_context
- Constraints: company match, shift not closed
- **Files:** fms_accounting/models/fms_payment_extension.py
- **Date:** 2026-08-18

### FIN-003 — Expense Integration [x]
- Covered by fms_payment_context='expense' on account.payment
- Replaces fragile in_invoice date+ref matching
- **Files:** models/fms_shift_entry.py (_compute_from_payments)
- **Date:** 2026-08-18

### FIN-004 — Vendor Payment Integration [x]
- Covered by fms_payment_context='vendor_payment' on account.payment
- **Files:** fms_accounting/models/fms_payment_extension.py
- **Date:** 2026-08-18

### FIN-005 — Cash Float Integration [x]
- Covered by fms_payment_context='cash_float' on account.payment
- **Files:** models/fms_shift_entry.py (float_amount computed field)
- **Date:** 2026-08-18

### FIN-006 — Cash Reconciliation Formula Expansion [x]
- total_in = reported_sales + customer_receipts + float - cash_drops
- total_out = cash_collected + mpesa + card + ar + vendor_payments + expenses
- SQL-aggregated via _compute_from_payments (no N+1)
- **Files:** models/fms_shift_entry.py
- **Date:** 2026-08-18

### FIN-007 — Meter + Dry-Stock + Sales Reconciliation [ ]
- Dry-stock aggregation not yet separated from fuel in gate logic
- Gate 6 checks meter vs invoice+receipt (fuel only)

### FIN-008 — Attendant Cash Reconciliation per Transaction Type [ ]
- Per-attendant breakdown report: fuel/dry-stock/receipts/expenses/vendor/floats/drops

### FIN-009 — Shift Close Gates (full 18-gate pipeline) [~]
- Current: 8 gates + concurrency check
- **In progress:** expanding to 18 gates (G9-G15 new)

### FIN-010 — SQL Optimization [ ]
- Payment aggregations already use SQL (_compute_from_payments)
- Remaining: audit all SQL views for missing composite indexes

### FIN-011 — Menu Shortcuts [x]
- Customer Receipts, Vendor Payments, Cash Floats, Cash Drops, Shift Expenses menus added
- **Files:** fms_accounting/views/fms_payment_views.xml, fms_accounting/views/fms_accounting_menus.xml
- **Date:** 2026-08-18

### FIN-012 — Security (account.payment company isolation) [x]
- Record rules: supervisor own-company, attendant own-payments-only
- **Files:** fms_accounting/security/ir_rule.xml
- **Date:** 2026-08-18

### FIN-013 — Full Test Suite [ ]

### FIN-014 — Documentation Verification [ ]

---

## Implementation Log

| Date | Task | Result | Notes |
|------|------|--------|-------|
| 2026-08-18 | Phase A audit | Complete | 18 gaps identified |
| 2026-08-18 | Phase C1 (11 tasks) | Complete | COGS gate, three-meter, emergency override, chatter, disputed shifts, etc. |
| 2026-08-18 | Phase C2 (8 tasks) | Mostly complete | Vehicle/Driver/Gate 6/account.move fields. C2.6 stub incomplete. |
| 2026-08-18 | Phase C3 (4 tasks) | Complete | Attendant assignment modes |
| 2026-08-18 | Phase G7 (indexes) | Partial | FK + state indexes added |
| 2026-08-18 | FIN-001 | Complete | account.move FMS fields |
| 2026-08-18 | FIN-002/003/004/005 | Complete | account.payment extension + all contexts |
| 2026-08-18 | FIN-006 | Complete | Expanded cash reconciliation formula, SQL aggregation |
| 2026-08-18 | FIN-011 | Complete | 5 menu shortcuts added |
| 2026-08-18 | FIN-012 | Complete | Record rules for account.payment |
