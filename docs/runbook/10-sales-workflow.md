# 10 — Sales Workflow

Audience: Supervisor, Accountant
Role required: `fms.group_fms_supervisor`

---

## Overview

FMS tracks two types of sales documents during a shift:

1. **Invoice (account.move, move_type=out_invoice)** — for credit customers with fleet accounts
2. **Sales Receipt (fms.sales.receipt)** — for cash/MPesa/card walk-in sales

Both documents link to:
- An active shift (`fms_shift_id`)
- An attendant (`fms_attendant_id`)
- Optionally a vehicle (`fms_vehicle_id`) and driver (`fms_driver_id`)

---

## Sales Receipt (Fast Entry)

Sales Receipt is a lightweight, non-AR document for immediate sales.
It auto-posts to `account.move` as an out-receipt on confirmation.

### Creating a Receipt

1. Go to **Forecourt → Operations → New Receipt**
2. Active shift is auto-filled from company's open shift
3. Select attendant (defaults to current user's linked employee)
4. Add product lines
5. Select payment method: Cash / MPesa / Card / Shell Card
6. Confirm → auto-posts journal entry

### Requirements

- An active shift must exist for the company
- Attendant is required
- Payment method is required

### Blocking rule

If no shift is open: receipt creation raises `ValidationError`.
After shift closes: receipt can no longer be created for that shift.

---

## Invoice (Credit Customer)

Invoices are used for fleet/credit accounts where payment is deferred.

### Creating an Invoice

1. Go to **Accounting → Customers → Invoices → New**
2. Set customer to a fleet customer (`fms_is_fleet_customer = True`)
3. Add fuel/product lines
4. Set FMS fields: Shift, Attendant, Vehicle, Driver
5. Confirm (post)

### Fleet Customer Setup

A fleet customer has:
- `fms_is_fleet_customer = True` on their `res.partner` record
- Credit limit set (warning when exceeded)
- Optional fleet card reference

---

## Vehicle and Driver

### Vehicle (`fms.vehicle`)

Tracks vehicles that purchase fuel on credit.

| Field | Description |
|---|---|
| `license_plate` | Required, unique per company |
| `make`, `model`, `year` | Vehicle description |
| `partner_id` | Account holder (fleet customer) |
| `fuel_type` | DX / UX / VP |

### Driver (`fms.driver`)

| Field | Description |
|---|---|
| `name` | Driver name |
| `license_no` | Driving licence number |
| `partner_id` | Optional linked customer |
| `vehicle_ids` | Vehicles this driver operates |
| `employee_id` | Linked hr.employee if internal driver |

---

## Attendant Assignment Modes

**Per-Nozzle (default):** Attendant set on each meter entry row. Required before closing.

**Pre-Assigned:** Default attendant set on nozzle. Auto-populated when shift opens. Supervisor confirms/changes.

Mode configured in: Forecourt → Configuration → Site Preferences → Attendant Assignment Mode.

---

## Meter vs Invoice+Receipt Gate (Gate 6)

On shift close, after gates 1-5, Gate 6 checks:
- Sum of fuel volume on closed invoices + posted receipts (for shift)
- Must match sum of meter entry qty_sold_elec per fuel product
- Tolerance: same as meniscus (configurable in site prefs)

If variance exceeds tolerance, shift close is blocked.

---

## Dry-Stock Sales

Non-fuel products (lubricants, accessories) appear in invoices and receipts but are excluded from the meter reconciliation gate. They are included in the cash reconciliation (attendant balance).

---

## Sales Without Active Shift

Any attempt to create a Sales Receipt when no shift is open raises:

```
ValidationError: No active shift for [Company]. Open a shift before recording sales.
```

Invoices can be drafted without an active shift, but the FMS shift field is required before posting.

---

## Preventing Sales After Shift Close

After a shift closes:
- Its `fms_shift_id` on invoices/receipts becomes read-only
- New receipts cannot be assigned to a closed shift
- Existing posted receipts remain unchanged (immutable GL)
