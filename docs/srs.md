# FMS — System Requirements Specification

**System:** Forecourt Management System (FMS)
**Platform:** Odoo 18 Community Edition
**Status:** Development — Phase 1
**Last updated:** 2026-08-31

---

## 1. Purpose

FMS manages the full lifecycle of a fuel-station shift:
- Pump meter readings → fuel dispensed per nozzle
- Tank dip readings → physical stock reconciliation
- Cash / MPesa / VISA / credit invoice collection per attendant
- GL posting (revenue, COGS, AR, cash) on shift close
- Hard gates that must all pass before a shift can close

---

## 2. Core Data Separation Principle

**Three independent source models — never merge, always aggregate:**

| Source | Model | What it captures |
|--------|-------|-----------------|
| Meter | `fms.shift.meter.entry` | Litres dispensed + cash collected per nozzle per shift |
| Dip | `fms.shift.dip.entry` | Physical tank level (stick reading) at shift open and close |
| Sales | `account.move` + `account.payment` | Invoiced revenue and receipts linked via `fms_shift_id` |

Gates, variance computations, and reports **query and aggregate** across these three sources. No source model caches data from another. POS is not used — all sales flow through `account.move` (invoices) and `account.payment` (receipts).

---

## 3. Modules

| Module | Path | Depends on |
|--------|------|------------|
| `fms` | `/home/niini/fms` | `account`, `stock`, `hr` |
| `fms_accounting` | `/home/niini/fms_accounting` | `fms`, `account` |

---

## 4. Module: Tank Dip Reconciliation

### 4.1 Entities

#### `stock.location` (extended)
Represents a physical fuel tank at the station.

| Field | Type | Description |
|-------|------|-------------|
| `fms_is_fuel_tank` | Boolean | Marks this location as a managed fuel tank |
| `fms_fuel_product_id` | Many2one(product.product) | Product stored in this tank |
| `fms_tank_capacity_l` | Float | Maximum physical capacity in litres |
| `fms_safety_days` | Integer | Minimum days of stock buffer before reorder alert |

**Note:** One product can span multiple tanks (e.g., two Diesel Extra tanks T3A and T3B). Dip entries are per-tank. Reports aggregate by product.

#### `fms.shift.dip.entry`
One row per tank per shift. Editable while shift is open; locked on close.

| Field | Type | Rules |
|-------|------|-------|
| `shift_id` | Many2one(fms.shift) | Required, cascade delete |
| `location_id` | Many2one(stock.location) | Must have `fms_is_fuel_tank=True` |
| `product_id` | related: location.fms_fuel_product_id | Read-only, stored |
| `opening_volume` | Float (L) | Auto-populated from previous shift's dip log closing volume |
| `closing_volume` | Float (L) | Entered by supervisor at shift end |
| `delivery_qty` | Float (L) | Litres received into this tank during the shift (default 0) |
| `book_stock_open` | Float (L) | `stock.quant` quantity at moment shift opens (auto-filled, read-only) |
| `notes` | Char | Optional supervisor note |

**Computed at gate/close time (not stored on entry — queried fresh):**

| Computation | Formula | Source |
|-------------|---------|--------|
| `meter_sales` | SUM of `qty_sold_elec` on meter entries where `product_id` matches | `fms.shift.meter.entry` |
| `invoice_sales` | SUM of invoice line quantities for this product on posted moves linked to shift | `account.move.line` |
| `shift_variance` | `closing_volume − (opening_volume + delivery_qty − meter_sales)` | Dip + Meter |
| `shift_var_amount` | `shift_variance × product.list_price` | Dip + Price |
| `month_variance` | `closing_volume − (month_opening + month_deliveries − month_meter_sales)` | Dip logs since month start |
| `month_var_amount` | `month_variance × product.list_price` | Dip log + Price |

Positive variance = stock gain (tank has more than expected). Negative = loss.

#### `fms.dip_log`
Immutable snapshot written on shift close. One row per tank per shift.

Stores all computed values at the moment of close (shift_variance, month_variance, var amounts). Cannot be written or deleted after creation — forms EPRA audit trail.

Additional fields vs current implementation:
- `delivery_qty`, `book_stock_open`, `meter_sales_snapshot`
- `shift_variance`, `shift_var_amount`
- `month_variance`, `month_var_amount`
- `var_rate` — price per litre used for amount calculation (currency-agnostic)

### 4.2 Gate: Dip Variance (Gate 5)

**Configured in:** `fms.site.preferences.default_dip_variance_meniscus` (absolute litres, default 1000 L)

**Rule:** For each tank, `abs(shift_variance) ≤ default_dip_variance_meniscus`.

