# FMS — FC Cash (Forecourt Cash) System

**Module:** `fms` + `fms_accounting`
**Status:** Specification — Release 2
**Last updated:** 2026-09-01
**Related:** `srs.md` §7, `tasks.md` §FC-01–FC-20, `feature.md`

---

## 1. Purpose

The FC Cash system answers the core shift accountability question:

> **Does every shilling the attendant collected make it to a proper account?**

Meter readings and physical stock counts establish what was *sold*. Invoices, receipts, drops, and expenses establish how the money was *accounted for*. FC Cash is the computed difference — the running balance of what each attendant still owes the station. It must be zero before the shift can close.

This is not a new GL account. FC Cash is a **computed operational balance** that exists only in the Odoo ORM layer. Real GL entries are posted by native Odoo when documents (invoices, payments) are confirmed. FC Cash tracks whether all documents have been raised.

---

## 2. Core Design Principles

### 2.1 FC Cash is Virtual — Never a GL Account

FC Cash is computed from four independent sources. It is never debited or credited in the ledger. The ledger is updated by:
- `account.move.action_post()` — invoices and out_receipts (Odoo native)
- `account.payment.action_post()` — cash drops, expenses, floats (Odoo native)
- `fms.shift._post_shift_journals()` — fuel COGS and stock on close

FC Cash simply checks that the *operational flow* is complete before the shift closes.

### 2.2 Shift Is a Lens, Not a Second Ledger

The shift record stores nothing it can derive from its documents. All totals are computed by querying `account.move`, `account.payment`, and `fms.shift.fc.line`. This prevents the two-ledger problem (shift total ≠ GL total).

### 2.3 No Parallel Accounting

All money flows use native Odoo documents. FMS adds fields (`fms_shift_id`, `fms_attendant_id`) to query them — it does not replace them or create shadow records.

### 2.4 Closed Shifts Are Immutable

Once a shift is `closed`:
- No field on `fms.shift` or its child models can be written.
- Linked `account.move` records cannot be cancelled or reset to draft.
- Linked `account.payment` records cannot be cancelled.
- **Only reversal is allowed** — creates an opposite GL entry, both records remain in the audit trail.

### 2.5 Residual Allocation — Money Side Removed

The original residual allocation algorithm (money reallocation when attendant lumped carwash into diesel) is removed from the GL posting path. With multi-line sales receipts and explicit FC-Service entries, attendants now record products correctly at point of sale. Residual allocation was a workaround for incomplete data entry — that workaround is no longer needed.

**Gate 5 (dip stock variance) is unchanged.** It is a physical stock check, not a money check. The residual allocation algorithm for stock variance remains.

---

## 3. FC Cash Sources

### 3.1 DR Side — What Attendant Owes (Captured Sales)

| # | Source | Model | Filter |
|---|--------|-------|--------|
| 1 | Fuel meter sales | `fms.shift.meter.entry` | `shift_id`, `attendant_id` — `qty_sold_elec × price` |
| 2 | FC-Product sales | `fms.shift.fc.line` | `line_type='goods'`, `attendant_id` — `sales_amount` |
| 3 | FC-Service amounts | `fms.shift.fc.line` | `line_type='service'`, `attendant_id` — `amount` |
| 4 | Floats issued | `account.payment` | `fms_payment_context='cash_float'`, `fms_attendant_id` |
| 5 | Customer payments collected through attendant | `account.payment` | `payment_type='inbound'`, `partner_type='customer'`, `fms_attendant_id`, excluding float/drop/expense contexts |

### 3.2 CR Side — How Attendant Accounted for It (Collections)

| # | Source | Model | Filter |
|---|--------|-------|--------|
| 6 | Posted credit invoices (→ AR) | `account.move` | `move_type='out_invoice'`, `state='posted'`, `fms_attendant_id` |
| 7 | Posted sales receipts (MPesa/card/cash) | `account.move` | `move_type='out_receipt'`, `state='posted'`, `fms_attendant_id` |
| 8 | Cash drops (incl. float returns) | `account.payment` | `fms_payment_context='cash_drop'`, `fms_attendant_id` |
| 9 | Expenses paid from FC Cash | `account.payment` | `fms_payment_context='expense'`, `fms_attendant_id` |

