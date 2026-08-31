# FMS Dip Reconciliation — Implementation Tasks

Checklist for modifying the tank dip module. Mark each task `[x]` after verifying it works end-to-end before starting the next.

---

## Task D-01: Site Preferences — replace meniscus_pct with absolute threshold

**File:** `models/fms_site_preferences.py`

- [ ] Add field `default_dip_variance_meniscus = Float(default=1000.0)` — absolute litres
- [ ] Keep `meniscus_pct` field with `deprecated=True` note in help text (backward compat for Gate 6)
- [ ] Update view XML to show new field under Gate configuration section

**Verify:** Open Forecourt → Configuration → Site Preferences. New field "Dip Variance Meniscus (L)" visible with default 1000.

---

## Task D-02: FMSShiftDipEntry — add fields

**File:** `models/fms_shift_entry.py`, class `FMSShiftDipEntry`

- [ ] Add `delivery_qty = Float('Delivery Received (L)', default=0.0)` — editable
- [ ] Add `book_stock_open = Float('Book Stock at Open (L)', readonly=True)` — auto-filled on shift open
- [ ] Update `_check_closing_volume_capacity` — no change needed, still checks `fms_tank_capacity_l`
- [ ] Update `_create_dip_log` — pass new fields to log (see D-04)

**No computed variance fields on entry** — variance is computed at gate/close time via queries.

**Verify:** Open a shift → Dip Entries tab. Two new columns: "Delivery (L)" (editable, default 0) and "Book Stock" (read-only, auto-filled).

---

## Task D-03: Auto-fill book_stock_open on shift open

**File:** `models/fms_shift.py`, method `_populate_shift_entries`

- [ ] After creating each dip entry, query `stock.quant` for that tank+product+company and write `book_stock_open`
- [ ] Query must filter: `location_id = tank.id`, `product_id = tank.fms_fuel_product_id.id`, `company_id in self.env.companies.ids`
- [ ] If no quant exists → `book_stock_open = 0.0`
- [ ] Idempotent: if dip entries already exist, skip (existing guard already in place)

**Verify:** Open new shift. Each dip entry's "Book Stock" column shows current stock.quant value for that tank.

---

## Task D-04: FMSDipLog — add snapshot fields

**File:** `models/fms_logs.py`, class `FMSDipLog`

Add stored fields (written once on shift close, never updated):
- [ ] `delivery_qty = Float`
- [ ] `book_stock_open = Float`
- [ ] `meter_sales_snapshot = Float` — litres from meter entries for this product at close time
- [ ] `shift_variance = Float` — closing − (opening + delivery − meter_sales)
- [ ] `shift_var_amount = Float` — shift_variance × price per litre
- [ ] `month_variance = Float` — cumulative variance since month start
- [ ] `month_var_amount = Float`
- [ ] `var_rate = Float` — price per litre used (from product.list_price at close)

**Verify:** After shift close, check dip_log record in developer mode — all fields populated.

---

## Task D-05: Variance helper method on FMSShift

**File:** `models/fms_shift.py`

Add private method `_compute_dip_variance_data(dip_entry)` that returns a dict:

```python
{
    'meter_sales': float,        # SUM qty_sold_elec for product, this shift
    'shift_variance': float,     # closing − (opening + delivery − meter_sales)
    'shift_var_amount': float,   # shift_variance × price
    'month_variance': float,     # closing − (month_opening + month_deliveries − month_meter_sales)
    'month_var_amount': float,
    'var_rate': float,
}
```

Rules:
- [ ] `meter_sales` = SUM `qty_sold_elec` from `fms.shift.meter.entry` WHERE `shift_id = self.id AND product_id = dip_entry.product_id.id`
- [ ] `var_rate` = `dip_entry.product_id.list_price` (price per litre at close time)
- [ ] Month variance: query `fms.dip_log` WHERE `location_id = dip_entry.location_id.id AND shift_id.date >= month_start AND shift_id.date <= today` — get `opening_volume` of first record and sum `meter_sales_snapshot` and `delivery_qty` of all records (including current entry)
- [ ] All queries filter by `company_id`
- [ ] Amounts use `shift.company_id.currency_id` — no hardcoded currency

**Verify:** Unit-testable — call method directly and check returned dict matches PDF figures.

---

## Task D-06: Fix Gate 5 — use absolute litre threshold

**File:** `models/fms_shift.py`, method `_gate_check_stock_variance`

- [ ] Replace `_get_meniscus_pct()` lookup with `prefs.default_dip_variance_meniscus or 1000.0`
- [ ] For each dip entry, call `_compute_dip_variance_data(dip)` to get `shift_variance`
- [ ] Gate fails if `abs(shift_variance) > meniscus_l`
- [ ] Error message shows: tank name, product name, variance in L, threshold in L, amount in company currency
- [ ] Skip tanks with `closing_volume == 0` (no reading entered — separate validation)