Replaces `meniscus_pct` (percentage-based). Absolute litres is more meaningful — a ±1000 L threshold applies equally to a 10,000 L and a 20,000 L tank rather than percentage which penalises smaller tanks.

If gate fails, supervisor must:
1. Re-check the dip reading
2. Confirm the delivery_qty is correct
3. Check meter entries for the product
4. Post a stock adjustment if readings are confirmed correct

**Gate message** shows per-tank: product name, tank name, variance in L, threshold, variance amount in company currency.

### 4.3 Stock Adjustment on Close

When shift closes and all gates pass:
1. For each dip entry, compute `shift_variance`
2. Update `stock.quant` for that tank: `inventory_quantity = closing_volume`
3. Call `action_apply_inventory()` — creates an audit inventory adjustment move in Odoo

This keeps Odoo book stock in sync with physical dips after every shift. The next shift's `book_stock_open` will equal the previous shift's `closing_volume`.

### 4.4 Month Variance Computation (materialized at close)

```
month_opening   = opening_volume of first dip_log of this product/tank in current month
month_deliveries = SUM(delivery_qty) across dip_logs for product/tank since month start
month_meter_sales = SUM(meter_sales_snapshot) across dip_logs for product/tank since month start
month_variance  = closing_volume − (month_opening + month_deliveries − month_meter_sales)
```

Computed once at shift close. Written to `fms.dip_log.month_variance`. Not recomputed on every report load.

### 4.5 Reports

**Report A: Shift Stock Calculation (by product)**
Mirrors the printed "Shift Stock Calculations" PDF. Aggregates across all tanks per product.

Columns: Product | Tank(s) | Opening Stock | Quantity Received | Available Stock | Shift Sales | Closing Stock | Phy Dipping | Shift Var | Month Var

Grouping: `product_id` — if two tanks hold same product, one summary row per product with sub-rows per tank.

**Report B: Tank Stock Balance (per tank)**
Per-tank granularity. Same columns. Used by supervisor for per-tank drill-down.

Both reports: variance amounts in company currency (not hardcoded).

### 4.6 UX Design Principles for Dip Tab

**What the supervisor sees on the Shift form → Dip Entries tab:**

| Column | Editable | Description |
|--------|----------|-------------|
| Tank | No | Tank name (e.g., "T3 — Diesel Extra") |
| Product | No | Auto from tank |
| Opening (L) | No | From previous shift |
| Delivery (L) | Yes | Enter 0 if no delivery |
| Closing Dip (L) | Yes | Stick reading — only field that matters |
| Notes | Yes | Optional |

Computed columns shown read-only after Save:
- Shift Variance (L) and amount — shown with colour: green = gain, red = loss, grey = within tolerance
- Month Variance (L) and amount

**No formula fields visible during entry** — supervisor enters ONE number (closing dip). System computes everything else.

---

## 5. Module: Pump Meter Entries

*(Section placeholder — not modified in current sprint)*

Meters capture per-nozzle opening and closing readings (electronic volume, mechanical volume, cash meter). Shift variance computed as `closing − opening`. Product aggregated via `nozzle → product`.

---

## 6. Module: Sales (Invoices & Receipts)

*(Section placeholder — not modified in current sprint)*

All sales flow through `account.move` (invoices) and `account.payment` (receipts) linked via `fms_shift_id`. No POS integration in current scope. `FMSShiftProductSales` aggregates from these sources for the residual allocation algorithm and cash reconciliation gate.

---

## 7. Module: Cash Reconciliation

*(Section placeholder — not modified in current sprint)*

Per-attendant cash gate: reported sales = cash dropped + MPesa + VISA + AR invoiced. Hard gate — FC Cash must equal zero before shift can close.

---

## 8. Module: GL Posting

*(Section placeholder — not modified in current sprint)*

On shift close: journal entries posted for fuel revenue per product, COGS, and stock adjustment. Uses company's configured journal accounts. Currency from `company_id.currency_id`.

---

## 9. Cross-Cutting Rules

### 9.1 Company Isolation
Every ORM query includes `company_id = self.env.company.id` or `company_id in self.env.companies.ids`. No cross-company data leakage.

### 9.2 Currency
All monetary amounts use `shift.company_id.currency_id`. Never hardcode currency symbol or code. Field labels say "Amount" not "Amount (KES)".

### 9.3 Idempotency
All mutations (shift open/close, log writes, stock adjustments) are idempotent. Running twice produces the same result, not duplicates.

### 9.4 Immutability
`fms.meter_log` and `fms.dip_log` raise `ValidationError` on any `write()` or `unlink()` (except delivery update context). These records are the EPRA audit trail.

### 9.5 No parallel accounting
FMS never creates a shadow cash balance. All amounts post directly to Odoo GL via `account.move`.
