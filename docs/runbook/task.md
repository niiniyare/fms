# FMS Financial Integration Tasks (FIN series)

**Owner:** FMS Development  
**Started:** 2026-08-18  
**Repo:** /home/niini/fms + /home/niini/fms_accounting  
**Odoo:** 18.0 Community  

Status legend: [ ] Not Started | [~] In Progress | [x] Complete | [!] Blocked

---

## FIN-001 — Native Invoice Integration

**Description:** Extend `account.move` with FMS fields. Already largely implemented in FMS Phase C2.  
Verify completeness, add any missing fields (dry-stock indicator, payment-method split).

**Affected models/files:**
- `fms_accounting/models/fms_shift_accounting.py` — `FMSAccountMoveExtension`
- `fms_accounting/models/fms_credit_customer.py` — `AccountMoveVehicle`

**Fields already implemented:**
- `fms_shift_id`, `fms_attendant_id`, `fms_vehicle_id`, `fms_driver_id`, `fms_station_id`
- `fms_vehicle` (Char legacy), `fms_driver` (hr.employee legacy)
- Credit limit: `fms_limit_bypass`, `fms_limit_bypass_reason`, `fms_limit_bypass_uid`

**Fields to add:**
- `fms_is_fuel_sale` (Boolean, computed: any line has fms_is_fuel product)

**Implementation status:** [x] Complete (fields exist, menu shortcut in FIN-011)  
**Tests required:** test_invoice_fms_fields, test_invoice_credit_limit_enforcement  
**Verification:** [ ]  
**Date completed:** 2026-08-18  
**Notes:** Legacy `fms_driver` (hr.employee) and `fms_driver_id` (fms.driver) both exist. Driver (Employee) label distinguishes them.

---

## FIN-002 — Customer Payment / Receipt Integration

**Description:** Extend `account.payment` with FMS context (shift, attendant, station). Customer receipts must feed into shift cash reconciliation and attendant balance.

**Affected models/files:**
- NEW: `fms_accounting/models/fms_payment_extension.py`
- `fms_accounting/models/__init__.py`
- `fms_accounting/security/ir_model_access.xml`
- `fms/models/fms_shift_entry.py` — `FMSShiftAttendantCash._compute_balance`
- `fms_accounting/views/fms_payment_views.xml` (NEW)

**Fields to add on account.payment:**
- `fms_shift_id` (Many2one fms.shift)
- `fms_attendant_id` (Many2one hr.employee)
- `fms_station_id` (related: fms_shift_id.company_id)
- `fms_payment_context` (Selection: customer_receipt / vendor_payment / cash_float / cash_drop / cash_pickup / other)

**Reconciliation impact:**
- `fms_payment_context = 'customer_receipt'` + `payment_type = 'inbound'` + posted → add to attendant `total_in`
- `fms_payment_context = 'vendor_payment'` + `payment_type = 'outbound'` + posted → add to attendant `total_out`
- `fms_payment_context = 'cash_float'` + posted → add to attendant/shift `total_in` (not revenue)
- `fms_payment_context = 'cash_drop'` + posted → reduce attendant `total_in` (cash moved to safe)

**Implementation status:** [ ] Not Started  
**Tests required:** test_customer_receipt_increases_cash, test_vendor_payment_decreases_cash, test_cash_float_not_revenue  
**Verification:** [ ]

---

## FIN-003 — Expense Integration

**Description:** Expenses paid from shift cash must reduce expected physical cash. Use `hr.expense` (payment_mode=company_account) or `account.payment` tagged as expense.

**Affected models/files:**
- NEW or extend `hr.expense` / `account.payment`
- `fms/models/fms_shift_entry.py` — expand `expense_amount` compute

**Current state:** `expense_amount` queries vendor bills (in_invoice) by date + shift ref — fragile ref-matching.

**Required change:** Link via `fms_shift_id` on `account.payment` with `fms_payment_context = 'expense'` OR extend `hr.expense` with `fms_shift_id`. Only `payment_mode = 'company_account'` affects physical cash.

**Implementation status:** [ ] Not Started  
**Tests required:** test_expense_company_account_reduces_cash, test_expense_own_account_no_effect  
**Verification:** [ ]

---

## FIN-004 — Vendor Payment Integration

**Description:** Vendor payments from shift cash reduce expected physical cash. Use `account.payment` with `fms_shift_id` + `fms_payment_context = 'vendor_payment'`.

**Affected models/files:**
- Same as FIN-002 (`fms_payment_extension.py`)
- `fms/models/fms_shift_entry.py`

**Implementation status:** [ ] Depends on FIN-002  
**Tests required:** test_vendor_payment_decreases_cash, test_vendor_bill_alone_no_effect  
**Verification:** [ ]

---

## FIN-005 — Cash Float Integration

**Description:** Opening/additional cash floats must be tracked per shift/attendant and included in reconciliation (they increase expected cash but are NOT revenue).

**Model:** `account.payment` with `fms_payment_context = 'cash_float'`.

