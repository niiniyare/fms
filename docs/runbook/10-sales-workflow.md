# 10 — Sales Workflow

Audience: Supervisor, Accountant
Role required: `fms.group_fms_supervisor`

---

## Overview

FMS tracks two types of sales documents during a shift:

1. **Customer Invoice (`account.move`, `move_type=out_invoice`)** — for credit customers with fleet accounts. This is a native Odoo customer invoice, extended with FMS context fields.
2. **Sales Receipt (`fms.sales.receipt`)** — for immediate cash/MPesa/card walk-in sales.

Both link to an active shift (`fms_shift_id`) — **auto-populated when created from the Forecourt menu**.

---

## Canonical Data Sources

| Concept | Odoo Object | FMS Extension |
|---|---|---|
| Customer Invoice | `account.move (out_invoice)` | `fms_shift_id`, `fms_vehicle_id`, `fms_driver_id`, `fms_odometer` |
| Customer Payment | `account.payment` | `fms_shift_id`, `fms_attendant_id`, `fms_payment_context='customer_receipt'` |
| Expense | `account.payment` | `fms_shift_id`, `fms_attendant_id`, `fms_payment_context='expense'` |
| Vendor Payment | `account.payment` | `fms_shift_id`, `fms_attendant_id`, `fms_payment_context='vendor_payment'` |
| Cash Float | `account.payment` | `fms_shift_id`, `fms_payment_context='cash_float'` |
| Cash Drop | `account.payment` | `fms_shift_id`, `fms_payment_context='cash_drop'` |
| Fleet Customer | `res.partner` | `fms_is_fleet_customer=True`, `fms_credit_limit`, `fms_on_hold` |
| Vehicle | `fms.vehicle` | `partner_id` (fleet customer), `driver_ids` |
| Driver | `fms.driver` | `partner_id` (fleet customer), `vehicle_ids` |

There is no separate `fms.credit.customer` model. Credit customers are standard `res.partner` records with `fms_is_fleet_customer=True`.

---

## Sales Receipt (Fast Entry)

Lightweight, non-AR document for immediate sales. Auto-posts to `account.move` on confirmation.

1. **Forecourt → Sales → Sales Receipts → New**
2. Active shift auto-filled
3. Select attendant, products, payment method
4. Confirm → posts journal entry

**Blocked if no active shift.**

---

## Customer Invoice (Credit Customer)

Invoices are native Odoo `account.move` records. No separate model.

### Creating an Invoice from the Forecourt Menu

1. **Forecourt → Sales → Customer Invoices → New**
2. **Shift auto-populated** from company's active shift
3. **Invoice date auto-populated** from shift date
4. Select customer (fleet customer, `fms_is_fleet_customer=True`)
5. Select vehicle (optional — customer auto-fills from vehicle)
6. Select driver (optional — customer and vehicle auto-fill where unambiguous)
7. Enter odometer reading (optional)
8. Add product/fuel lines
9. Confirm (post)

**If no active shift exists**, creation is blocked:
> "No active shift — cannot create a customer invoice. Open a shift first, then create the invoice."

This block applies only when creating from the Forecourt menu (`fms_invoice_context=True`). Normal Accounting → Invoices creation is never blocked.

### Vehicle / Driver Auto-Resolution

| Action | Auto-populates |
|---|---|
| Select vehicle | Customer (if not yet set), Driver (if vehicle has exactly one driver) |
| Select driver | Customer (if not yet set), Vehicle (if driver has exactly one vehicle) |
| Multiple vehicles/drivers | User must select manually |

**Validation (hard constraints):**
- Vehicle's account holder must match the invoice customer
- Driver's linked customer must match the invoice customer
- Mismatches raise `ValidationError` — no silent override

### Credit Limit Control

- At 90% of limit: warning on invoice form
- At 100%: posting blocked unless supervisor enables `fms_limit_bypass` with reason
- On hold: posting always blocked

---

## Vehicle and Driver Management

**Forecourt → Customers & Fleet**

### fms.vehicle

| Field | Description |
|---|---|
| `license_plate` | Required, unique per company |
| `partner_id` | Account holder (fleet customer) |
| `driver_ids` | Authorised drivers |
| `fuel_type` | DX / UX / VP |

### fms.driver

| Field | Description |
|---|---|
| `name` | Driver name |
| `partner_id` | Linked fleet customer |
| `vehicle_ids` | Authorised vehicles |
| `employee_id` | Linked `hr.employee` if internal |

---

## Cash Movements

All non-AR cash movements are native `account.payment` records with `fms_payment_context`:

| Operation | Menu | Context value |
|---|---|---|
| Float to attendant | Forecourt → Cash → Cash Movements | `cash_float` |
| Cash drop to safe | Forecourt → Cash → Cash Movements | `cash_drop` |
| Expense from shift cash | Forecourt → Cash → Expenses | `expense` |
| Vendor payment from shift cash | Forecourt → Cash → Vendor Payments | `vendor_payment` |
| Customer receipt | Forecourt → Sales → Customer Payments | `customer_receipt` |

All payments with `fms_shift_id` set automatically participate in the shift cash reconciliation (see `03-daily-shift.md`).

---

## GL Impact

### Customer Invoice (credit sale)
```
DR  Accounts Receivable    invoice_total
CR  Revenue account        net_amount
CR  VAT Payable            tax_amount (if taxes configured)
```

### Customer Receipt
```
DR  Cash / MPesa / Bank    payment_amount
CR  Accounts Receivable    payment_amount
```
Adds to `total_in` in shift cash reconciliation.

### Expense (from shift cash)
```
DR  Expense account        amount
CR  Cash                   amount
```
Adds to `total_out` in shift cash reconciliation.