### 3.3 FC Cash Formula

```
fc_variance (per attendant) = (1 + 2 + 3 + 4 + 5) − (6 + 7 + 8 + 9)

Target: fc_variance = 0.00 per attendant
```

---

## 4. Model: `fms.shift.fc.line`

Unified forecourt product and service lines. One model, two view tabs.

### 4.1 Fields

| Field | Type | Notes |
|-------|------|-------|
| `shift_id` | Many2one(`fms.shift`) | Required, ondelete=cascade |
| `attendant_id` | Many2one(`hr.employee`) | Required, domain `fms_is_attendant=True` |
| `product_id` | Many2one(`product.product`) | Required |
| `line_type` | Selection: `goods` / `service` | Auto-set from `product.detailed_type` on product change |
| `opening_qty` | Float | Goods only. Snapshotted from `stock.quant` at `fms_is_forecourt` location on shift open. Editable until state=`closing` |
| `delivery_qty` | Float | Goods only. Deliveries received at forecourt during shift. Default 0 |
| `closing_qty` | Float | Goods only. Physical count at shift end (attendant enters) |
| `qty_sold` | Float (computed) | Goods: `opening_qty + delivery_qty − closing_qty` |
| `price_unit` | Float | Auto from pricelist on `shift.date`. Editable by supervisor |
| `amount` | Float | Service only. Direct entry — no qty or price |
| `sales_amount` | Float (computed) | Goods: `qty_sold × price_unit`. Service: `amount` |

### 4.2 Stock Formula — Parallel to Fuel Dips

```
Fuel:    fuel_dispensed = opening_dip   + delivery_litres − closing_dip
Product: qty_sold       = opening_qty   + delivery_qty    − closing_qty
```

### 4.3 Opening Qty Snapshot (fires on `fms.shift.action_open()`)

```python
def _snapshot_fc_opening_qty(self):
    forecourt_locs = self.env['stock.location'].search(
        [('fms_is_forecourt', '=', True),
         ('company_id', '=', self.company_id.id)]
    )
    for line in self.fc_line_ids:
        quants = self.env['stock.quant'].search([
            ('product_id', '=', line.product_id.id),
            ('location_id', 'in', forecourt_locs.ids),
        ])
        line.opening_qty = sum(quants.mapped('quantity'))
```

**First shift:** `stock.quant` holds values from the opening balance seed. If product never tracked, opening = 0.0 — supervisor edits manually.

**No previous-shift fetch.** Carrying closing_qty forward risks corruption when shifts overlap, stock adjustments are made, or a shift is reopened. The single source of truth is always `stock.quant`.

### 4.4 Price Fetch

```python
def _get_fc_price(self, product, shift):
    pricelist = shift.company_id.property_product_pricelist
    price = pricelist._get_product_price(product, 1.0, date=shift.date)
    return price or product.list_price
```

- **Revenue**: pricelist price effective on `shift.date`
- **COGS**: `product.standard_price` (AVCO) — Odoo stock module handles this automatically via `stock.move` when posting

### 4.5 View Tab Logic

**Non Fuel Sales tab:** `fc_line_ids` — all lines regardless of `line_type`
- Goods lines: Attendant | Product | Opening | Delivery | Closing | Qty Sold | Price | Amount
- Service lines: Attendant | Service | Amount (qty fields hidden via `column_invisible`)
- Both types in one list: `line_type` column optional, auto-set from product

Product field `onchange`: if `product.detailed_type == 'service'` → set `line_type='service'`, qty fields `column_invisible`, amount field visible. Otherwise `line_type='goods'`, qty/price fields visible, amount computed.

---

## 5. Shift Form — Tab Structure (Final)

### 5.1 Tabs on Shift Form

