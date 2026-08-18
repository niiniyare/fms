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

## Phase A — Audit (COMPLETE)

Audit report generated from:
- All ./docs/runbook/*.md files
- All models, security, reports, SQL views, tests
- Reconciled against actual implementation

Key findings:
1. Core shift state machine, gates 1-5, GL posting, residual allocation all implemented.
2. Meter logs + dip logs immutable — enforced at ORM level.
3. Company scoping (record rules) implemented for all FMS models.
4. COGS missing = WARNING not ERROR — residual allocations silently skip.
5. Clearing account + FMS journal have silent name-search fallbacks.
6. No Electronic vs Manual ±1L gate (three-meter reconciliation missing).
7. No Electronic vs Cash configurable threshold gate.
8. Meter entry amount uses product.list_price not price period.
9. No disputed shift concurrency control.
10. No failed-close audit logging.
11. No emergency override mechanism.
12. No dip capacity validation.
13. No Sales Receipt model (fms_accounting has stub, incomplete).
14. No Vehicle or Driver model.
15. No two-mode attendant assignment.
16. No meter vs invoice+receipt reconciliation gate.
17. Tank loss source analysis missing.
18. Wetstock / cash reconciliation are inline views, not proper read-only reports.

---

## Phase B — Gap Matrix (COMPLETE)

See audit output. Gaps prioritized in Phases C-I below.

---

## Phase C-1 — Critical Business Logic

### C1.1 — Elevate COGS missing from warning to error
- **Status:** [ ]
- **Docs:** ./docs/runbook/08-gl-and-accounting.md
- **Files:** models/fms_setup_check.py, docs/runbook/08-gl-and-accounting.md
- **Problem:** `no_cogs` issues added as 'warning' → gate_check_gl_config only blocks on errors → residual allocation journals silently skip COGS posting
- **Fix:** Change COGS missing to 'error' level so GL config gate blocks shift close.
- **Tests:** test_gl_config_gate_blocks_on_missing_cogs
- **Verification:** [ ]

### C1.2 — Remove silent fallback in _get_fms_journal / _get_clearing_account
- **Status:** [ ]
- **Docs:** ./docs/runbook/08-gl-and-accounting.md, ./docs/runbook/02-configuration.md
- **Files:** models/fms_shift.py (lines 1043-1095)
- **Problem:** If journal/clearing not configured, system silently falls back to name-search → wrong account used without warning.
- **Fix:** Both methods should raise ValidationError immediately if not explicitly configured in site preferences. Remove name-search fallbacks.
- **Tests:** test_journal_required_in_prefs, test_clearing_account_required_in_prefs
- **Verification:** [ ]

### C1.3 — Three-meter reconciliation: Electronic vs Manual ±1L gate
- **Status:** [ ]
- **Docs:** ./docs/runbook/03-daily-shift.md (add section), ./docs/runbook/09-field-reference.md
- **Files:** models/fms_shift.py (add _gate_check_meter_elec_vs_manual), models/fms_shift_entry.py
- **Problem:** No gate validates that Electronic volume ≈ Manual volume within ±1L per nozzle. Three-meter reconciliation completely absent.
- **Fix:** Add _gate_check_meter_elec_vs_manual() called in gate sequence before gates 1-5. Block if any nozzle |elec_vol - manual_vol| > 1.0L.
- **Tests:** test_gate_elec_vs_manual_blocks_on_variance, test_gate_elec_vs_manual_passes_within_tolerance
- **Verification:** [ ]

### C1.4 — Electronic vs Cash configurable threshold gate
- **Status:** [ ]
- **Docs:** ./docs/runbook/03-daily-shift.md (update gate table), ./docs/runbook/02-configuration.md
- **Files:** models/fms_site_preferences.py, models/fms_shift.py, docs/runbook/02-configuration.md
- **Problem:** No gate for Electronic volume vs Cash meter discrepancy per nozzle. Gate 2 only validates aggregate POS vs meter totals.
- **Fix:** Add fms_elec_vs_cash_threshold_l (Float, default 5.0L) to site prefs. Add _gate_check_meter_elec_vs_cash(). Block if any nozzle |elec_vol - cash_meter_vol| > threshold.
- **Note:** cash_meter_vol = (closing_elec_cash - opening_elec_cash) / price_period_price
- **Tests:** test_gate_elec_vs_cash_configurable, test_gate_elec_vs_cash_blocks
- **Verification:** [ ]

### C1.5 — Price period usage in meter entry amount calculation
- **Status:** [ ]
- **Docs:** ./docs/runbook/09-field-reference.md (Amount column), ./docs/runbook/03-daily-shift.md
- **Files:** models/fms_shift_entry.py (line 108-111), models/fms_price_period.py
- **Problem:** amount_elec computed as qty_sold_elec × product.list_price. Should use active price period for shift date.
- **Fix:** Compute amount_elec using FMSPricePeriodLine.get_price(product, shift.date) or equivalent. Add @api.depends on shift.date + price period.
- **Tests:** test_amount_uses_price_period_not_list_price
- **Verification:** [ ]

### C1.6 — Disputed shift concurrency control
- **Status:** [ ]
- **Docs:** ./docs/runbook/03-daily-shift.md (add disputed state docs), ./docs/runbook/02-configuration.md
- **Files:** models/fms_shift.py, models/fms_site_preferences.py, security/ir_rule.xml
- **Problem:** No 'disputed' state defined. No concurrency rule for disputed shifts.
- **Fix:** Add 'disputed' to state selection. Add fms_allow_multiple_disputed (Boolean, default False) to site prefs. Enforce in create/write: if disputed shift exists and !allow_multiple → raise ValidationError.
- **Tests:** test_disputed_shift_single_default, test_disputed_shift_multiple_allowed_by_config
- **Verification:** [ ]

### C1.7 — Failed close audit logging
- **Status:** [ ]
- **Docs:** ./docs/runbook/06-administration.md (add audit section)
- **Files:** models/fms_shift.py (action_close_shift), new model fms.shift.close.attempt or chatter
- **Problem:** Gate failures raise ValidationError but not logged. Cannot audit who tried to close, when, and why it failed.
- **Fix:** Before gate sequence, record attempt. On ValidationError, catch and log to chatter (mail.thread) with: user, timestamp, gate name, failure message. Re-raise original error.
- **Tests:** test_failed_close_logged_to_chatter
- **Verification:** [ ]

### C1.8 — Emergency override with audit trail
- **Status:** [ ]
- **Docs:** ./docs/runbook/04-gate-failures.md (add emergency override section)
- **Files:** models/fms_shift.py, new wizard fms_emergency_override_wizard.py, security/fms_groups.xml
- **Problem:** No emergency override mechanism. Runbook says sysadmin shell reset — not audited.
- **Fix:** Add action_emergency_override_close() restricted to fms.group_fms_accountant. Requires: explicit reason (text), approver (hr.employee). Creates immutable fms.shift.override record. Skips gates but records all gate failures. Shift marked 'closed_override'. Override visible in reporting.
- **Tests:** test_emergency_override_requires_accountant, test_emergency_override_audit_record_created, test_emergency_override_supervisor_blocked
- **Verification:** [ ]

### C1.9 — Dip capacity validation
- **Status:** [ ]
- **Docs:** ./docs/runbook/09-field-reference.md
- **Files:** models/fms_shift_entry.py (_constrains on closing_volume)
- **Problem:** closing_volume can exceed tank capacity (fms_tank_capacity_l on stock.location). Audit log records physically impossible values.
- **Fix:** Add @api.constrains('closing_volume') on FMSShiftDipEntry: if location.fms_tank_capacity_l and closing_volume > location.fms_tank_capacity_l → raise ValidationError.
- **Tests:** test_dip_exceeds_capacity_blocked
- **Verification:** [ ]

### C1.10 — Security ACL corrections
- **Status:** [ ]
- **Docs:** ./docs/runbook/06-administration.md (security section)
- **Files:** security/ir_model_access.csv
- **Problem 1:** ACL grants supervisor create on fms.meter_log — runbook says logs written only at shift close, not manually.
- **Problem 2:** Attendant can write all fields on own attendant_cash line, not just cash_collected.
- **Fix:** Restrict fms.meter_log create to supervisor only via system action (not UI). Add field-level readonly on attendant_cash (supervisor field) for attendant.
- **Tests:** test_attendant_cannot_manually_create_meter_log
- **Verification:** [ ]

### C1.11 — Concurrent shift edit protection
- **Status:** [ ]
- **Docs:** ./docs/runbook/07-troubleshooting.md (add concurrent edit section)
- **Files:** models/fms_shift.py (action_start_closing, action_close_shift)
- **Problem:** Two supervisors editing simultaneously = last-save-wins. No detection.
- **Fix:** On action_start_closing and action_close_shift, use write_date optimistic locking: read write_date before operation, compare at start of action, raise ConcurrencyError if changed.
- **Tests:** test_concurrent_close_raises_error
- **Verification:** [ ]

---

## Phase C-2 — Sales Integration

### C2.1 — Document Invoice + Sales Receipt workflow
- **Status:** [ ]
- **Docs:** Create ./docs/runbook/10-sales-workflow.md
- **Files:** docs/runbook/10-sales-workflow.md
- **Problem:** No runbook document for sales workflow.
- **Fix:** Write complete runbook for Invoice + Sales Receipt, attendant, vehicle, driver, shift linking.
- **Verification:** [ ]

### C2.2 — Extend account.move with FMS fields
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/fms_shift_accounting.py
- **Fix:** Add to account.move: fms_shift_id, fms_attendant_id, fms_vehicle_id, fms_driver_id, fms_station_id
- **Tests:** test_invoice_fms_fields
- **Verification:** [ ]

### C2.3 — Vehicle model
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/fms_vehicle.py (new)
- **Fix:** Create fms.vehicle: license_plate (required, unique per company), make, model, year, partner_id (customer), fuel_type, active, company_id
- **Tests:** test_vehicle_create, test_vehicle_company_scoped
- **Verification:** [ ]

### C2.4 — Driver model
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/fms_driver.py (new) or extend hr.employee
- **Fix:** Create fms.driver: name, license_no, partner_id, vehicle_ids (M2M to fms.vehicle), employee_id (optional), company_id
- **Tests:** test_driver_create, test_driver_vehicle_relationship
- **Verification:** [ ]

### C2.5 — Extend res.partner with FMS fields
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/ or fms/models/fms_shift.py _inherit res.partner
- **Fix:** Add to res.partner: fms_is_fleet_customer (Boolean), fms_credit_limit (Float), fms_outstanding_balance (computed)
- **Verification:** [ ]

### C2.6 — Sales Receipt model
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/fms_sales_receipt.py
- **Problem:** Stub exists but incomplete. Must be QuickBooks-style fast entry.
- **Fix:** Complete fms.sales.receipt: shift_id (auto from active shift), attendant_id (auto from nozzle/context), partner_id, vehicle_id, driver_id, line_ids, payment_method, total, state (draft/posted). Auto-post to account.move on confirm.
- **Tests:** test_receipt_creates_account_move, test_receipt_requires_active_shift
- **Verification:** [ ]

### C2.7-C2.9 — Sales linked to shift/attendant/vehicle/driver
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Fix:** Enforce fms_shift_id on both invoice and receipt. Auto-populate from context where possible.
- **Verification:** [ ]

### C2.10 — Meter vs Invoice+Receipt reconciliation gate
- **Status:** [ ]
- **Docs:** ./docs/runbook/03-daily-shift.md (add Gate 6), ./docs/runbook/10-sales-workflow.md
- **Files:** models/fms_shift.py
- **Problem:** No gate comparing meter_qty vs (invoice_qty + receipt_qty) per product.
- **Fix:** Add Gate 6: _gate_check_meter_vs_sales(). For each fuel product: meter_vol = sum(meter_entry qty). sales_vol = sum(invoice lines + receipt lines for shift). Block if |meter_vol - sales_vol| > tolerance.
- **Note:** Configurable tolerance (same meniscus or separate config).
- **Tests:** test_gate_meter_vs_sales_blocks, test_gate_meter_vs_sales_passes
- **Verification:** [ ]

### C2.11 — Dry-stock sales in reconciliation
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Fix:** Sales reconciliation report includes non-fuel products. Meter reconciliation gate only applies to fuel products.
- **Verification:** [ ]

### C2.12 — Prevent sales outside active shift
- **Status:** [ ]
- **Docs:** ./docs/runbook/10-sales-workflow.md
- **Files:** fms_accounting/models/fms_sales_receipt.py, fms_shift_accounting.py
- **Fix:** On receipt/invoice create: validate active shift exists for company. Raise ValidationError if no open shift.
- **Tests:** test_receipt_blocked_without_active_shift
- **Verification:** [ ]

---

## Phase C-3 — Attendant Assignment

### C3.1 — Document both assignment modes
- **Status:** [ ]
- **Docs:** Create ./docs/runbook/11-attendant-assignment.md
- **Verification:** [ ]

### C3.2 — Add assignment-mode config to site preferences
- **Status:** [ ]
- **Files:** models/fms_site_preferences.py, views/fms_site_preferences_views.xml
- **Fix:** Add attendant_assignment_mode Selection('pre_assigned', 'per_nozzle') default 'per_nozzle'
- **Verification:** [ ]

### C3.3 — Pre-assigned mode
- **Status:** [ ]
- **Files:** models/fms_pump.py (fms_default_attendant_id on nozzle), models/fms_shift.py
- **Fix:** If mode=pre_assigned: _populate_opening_entries copies nozzle.fms_default_attendant_id → meter_entry.attendant_id. Supervisor confirms/changes before ops start.
- **Verification:** [ ]

### C3.4 — Per-nozzle attendant mode
- **Status:** [ ]
- **Files:** models/fms_shift_entry.py, views/fms_shift_meter_views.xml
- **Fix:** attendant_id editable on each meter entry row. Required before Start Closing if mode=per_nozzle.
- **Verification:** [ ]

### C3.5-C3.9 — Attendant on nozzle, invoice, receipt; validate; reporting
- **Status:** [ ]
- **Verification:** [ ]

---

## Phase D — Operational UX

### D4.1 — Remove opening-reading manual entry from meter view
- **Status:** [ ]
- **Docs:** ./docs/runbook/03-daily-shift.md
- **Files:** views/fms_shift_meter_views.xml, views/fms_shift_views.xml
- **Fix:** Hide opening_elec_volume/opening_elec_cash/opening_man_mech from default view. Show as read-only stat in context. User only enters closing reading.
- **Verification:** [ ]

### D4.2 — Auto-load running meter balances
- **Status:** [ ]
- **Problem:** Opening readings already auto-populated on shift open. UX issue is they're visible as editable. Fix is D4.1.
- **Verification:** [ ]

### D4.3 — Auto-load tank opening dips
- **Status:** [ ]
- **Problem:** Already implemented in _populate_opening_entries. UX: show as read-only. Fix in D4.1 scope.
- **Verification:** [ ]

### D4.4-D4.10 — UX cleanup
- **Status:** [ ]
- **Fix:** Meter entry: show current meter as header stat, only show closing entry field + RTT. Dip: show opening as stat, only enter closing. Shift close: show blocker panel listing all gate failures with direct links.
- **Verification:** [ ]

---

## Phase E — Reporting

### E5.1 — Wetstock read-only report (SQL view)
- **Status:** [ ]
- **Docs:** ./docs/runbook/05-reports.md
- **Files:** models/fms_report_views.py (add fms_report_wetstock), views/fms_report_views2.xml
- **Fix:** SQL view: GROUP BY company/shift/tank/product. Columns: opening_vol, deliveries, meter_sold, theoretical_close, actual_close (dip), variance_l, variance_pct, tolerance, status.
- **Verification:** [ ]

### E5.2 — Cash reconciliation read-only report (SQL view)
- **Status:** [ ]
- **Fix:** SQL view: GROUP BY company/shift/attendant. Fuel/dry-stock/invoice/receipt sales, cash, equivalents, variance, status.
- **Verification:** [ ]

### E5.3 — Meter reconciliation report
- **Status:** [ ]
- **Fix:** Per nozzle: elec vol, manual vol, cash meter vol, variance elec-manual, variance elec-cash. Links to source entries.
- **Verification:** [ ]

### E5.4 — Tank loss source report
- **Status:** [ ]
- **Fix:** Correlate tank variance with meter variances, sales variances, delivery variances. Show breakdown of explained vs unexplained loss per source.
- **Verification:** [ ]

### E5.5-E5.9 — Remaining reports + company scoping
- **Status:** [ ]
- **Verification:** [ ]

---

## Phase F — Native Odoo Integration

### F6.1-F6.10 — Model extensions
- **Status:** [ ]
- **Fix:** Systematic extension of product, stock.location, stock.move, stock.picking, account.move, pos models with FMS fields where missing.
- **Verification:** [ ]

---

## Phase G — Performance

### G7.1-G7.7 — SQL + Index optimization
- **Status:** [ ]
- **Fix:** Audit all SQL views for missing indexes. Add composite indexes on (company_id, shift_id), (shift_id, product_id) etc. Verify EXPLAIN ANALYZE on heavy queries.
- **Verification:** [ ]

---

## Phase H — Security & Compliance

### H8.1-H8.10 — Full security audit and hardening
- **Status:** [ ]
- **Fix:** Verify all ACLs, record rules, ORM enforcement. Attempt bypass via direct ORM calls. Fix any gaps.
- **Verification:** [ ]

---

## Phase I — Testing

### I9.1-I9.13 — Full test suite
- **Status:** [ ]
- **Verification:** [ ]

---

## Implementation Log

| Date | Task | Result | Notes |
|------|------|--------|-------|
| 2026-08-18 | Phase A audit | Complete | 15 gaps identified |
| 2026-08-18 | task.md created | Complete | All phases mapped |