**Verify:** Set meniscus to 50 L. Enter a closing dip that creates 200 L variance. Shift close blocked with clear message. Set closing dip correctly → gate passes.

---

## Task D-07: Update _write_dip_logs to snapshot full data

**File:** `models/fms_shift.py`, method `_write_dip_logs`
**File:** `models/fms_shift_entry.py`, method `_create_dip_log`

- [ ] In `_write_dip_logs`: call `_compute_dip_variance_data(entry)` for each entry
- [ ] Pass full dict to `_create_dip_log`
- [ ] `_create_dip_log` writes all D-04 fields to `fms.dip_log`
- [ ] Idempotency: existing guard already checks `existing_tank_ids` — no change needed

**Verify:** Close a shift. Check each dip_log record has shift_variance, month_variance, and amounts populated correctly.

---

## Task D-08: Stock adjustment on shift close

**File:** `models/fms_shift.py`, method `action_close_shift` (or `_action_close`)

After all gates pass and dip logs written:
- [ ] For each dip entry: set `stock.quant.inventory_quantity = closing_volume` and call `action_apply_inventory()`
- [ ] Filter quant by `location_id` + `product_id` + `company_id in self.env.companies.ids`
- [ ] Create quant if none exists (first time)
- [ ] Wrap in try/except — log error but don't block shift close if stock adjustment fails (with warning notification)
- [ ] Only run once: check if already done via `stock.quant` comparison before applying

**Verify:** Close shift. Check Inventory → Products → product → On Hand. Stock matches closing dip.

---

## Task D-09: Dip Entries tab — UI columns

**File:** `views/fms_shift_views.xml` (or `fms_shift_entry_views.xml`)

In the dip entries One2many list (inside shift form):
- [ ] Visible columns: Tank, Product, Opening (L), Delivery (L), Closing Dip (L), Notes
- [ ] Read-only columns in same list: Book Stock (L)
- [ ] Add a stat button or summary line below list showing shift-level totals:
  - Total Shift Variance (L) with colour widget
  - Total Shift Variance Amount

**No formula columns in the list** — variance shown only at the summary level to keep the entry form clean.

**Verify:** Open shift form → Dip Entries tab. Supervisor sees a clean table: enters ONE number per tank (closing dip). Delivery defaults to 0. No confusing computed columns during entry.

---

## Task D-10: Dip Log list view

**File:** `views/fms_logs_views.xml` (or wherever dip_log view is defined)

- [ ] Add new columns to dip_log list: Delivery (L), Meter Sales Snapshot (L), Shift Variance (L), Shift Var Amount, Month Variance (L), Month Var Amount
- [ ] Group-by product_id available
- [ ] Filter: date range, product, tank

**Verify:** Forecourt → Reporting → Tank Dip Logs. Records show full variance breakdown.

---

## Task D-11: FMSReportWetstock — fix variance formula

**File:** `models/fms_report_views.py`, class `FMSReportWetstock`

Current SQL view has correct columns but formula may be wrong. Fix:
- [ ] Variance = `closing_vol − (opening_vol + deliveries_l − metered_sale)`  (not just `closing − opening`)
- [ ] Add `month_variance` column from `fms_dip_log.month_variance`
- [ ] `within_tolerance` = `abs(variance_l) <= default_dip_variance_meniscus` (join site_preferences)
- [ ] All WHERE clauses include `company_id`

**Verify:** Run wetstock report after closing a shift. Numbers match the manual PDF calculation.

---

## Task D-12: New SQL view — Stock Calculation by Product

**File:** `models/fms_report_views.py` — new class `FMSReportStockCalc`

Mirrors the printed "Shift Stock Calculations" report. Groups by product across tanks.

Columns (matching PDF exactly):
- Product, Opening Stock, Quantity Received, Available Stock, Shift Sales, Closing Stock (expected), Phy Dipping, Shift Var, Month Var, Shift Var Amount, Month Var Amount

- [ ] SQL view groups `fms_dip_log` by `shift_id` + `product_id`, sums all numeric fields
- [ ] Joins `fms_shift` for date and company
- [ ] Amounts in company currency (no hardcoded symbol)
- [ ] Add list view and menu under Forecourt → Reporting → Stock Calculation

**Verify:** Open report for 29-Aug-2026. Figures match the PDF exactly (VP +47.48, UX −75.48, DX +26.37).

---

## Task D-13: Regression check

After all D-01 through D-12 are done:

- [ ] `make upgrade` — no errors
- [ ] Open existing shift → all tabs load without errors
- [ ] Create new shift → dip entries auto-populated with correct opening volumes and book_stock
- [ ] Enter closing dips → no errors on save
- [ ] Close shift → all gates evaluated, dip_log records written with full data
- [ ] Wetstock report → correct figures
- [ ] Stock Calculation report → correct figures matching PDF
- [ ] `stock.quant` updated to closing dip values after close