```
[ Meters ]  [ Dips ]  [ Non Fuel Sales ]  [ Floats / Drops ]
```

**Four tabs only.** Clean entry surface. Supervisor enters data, sees instant subtotals.

Documents raised against the shift (invoices, receipts, expenses, attendant breakdown) are accessed via **Forecourt → Operations** menu — not embedded in the shift form.

### 5.2 Tab: Meters

**Content:** `meter_entry_ids` One2many list (existing)

Columns: Attendant | Nozzle | Product | Opening | Closing | Qty Sold (L) | Electronic (L)

**Subtotals section (read-only, below the list):**

*By Product:*

| Product | Qty Sold (L) | Amount |
|---------|-------------|--------|
| Diesel  | [sum]       | [sum]  |
| ...     | ...         | ...    |
| **Total** | [sum]     | [sum]  |

*By Attendant:*

| Attendant | Qty Sold (L) | Amount |
|-----------|-------------|--------|
| Shedrack  | [sum]       | [sum]  |
| ...       | ...         | ...    |
| **Total** | [sum]       | [sum]  |

Computed as stored Float fields on `fms.shift` refreshed on every meter_entry write.

### 5.3 Tab: Dips

**Content:** `dip_entry_ids` One2many list (existing)

Columns: Tank | Product | Opening (L) | Delivery (L) | Closing Dip (L) | Notes

**Subtotals section (read-only, below the list):**

*By Product:*

| Product | Opening (L) | Delivery (L) | Closing (L) | Variance (L) |
|---------|------------|-------------|------------|-------------|
| Diesel  | [sum]      | [sum]       | [sum]      | [sum]       |
| ...     | ...        | ...         | ...        | ...         |
| **Total** | [sum]    | [sum]       | [sum]      | [sum]       |

No variance amount column in the tab — keeps entry clean. Full variance detail in the close report.

### 5.4 Tab: Non Fuel Sales

**Content:** `fc_line_ids` — all lines (goods + service in one list)

Columns: Attendant | Product | Type | Opening | Delivery | Closing | Qty Sold | Price | Amount

`Type` column shows "Goods" / "Service" badge. When `line_type='service'`: Opening/Delivery/Closing/Qty Sold columns are `column_invisible=True`, Amount is direct entry.

**Subtotals section (read-only, below the list):**

*By Product:*

| Product | Type | Qty Sold | Amount |
|---------|------|----------|--------|
| Helix 5W30 | Goods | [sum] | [sum] |
| Carwash | Service | — | [sum] |
| **Total** | | | [sum] |

*By Attendant:*

| Attendant | Amount |
|-----------|--------|
| Shedrack  | [sum]  |
| **Total** | [sum]  |

### 5.5 Tab: Floats / Drops

**Content:** `account.payment` records filtered `fms_payment_context in ('cash_float', 'cash_drop')` for this shift.

Single list showing both floats and drops, distinguished by context column.

Columns: Date | Type (Float / Drop) | Attendant | Amount | Note | State

**Subtotals section (read-only, below the list):**

*By Attendant:*

| Attendant | Floats In | Drops Out | Net |
|-----------|-----------|-----------|-----|
| Shedrack  | [sum]     | [sum]     | [diff] |
| Peter     | [sum]     | [sum]     | [diff] |
| **Total** | [sum]     | [sum]     | [diff] |

Net = Drops Out − Floats In. Positive = attendant has returned more than received (rare). Negative = attendant still holds float.

Float return (attendant hands back change) → recorded as cash drop, same attendant. Net effect on FC Cash:
```
Float issued  (cash_float) → DR FC Cash
Float returned (cash_drop) → CR FC Cash
Net = 0 when fully returned
```

### 5.6 Subtotal Implementation

Subtotals are **stored Float fields on `fms.shift`**, recomputed by `@api.depends` on their respective child model writes. Not computed in QWeb — these must be available for the supervisor to read without generating a report.