**Affected models/files:**
- FIN-002 prerequisite
- `fms/models/fms_shift_entry.py` — add `float_amount` to attendant cash

**Implementation status:** [ ] Depends on FIN-002  
**Tests required:** test_float_increases_expected_cash_not_revenue  
**Verification:** [ ]

---

## FIN-006 — Cash Reconciliation Formula Expansion

**Description:** Expand `FMSShiftAttendantCash.balance` formula to include all cash-affecting transactions.

**New formula:**
```
expected_cash =
  reported_sales (meter elec_cash_sold)
  + customer_receipts (account.payment inbound, fms_shift+attendant, posted)
  + float_received (account.payment fms_payment_context=cash_float, posted)
  - cash_dropped (account.payment fms_payment_context=cash_drop, posted)
  - mpesa_amount (digital payments via POS)
  - card_amount (card payments via POS)
  - ar_amount (credit/AR sales via POS)
  - expense_amount (vendor_payment/expense from cash)
  - vendor_payment_amount (outbound payments from shift cash)

variance = cash_collected - expected_cash
balance = expected_cash - cash_collected  (must = 0)
```

**Affected models/files:**
- `fms/models/fms_shift_entry.py` — `FMSShiftAttendantCash`
- New computed fields: `customer_receipt_amount`, `float_amount`, `cash_drop_amount`, `vendor_payment_amount`

**Implementation status:** [ ] Depends on FIN-002  
**Tests required:** test_full_reconciliation_formula, test_balance_zero_on_clean_shift  
**Verification:** [ ]

---

## FIN-007 — Meter + Dry-Stock + Sales Reconciliation

**Description:** Reconcile three dimensions: Volume (meters), Sales (invoices+receipts), Cash (formula above). Distinguish cash/credit/digital per payment method.

**Implementation status:** [~] Partial — Gate 6 checks meter vs invoice+receipt. Dry-stock aggregation not yet separate.  
**Tests required:** test_cash_sale_vs_credit_sale_distinction  
**Verification:** [ ]

---

## FIN-008 — Attendant Cash Reconciliation per Transaction Type

**Description:** Per-attendant reconciliation report showing breakdown by: fuel sales, dry-stock, customer receipts, expenses, vendor payments, floats, drops, expected, declared, variance.

**Implementation status:** [ ] Depends on FIN-006  
**Tests required:** test_attendant_breakdown_correct  
**Verification:** [ ]

---

## FIN-009 — Shift Close Gates (full 18-gate pipeline)

**Description:** Expand from 8 to 18 gate checks. New gates:
- G9: Dry-stock sales reconciliation (meter vs dry-stock invoice lines)
- G10: Customer receipt vs invoiced amount
- G11: Float reconciliation
- G12: Expense reconciliation
- G13: Vendor payment reconciliation
- G14: Digital payment reconciliation
- G15: Unresolved blocking exceptions check

**Implementation status:** [ ] Depends on FIN-002, FIN-006  
**Tests required:** test_each_gate_blocks_on_failure  
**Verification:** [ ]

---

## FIN-010 — SQL Optimization

**Description:** Payment aggregations added in FIN-006 must use SQL, not N+1 ORM.

**Implementation status:** [ ] After FIN-006  
**Verification:** [ ]

---

## FIN-011 — Menu Shortcuts (ALL)

**Description:** Add Forecourt menu shortcuts to native Odoo:
- Forecourt → Sales → Customer Invoices (account.move out_invoice list)
- Forecourt → Sales → Customer Payments (account.payment inbound)
- Forecourt → Cash → Expenses (hr.expense or account.move in_invoice)
- Forecourt → Cash → Vendor Payments (account.payment outbound)
- Forecourt → Cash → Cash Drops
- Forecourt → Cash → Cash Pickups
- Reorganize menu to spec structure

**Implementation status:** [ ] Not Started  
**Files:** `fms/views/fms_menus.xml`, `fms_accounting/views/fms_accounting_menus.xml`  
**Verification:** [ ]

---

## FIN-012 — Security

**Description:** Record rules for `account.payment.fms_shift_id` — company isolation. Verify all new fields respect env.company.

**Implementation status:** [ ] After FIN-002  
**Files:** `fms/security/ir_rule.xml`, `fms_accounting/security/`  
**Verification:** [ ]

---

## FIN-013 — Tests

**Description:** Full test suite for FIN-001 through FIN-012.

**Implementation status:** [ ] After all above  
**Verification:** [ ]

---

## FIN-014 — Documentation Verification

**Description:** Update all runbooks to reflect new financial integration. Verify task.md is accurate.

**Implementation status:** [~] In Progress (runbooks being updated as implementation proceeds)  
**Verification:** [ ]

---

## Implementation Log

| Date | Task | Result | Notes |
|------|------|--------|-------|
| 2026-08-18 | task.md created | Complete | FIN-001 to FIN-014 mapped |
| 2026-08-18 | Phase C1-C3 (prev session) | Complete | Gates, vehicle/driver, attendant modes |