```python
# Example — meter subtotals stored on fms.shift
meter_total_qty    = fields.Float(compute='_compute_meter_totals', store=True)
meter_total_amount = fields.Float(compute='_compute_meter_totals', store=True)
# Per-product and per-attendant: stored as JSON or as a child summary model
```

For the per-product and per-attendant breakdowns (tables), use a `<group>` with a nested `<list>` widget pointing to a lightweight compute-only child model, or render as a `<field widget="one2many">` with a readonly list. The list must not be editable.

**Design rule:** Supervisor sees totals instantly on the tab — no button click, no reload required.

---

## 5A. Forecourt → Operations Menu (documents moved here)

Documents previously embedded as shift tabs are now standalone menu items under **Forecourt → Operations**:

| Menu Item | Model | Filter |
|-----------|-------|--------|
| Sales Receipts | `account.move` | `move_type='out_receipt'` |
| Customer Invoices | `account.move` | `move_type='out_invoice'` |
| Expenses | `account.payment` | `fms_payment_context='expense'` |
| Attendant Summary | `fms.shift.attendant.cash` | all, groupable by shift |
| Customer Payments | `account.payment` | inbound customer, standard Odoo |
| Vendor Payments | `account.payment` | outbound vendor |

Each list has filter "Current Shift" and "This Week" pre-built.

Supervisor workflow:
1. Open shift → enter data in 4 tabs → see subtotals instantly
2. Go to Forecourt → Operations → Sales Receipts → post receipts per attendant
3. FC Cash stat button on shift form turns green → Validate Shift → close

### 5.2 Customer/Vendor Payments

Recorded via standard Odoo **Accounting → Payments** flow. FMS extends `account.payment` with:
- `fms_shift_id` Many2one(`fms.shift`)
- `fms_attendant_id` Many2one(`hr.employee`)
- `fms_payment_context` Selection

FMS queries these fields in FC Cash computation and the attendant reconciliation report. No custom payment document model.

---

## 6. Expense Attendant Rule

If a payment has `fms_shift_id` set and `fms_payment_context='expense'`, then `fms_attendant_id` is **required**.

**Pattern for station cash expenses (not FC Cash):**
1. Supervisor issues Float to attendant who will pay the expense
2. Attendant pays expense → recorded as Expense against that attendant
3. Float (DR FC Cash) + Expense (CR FC Cash) = net 0 on that attendant's FC Cash

This ensures every expense is always attributable to an attendant. Unattributed expenses create unresolvable FC Cash variance.

---

## 7. Invoice and Partial Payment Rule

**Invoice posted → FC Cash cleared immediately. Full invoice amount. Regardless of payment status.**

Once an invoice is posted:
- Attendant's obligation transfers to the customer's AR debt
- GL is correct: DR AR, CR Revenue (Odoo native)
- Attendant is no longer responsible for collecting that cash — credit control is
- The shift can close

If an invoice is subsequently reversed (after shift close), the reversal creates an opposite GL entry. Both entries remain in the audit trail. The shift is not reopened.

---

## 8. Shift State Machine

```
draft
  │
  │  action_open()
  │  → populate dip entries (auto)
  │  → snapshot fc_line opening_qty from stock.quant
  ▼
open  ←─────── all data entry happens here
  │             meter, dip, fc-lines, floats, invoices, receipts,
  │             cash drops, expenses
  │
  │  action_validate_shift()
  │  → checks fc_variance == 0 for ALL attendants
  │  → if not: opens reconciliation wizard (not a hard error)
  │  → if all resolved: state = 'closing'
  │  → fc_line fields locked at this point (no more edits)
  ▼
closing  ←──── supervisor reviews, posts variance entries
  │
  │  action_close()
  │  → Gate 5: dip stock variance within meniscus
  │  → _post_shift_journals() (fuel COGS, stock move)
  │  → _write_dip_logs() (immutable snapshot)
  │  → state = 'closed'
  ▼
closed  ←──── immutable. reversals only.
```

### 8.1 Gate on State Transition to 'closing'

```python
def write(self, vals):
    if vals.get('state') == 'closing':
        for shift in self:
            unresolved = shift.attendant_cash_ids.filtered(
                lambda a: abs(a.fc_variance) > 0.01
            )
            if unresolved:
                raise ValidationError(
                    "Cannot close shift — FC Cash variance exists for: "
                    + ", ".join(unresolved.mapped('attendant_id.name'))
                    + "\nUse 'Validate Shift' to resolve."
                )
    return super().write(vals)
```

---

## 9. Variance Resolution

### 9.1 Site Preferences — New Section: "Variance Resolution"

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allow_variance_writeoff` | Boolean | False | If off, all variance posts to Staff Advances (115130) |
| `variance_writeoff_account_id` | Many2one(`account.account`) | — | Visible only if allow=True |
| `max_writeoff_amount` | Float | 200.0 | Auto write-off threshold ± in company currency |

### 9.2 Resolution Logic

```
fc_variance per attendant:

Case A — allow_variance_writeoff = False (any amount):
  Only option: "Charge to Staff Advance" (115130)
  No write-off button shown

Case B — allow_variance_writeoff = True, abs(variance) ≤ max_writeoff_amount:
  Two buttons: "Write Off" | "Charge to Staff Advance"
  Supervisor chooses

Case C — allow_variance_writeoff = True, abs(variance) > max_writeoff_amount:
  Default: "Charge to Staff Advance"
  Supervisor can still "Write Off" — confirmation dialog required (over threshold)
```

### 9.3 Journal Entry — Variance Post

**Charge to Staff Advance:**
```
DR 115130  AR — Staff Advances    [variance amount]
  CR [shift variance clearing account]
```

**Write Off:**
```
DR prefs.variance_writeoff_account_id   [variance amount]
  CR [shift variance clearing account]
```

The "shift variance clearing account" is the balancing entry that zeroes the operational FC Cash difference. Once posted, `fc_variance` recomputes to 0, and the shift can proceed to `closing`.

---

## 10. Attendant Reconciliation Report

Generated by `action_validate_shift()` when variance exists. Also available as a standalone report button.

### 10.1 Structure (Per Attendant)

```
ATTENDANT: [Name]
════════════════════════════════════════════════════════════
CAPTURED SALES
  Meter — [Product] ([Nozzle])      [Qty]L × [Price]   =  [Amount]
  FC-Product — [Product]            [Qty] × [Price]    =  [Amount]
  FC-Service — [Service]                               =  [Amount]
  Float received                                       =  [Amount]
  Customer payments through attendant                  =  [Amount]
  ──────────────────────────────────────────────────────────
  TOTAL CAPTURED                                          [Amount]

ACCOUNTED FOR
  Invoice [INV/xxxx] ([Customer])   [move_type=out_invoice]  =  [Amount]
  Receipt [RINV/xxxx] ([Journal])   [move_type=out_receipt]  =  [Amount]
  Cash Drop [date]                                           =  [Amount]
  Expense [description]                                      =  [Amount]
  ──────────────────────────────────────────────────────────
  TOTAL ACCOUNTED                                           [Amount]

VARIANCE                                                    [Amount]
STATUS: [Pending / Written Off / Charged to Staff Advance]
════════════════════════════════════════════════════════════
```

### 10.2 Shift Summary

Footer shows:
- Total Captured (all attendants)
- Total Accounted (all attendants)
- Total Variance
- Breakdown by payment method: Cash | MPesa | VISA | AR | Expense

---

## 11. GL Flow Summary — What Posts When

| Action | DR | CR | Who posts |
|--------|----|----|-----------|
| Invoice confirmed | AR (115xxx) | Revenue (4xxxxx) | Odoo native |
| Receipt confirmed (MPesa) | MPesa Float (101030) | Revenue (4xxxxx) | Odoo native |
| Receipt confirmed (VISA) | VISA account (115020/030) | Revenue (4xxxxx) | Odoo native |
| Cash drop | Forecourt Safe (101010) | Source journal | Odoo native |
| Expense | Expense account (6xxxxx) | Forecourt Safe (101010) | Odoo native |
| Float issued | N/A — operational DR only | N/A | FC Cash compute only |
| Customer payment through attendant | Cash journal | AR (115xxx) | Odoo native |
| Shift close — fuel COGS | COGS (5xxxxx) | Inventory (2xxxxx) | `_post_shift_journals` |
| Variance — staff advance | AR Staff Advances (115130) | Shift clearing | Variance wizard |
| Variance — write off | Write-off account | Shift clearing | Variance wizard |

---

## 12. Immutability Constraints

### 12.1 `fms.shift.write()`

```python
def write(self, vals):
    modifiable_when_closed = {'state'}
    for shift in self:
        if shift.state == 'closed' and (set(vals) - modifiable_when_closed):
            raise UserError(
                "Closed shift cannot be modified. "
                "Create a correction shift or use document reversal."
            )
    return super().write(vals)
```

### 12.2 `account.move` — Cancel/Reset Guard

```python
def button_cancel(self):
    for move in self:
        if move.fms_shift_id and move.fms_shift_id.state == 'closed':
            raise UserError(
                f"Shift '{move.fms_shift_id.display_name}' is closed. "
                "Use 'Reverse' to correct this entry — both entries remain in the audit trail."
            )
    return super().button_cancel()

def button_draft(self):
    for move in self:
        if move.fms_shift_id and move.fms_shift_id.state == 'closed':
            raise UserError(
                "Cannot reset to draft — shift is closed. Use reversal."
            )
    return super().button_draft()
```

### 12.3 `account.payment` — Cancel Guard

```python
def action_cancel(self):
    for pay in self:
        if pay.fms_shift_id and pay.fms_shift_id.state == 'closed':
            raise UserError(
                "Cannot cancel — shift is closed. Use reversal via Accounting → Payments."
            )
    return super().action_cancel()
```

---

## 13. Stock Location — Forecourt Flag

`stock.location` extended with:

| Field | Type | Description |
|-------|------|-------------|
| `fms_is_forecourt` | Boolean | Marks this location as the forecourt product holding area (lubes, filters, accessories physically at the pump) |

One forecourt location per company. Products here are tracked by `fms.shift.fc.line`. Separate from fuel tanks (`fms_is_fuel_tank`) and the main store.

**Opening snapshot queries this location.** Products must be moved from the main store to the forecourt location via a stock move before being tracked in FC-Products.

---

## 14. Removed from Previous Design

| Removed | Reason |
|---------|--------|
| `FMSShiftProductSales` residual money allocation | FC-line entries + multi-line receipts replace it |
| `_allocate_residuals()` GL posting step | Attendants now declare products explicitly |
| Previous-shift opening qty fetch on fc_line | `stock.quant` is single source of truth |
| "Customer Payments" FMS menu | Standard Odoo Accounting → Payments, extended with shift/attendant |
| Separate FC-Service model | Unified in `fms.shift.fc.line` with `line_type` field |

Gate 5 (dip stock variance ≤ meniscus) is **unchanged** — it is a physical stock check, not a money check.

---

## 15. Open Questions Resolved

| Question | Decision |
|----------|----------|
| FC Cash: GL account or virtual? | Virtual computed — never posted |
| Partial invoice during shift | Invoice posted = FC Cash cleared. Full amount. Regardless of payment |
| Cash drop: per-attendant or whole-shift? | Per-attendant. Supervisor is treated as an attendant |
| Float return: separate context or cash drop? | Cash drop (`fms_payment_context='cash_drop'`) |
| FC-Product price | Pricelist price on `shift.date`; COGS = average cost (`product.standard_price`) |
| First shift opening qty | From `stock.quant` (seeded as opening balance) |
| FC-Products editable until when? | Until state = `closing` |
| Per-attendant variance write-off | Supervisor (`group_fms_supervisor`) can write off |
| Customer/vendor payments | Standard Odoo `account.payment` — FMS extends, never replaces |
| Residual allocation (money) | Removed — see §2.5 |
