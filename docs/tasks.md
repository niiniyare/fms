# FMS Implementation Tasks

Checklist for all FMS implementation tasks. Mark each task `[x]` after verifying it works end-to-end before starting the next.

**Task series:**
- `D-xx` — Tank Dip Reconciliation (D-01 through D-13)
- `FC-xx` — FC Cash (Forecourt Cash) System (FC-01 through FC-20)

**Spec references:**
- Dip: `docs/srs.md` §4
- FC Cash: `docs/fc_cash_system.md`

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

---

---

# FC Cash (Forecourt Cash) System Tasks

**Spec:** `docs/fc_cash_system.md`
**Dependencies:** D-series tasks should be complete before FC-08 (shift close gate update)
**Critical path:** FC-01 → FC-02 → FC-03 → FC-04 → FC-05 → FC-08 → FC-09 → FC-12 → FC-13

---

## Task FC-01: `stock.location` — add `fms_is_forecourt` flag

**File:** `models/fms_site_preferences.py` or `models/fms_shift.py` (wherever `stock.location` is extended)

- [ ] Add `fms_is_forecourt = fields.Boolean('Forecourt Holding Location', default=False)` to `stock.location` inherit
- [ ] Add field to stock.location form view (in FMS configuration group)
- [ ] Mark the station's forecourt holding location `fms_is_forecourt=True` via shell or data file
- [ ] Add to `ir.model.access.csv` if new ACL needed

**Verify:** Forecourt → Configuration → Locations. One location has "Forecourt Holding" checked.

---

## Task FC-02: `fms.shift.fc.line` — new model

**Files:** new `models/fms_shift_fc_line.py`, update `models/__init__.py`

Fields (see `fc_cash_system.md` §4.1):
- [ ] `shift_id`, `attendant_id`, `product_id` (all required)
- [ ] `line_type` Selection `goods` / `service` — auto-set in `@api.onchange('product_id')`
- [ ] `opening_qty`, `delivery_qty`, `closing_qty`, `qty_sold` (computed goods fields)
- [ ] `price_unit` (auto from pricelist, editable)
- [ ] `amount` (service direct entry)
- [ ] `sales_amount` computed: goods → `qty_sold × price_unit`, service → `amount`
- [ ] `_get_fc_price(product, shift)` helper using `company.property_product_pricelist._get_product_price(product, 1.0, date=shift.date)`
- [ ] `@api.constrains('shift_id')`: block write if `shift.state in ('closing', 'closed')`
- [ ] Add `fc_line_ids = One2many('fms.shift.fc.line', 'shift_id')` to `fms.shift`

**Verify (unit test):**
- Create fc_line with goods product → `line_type='goods'`, qty fields active
- Create fc_line with service product → `line_type='service'`, amount field active
- `sales_amount` computes correctly for both types

---

## Task FC-03: Opening qty snapshot on shift open

**File:** `models/fms_shift.py`, method `action_open` (or `_populate_shift_entries`)

- [ ] Add `_snapshot_fc_opening_qty(self)` method:
  - Query `stock.location` where `fms_is_forecourt=True`, `company_id=self.company_id.id`
  - For each `fc_line` in `self.fc_line_ids` where `line_type='goods'`:
    - Query `stock.quant` for `product_id` + forecourt location
    - Write `opening_qty = sum(quants.mapped('quantity'))` (0.0 if none)
- [ ] Call `_snapshot_fc_opening_qty()` inside `action_open()` after populating shift entries
- [ ] Idempotent: if `opening_qty` already set, do not overwrite (guard with `if not line.opening_qty`)
- [ ] Wrap in `sudo()` if stock access rights require it

**Verify:** Open a new shift that has fc_line entries. Each goods line shows `opening_qty` matching `stock.quant` for the forecourt location.

---

## Task FC-04: FC Cash compute on `fms.shift.attendant.cash`

**File:** `models/fms_shift_entry.py`, class `FMSShiftAttendantCash`

Add computed fields (store=False — always live):
- [ ] `fc_captured = Float` — computed: sources 1–5 (see `fc_cash_system.md` §3.1)
- [ ] `fc_collected = Float` — computed: sources 6–9 (see `fc_cash_system.md` §3.2)
- [ ] `fc_variance = Float` — computed: `fc_captured − fc_collected`

Implementation notes:
- Source 1 (meter): `shift.meter_entry_ids.filtered(lambda e: e.attendant_id == self.attendant_id)`
- Source 2 (fc-products): `shift.fc_line_ids.filtered(lambda l: l.line_type=='goods' and l.attendant_id == self.attendant_id)`
- Source 3 (fc-services): `shift.fc_line_ids.filtered(lambda l: l.line_type=='service' and l.attendant_id == self.attendant_id)`
- Sources 4–5, 8–9: query `account.payment` with shift_id + attendant_id + context filter
- Sources 6–7: query `account.move` with shift_id + attendant_id + move_type + state='posted'
- All queries must filter by `company_id`
- Use `self.env['account.move'].search([...])` — do not use `shift.invoice_ids` (may not exist as a computed field)

Add `fc_cash_balance_total = Float` to `fms.shift`:
- [ ] `fc_cash_balance_total` computed: `sum(self.attendant_cash_ids.mapped('fc_variance'))`

**Verify:** Open shift with test data. Attendant cash tab shows `fc_captured`, `fc_collected`, `fc_variance` columns. Post a receipt → `fc_variance` recalculates.

---

## Task FC-05: Meter price fetch

**File:** `models/fms_shift_entry.py`, class `FMSShiftMeterEntry`

- [ ] Add `_get_shift_price(self)` method:
  - `pricelist = self.shift_id.company_id.property_product_pricelist`
  - `return pricelist._get_product_price(self.product_id, 1.0, date=self.shift_id.date) or self.product_id.list_price`
- [ ] Use `_get_shift_price()` in `FMSShiftFcLine._get_fc_price()` (call same pattern)
- [ ] Use company currency — no hardcoded currency symbol anywhere

**Verify:** Shift with a dated pricelist. Meter entry price matches the pricelist price effective on shift.date, not today's list_price.

---

## Task FC-06: Expense attendant constraint

**File:** `models/fms_shift_entry.py` or `fms_accounting/models/fms_sales_receipt.py` — whichever `account.payment` inherit is in

- [ ] Add `@api.constrains('fms_shift_id', 'fms_payment_context', 'fms_attendant_id')`:
  - If `fms_shift_id` set AND `fms_payment_context == 'expense'` AND `not fms_attendant_id`
  - Raise `ValidationError("Shift expenses require an attendant. ...")`
- [ ] Add `required` in the view: expense payment form must show `fms_attendant_id` as required when `fms_payment_context='expense'`

**Verify:** Try to confirm a shift expense with no attendant set → ValidationError. With attendant set → posts fine.

---

## Task FC-07: Shift form — clean tab structure + subtotals

**Spec:** `fc_cash_system.md` §5

**File:** `views/fms_shift_views.xml`

### 7A — Remove tabs from shift form

- [ ] Remove "Expenses" tab from shift form (move to Operations menu — FC-07C)
- [ ] Remove "Invoices" tab from shift form
- [ ] Remove "Receipts" tab from shift form
- [ ] Remove "Attendants" tab from shift form
- [ ] Remove any other tabs not in the final four

**Final four tabs only:**
```
[ Meters ]  [ Dips ]  [ Non Fuel Sales ]  [ Floats / Drops ]
```

### 7B — Merge Floats + Cash Drops into one tab

- [ ] Replace separate "Floats" and "Cash Drops" tabs with single "Floats / Drops" tab
- [ ] Tab shows `account.payment` records where `fms_payment_context in ('cash_float', 'cash_drop')` and `fms_shift_id = active_id`
- [ ] Columns: Date | Type (Float/Drop — from `fms_payment_context`) | Attendant | Amount | Note | State
- [ ] "New Float" button: context `{'default_fms_payment_context': 'cash_float'}`
- [ ] "New Drop" button: context `{'default_fms_payment_context': 'cash_drop'}`
- [ ] Or single "New" button + context selector on the record

### 7C — Merge FC-Products + FC-Services into "Non Fuel Sales" tab

- [ ] Single tab "Non Fuel Sales" showing all `fc_line_ids`
- [ ] Columns: Attendant | Product | Type | Opening | Delivery | Closing | Qty Sold | Price | Amount
- [ ] `column_invisible="line_type != 'goods'"` on Opening/Delivery/Closing/Qty Sold/Price
- [ ] `column_invisible="line_type == 'goods'"` not needed — Amount always visible
- [ ] Product `onchange` auto-sets `line_type` and shows/hides columns per record
- [ ] Editable until `state in ('closing', 'closed')`

### 7D — Subtotals on each tab

Each tab has a **read-only subtotal section** immediately below the editable list.
Implemented as stored Float fields on `fms.shift` recomputed via `@api.depends` on child writes.
No button needed — updates on every save.

**Meters tab subtotals:**

```xml
<!-- By Product -->
<group string="By Product" col="4">
  <field name="meter_summary_ids" readonly="1">  <!-- lightweight readonly list -->
    <list>
      <field name="product_id"/>
      <field name="qty_sold_l" sum="Total (L)"/>
      <field name="amount" sum="Total"/>
    </list>
  </field>
</group>
<!-- By Attendant -->
<group string="By Attendant" col="4">
  <field name="meter_att_summary_ids" readonly="1">
    <list>
      <field name="attendant_id"/>
      <field name="qty_sold_l" sum="Total (L)"/>
      <field name="amount" sum="Total"/>
    </list>
  </field>
</group>
```

Fields needed on `fms.shift` (all stored, recomputed on meter_entry write):
- [ ] `meter_total_qty` Float (grand total litres)
- [ ] `meter_total_amount` Float (grand total amount)

For per-product and per-attendant tables: use a lightweight **compute-only child model** (no DB table — use `_auto = False` or just `store=False` with `depends` triggers), or use a `<group>` rendering a Python-computed list. Keep it simple — two small tables, 3–5 columns each.

**Dips tab subtotals:**

Fields needed (computed on dip_entry write):
- [ ] Per-product: opening sum, delivery sum, closing sum, variance sum (L)
- [ ] Grand totals: all same fields summed

**Non Fuel Sales tab subtotals:**

Fields needed (computed on fc_line write):
- [ ] Per-product: qty sold (goods only), amount (all)
- [ ] Per-attendant: total amount
- [ ] Grand total amount

**Floats / Drops tab subtotals:**

Fields needed (computed on payment write/post):
- [ ] Per-attendant: floats in (sum cash_float), drops out (sum cash_drop), net (drops − floats)
- [ ] Grand totals: total floats, total drops, net

**Verify:**
- Open shift. Four tabs only. No Expenses/Invoices/Receipts/Attendants tabs.
- Enter meter readings → product and attendant subtotals update on save.
- Enter closing dip → dip subtotals update.
- Enter fc_line → non-fuel subtotals update.
- Issue float, record drop → floats/drops subtotals update.
- All subtotals read-only — cannot be edited directly.

---

## Task FC-08: `action_validate_shift` and gate on 'closing' state

**File:** `models/fms_shift.py`

- [ ] Add `action_validate_shift(self)` method:
  - Compute `fc_variance` for each attendant
  - If all zero (within 0.01): `self.write({'state': 'closing'})`, return success notification
  - If any non-zero: return `ir.actions.act_window` opening `fms.shift.recon.wizard` (FC-09)
- [ ] Add "Validate Shift" button to shift form header — visible when `state='open'`
- [ ] Override `write()` on `fms.shift`:
  - If `vals.get('state') == 'closing'`: check all attendant `fc_variance` == 0 within 0.01
  - If not: raise `ValidationError` listing unresolved attendants
- [ ] Lock `fc_line_ids` when `state in ('closing', 'closed')`: add constraint in `FmsShiftFcLine.write()`

**Verify:** Open shift with unresolved variance → click "Validate Shift" → reconciliation wizard opens. Resolve all variance → click again → state moves to 'closing'. Shift form locks fc_line fields.

---

## Task FC-09: Reconciliation wizard — `fms.shift.recon.wizard`

**Files:** new `models/fms_shift_recon_wizard.py`, new `views/fms_shift_recon_wizard_views.xml`

- [ ] Transient model `fms.shift.recon.wizard`:
  - `shift_id` Many2one (required)
  - `line_ids` One2many `fms.shift.recon.wizard.line` (one row per attendant with variance)
- [ ] `fms.shift.recon.wizard.line`:
  - `attendant_id`, `fc_captured`, `fc_collected`, `fc_variance`
  - `resolution` Selection: `advance` / `writeoff`
  - `writeoff_account_id` Many2one — defaults from site preferences
  - `invisible` logic: writeoff option hidden if `not prefs.allow_variance_writeoff`
- [ ] `action_post_resolution(self)`:
  - For each line where `abs(fc_variance) > 0.01`:
    - If `resolution='advance'`: post journal DR 115130 Staff Advances CR shift clearing
    - If `resolution='writeoff'`: post journal DR writeoff_account CR shift clearing
  - After all posted: call `shift.write({'state': 'closing'})`
- [ ] Respects `prefs.max_writeoff_amount`: if abs(variance) > threshold AND resolution='writeoff': show confirmation dialog

**Verify:** Open wizard with two attendants with variance. Choose advance for one, write-off for other. Post → both journal entries created → state moves to 'closing'.

---

## Task FC-10: Site preferences — Variance Resolution section

**File:** `models/fms_site_preferences.py`

- [ ] Add fields:
  - `allow_variance_writeoff = fields.Boolean('Allow Variance Write-Off', default=False)`
  - `variance_writeoff_account_id = fields.Many2one('account.account', 'Variance Write-Off Account')`
  - `max_writeoff_amount = fields.Float('Write-Off Threshold (±)', default=200.0)`
- [ ] Add "Variance Resolution" section to site preferences view (`views/fms_config_settings_views.xml` or site prefs view)
- [ ] `variance_writeoff_account_id` and `max_writeoff_amount` invisible when `not allow_variance_writeoff`

**Verify:** Site Preferences → Variance Resolution section visible. Toggle "Allow Write-Off" → additional fields appear/disappear.

---

## Task FC-11: Attendant reconciliation report (QWeb)

**Files:** new `reports/fms_attendant_recon_report.xml`, new `reports/fms_attendant_recon_report.py`

Report structure per `fc_cash_system.md` §10:
- [ ] Per-attendant section: Captured Sales breakdown | Accounted breakdown | Variance | Status
- [ ] Shift summary footer: totals by attendant + payment method breakdown
- [ ] `fms_payment_classification` column on receipts (Cash / Digital / Credit)
- [ ] Report callable from shift form (button visible when `state in ('open','closing')`)
- [ ] Report callable from reconciliation wizard
- [ ] All amounts in company currency — no hardcoded currency symbol

**Verify:** Generate report from a shift with mixed attendants. Each attendant section shows correct product/amount breakdown. Variance matches `fc_variance` computed field.

---

## Task FC-12: Immutability guards on `account.move` and `account.payment`

**Files:** `fms_accounting/models/fms_sales_receipt.py` (account.move inherit), relevant payment inherit

`account.move`:
- [ ] Override `button_cancel()`: raise `UserError` if `fms_shift_id.state == 'closed'`
- [ ] Override `button_draft()`: raise `UserError` if `fms_shift_id.state == 'closed'`
- [ ] Error message must mention "Use Reverse to correct..."

`account.payment`:
- [ ] Override `action_cancel()`: raise `UserError` if `fms_shift_id.state == 'closed'`
- [ ] Error message consistent with above

**Verify:**
- Close a test shift. Find a linked invoice. Try to cancel → blocked. Try to reset to draft → blocked. Use "Reverse" → reversal entry created, original intact. Both entries visible in journal.
- Repeat for a linked payment → same behaviour.

---

## Task FC-13: Remove residual allocation from money GL path

**File:** `models/fms_shift.py`

- [ ] Locate `_allocate_residuals()` call inside `action_close_shift()` or `_post_shift_journals()`
- [ ] Remove that call (or wrap in a `if prefs.use_residual_allocation` flag if rollback needed)
- [ ] Gate 5 (`_gate_check_stock_variance`) is NOT changed — dip variance check stays
- [ ] Ensure `FMSShiftProductSales` queries (if still used for reports) still work — they aggregate from account.move lines, no change needed there
- [ ] Run full regression (FC-20) after this task

**Verify:** Close a shift where previously residual allocation would fire. GL entries posted — no residual allocation journal entry. FC Cash balance = 0. Dip variance check still fires if threshold exceeded.

---

## Task FC-14: Forecourt → Operations menu items

**Spec:** `fc_cash_system.md` §5A

**File:** `fms_accounting/views/fms_accounting_menus.xml` (or `fms/views/fms_menu_structure.xml`)

Documents removed from shift tabs are now accessible under **Forecourt → Operations**:

- [ ] Add menu item "Sales Receipts" under Operations (already exists — verify points to `action_fms_sales_receipt`)
- [ ] Add menu item "Customer Invoices" under Operations — action: `account.move`, `move_type='out_invoice'`, no shift filter (user adds filter)
- [ ] Add menu item "Expenses" under Operations — action: `account.payment`, `fms_payment_context='expense'`
- [ ] Add menu item "Attendant Summary" under Operations — action: `fms.shift.attendant.cash` list, groupable by shift
- [ ] Each list view must have search filters: "Open Shift", "Today", "This Week"
- [ ] Each list view must have `fms_shift_id` as an optional column for quick shift identification

**Verify:** Forecourt → Operations menu shows all five items. Each opens correct list filtered to relevant records. Search filters work.

---

## Task FC-14B: Shift form stat buttons — update

**File:** `views/fms_shift_views.xml`

Stat buttons visible in shift form header:
- [ ] "FC Cash" button: shows `fc_cash_balance_total`, green if 0 (within 0.01), red if non-zero. Clicking when non-zero triggers `action_validate_shift()`
- [ ] "Non Fuel Sales" button: shows count of `fc_line_ids` (navigates to Non Fuel Sales tab)
- [ ] Remove any stat buttons that previously pointed to Invoices/Receipts/Expenses tabs (those are now in Operations menu)
- [ ] "Receipts" smart button: shows count of out_receipts linked to shift — opens Forecourt → Operations → Sales Receipts filtered to this shift
- [ ] "Invoices" smart button: shows count of out_invoices linked to shift — opens Customer Invoices filtered to this shift

**Verify:** Stat buttons correct. FC Cash green/red per balance. Clicking Receipts/Invoices opens Operations list filtered to this shift, not embedded tab.

---

## Task FC-15: Attendant reconciliation — access from Operations menu

**File:** `fms_accounting/views/fms_accounting_menus.xml`

- [ ] Add "Attendant Summary" menu item under Forecourt → Operations
- [ ] Action: `fms.shift.attendant.cash` list view showing all attendants across all shifts
- [ ] List columns: Shift | Date | Attendant | fc_captured | fc_collected | fc_variance | resolution_state
- [ ] Filters: "Open Shifts", "Variance > 0", "Today"
- [ ] Group by: Shift, Attendant
- [ ] fc_variance column: green/red colour decoration

**Verify:** Forecourt → Operations → Attendant Summary opens. Shows all attendant lines. Filter "Variance > 0" shows only unresolved lines. Group by Shift works.

---

## Task FC-16: Subtotal child models — `fms.shift.meter.summary` etc.

**Files:** `models/fms_shift_summary.py` (new), `views/fms_shift_views.xml`

Lightweight read-only child models for subtotal tables. No DB table (`_auto = False` not needed — use normal models with `store=False` computed fields and `@api.depends` on parent writes).

**Option A (recommended): SQL view models**
Create one SQL view per subtotal grouping — fast read, zero duplication.

- [ ] `fms.shift.meter.summary` — SQL: GROUP BY shift_id, product_id → qty_sold_l, amount
- [ ] `fms.shift.meter.att.summary` — SQL: GROUP BY shift_id, attendant_id → qty_sold_l, amount
- [ ] `fms.shift.dip.summary` — SQL: GROUP BY shift_id, product_id → opening, delivery, closing, variance (L)
- [ ] `fms.shift.fc.summary` — SQL: GROUP BY shift_id, product_id, line_type → qty (goods), amount (all)
- [ ] `fms.shift.fc.att.summary` — SQL: GROUP BY shift_id, attendant_id → total_amount
- [ ] `fms.shift.float.att.summary` — SQL: GROUP BY shift_id, attendant_id → floats_in, drops_out, net

Each model: `_auto = False`, `init()` creates the SQL view, read-only.

**Render in view:** One2many-like widget on shift form pointing to these summary models, read-only list with `sum` totals row. Placed below the editable list in each tab.

**Verify:**
- Enter meter readings → save → By Product and By Attendant tables populate.
- Enter dip closing → save → Dips summary updates.
- Enter fc_line → save → Non Fuel summary updates.
- Enter float/drop → post → Floats/Drops summary updates.
- All summary tables read-only. Grand totals row visible.

---

## Task FC-17: `fms.site.preferences` — GL Account Setup Check update

**File:** `models/fms_setup_check.py`

- [ ] Add check: if `allow_variance_writeoff=True` but `variance_writeoff_account_id` not set → warning
- [ ] Add check: if no `stock.location` has `fms_is_forecourt=True` → warning (FC-Products will fail to snapshot)
- [ ] Add check: `property_product_pricelist` set on company → required for FC price fetch
- [ ] Existing checks unchanged

**Verify:** GL Account Setup Check → new warnings appear for missing forecourt location and missing write-off account.

---

## Task FC-18: Customer/vendor payment extensions — views

**File:** `fms_accounting/views/fms_payment_views.xml`

- [ ] Verify `fms_shift_id` and `fms_attendant_id` fields already on `account.payment` form (from previous work)
- [ ] Verify `fms_payment_context` field on form
- [ ] Add `fms_attendant_id` to payment list view (optional column)
- [ ] Add filter "This Shift" to standard payment search view (filter by `fms_shift_id = active_id` from context)
- [ ] No custom payment document model — standard Odoo flow only
- [ ] Ensure Expenses action under Operations menu filters to `fms_payment_context='expense'` only

**Verify:** Accounting → Payments (standard). FMS tab shows shift/attendant/context. Forecourt → Operations → Expenses shows only expense-context payments. Filter "This Shift" works.

---

## Task FC-19: Data migration — set `fms_is_forecourt` on existing location

**File:** shell script or `data/fc_cash_data.xml`

- [ ] Identify the existing "forecourt" or "pump area" stock location in the database
- [ ] Set `fms_is_forecourt=True` on it
- [ ] Verify `stock.quant` records exist for non-fuel products at that location (lubes, filters, etc.)
- [ ] If no forecourt location exists: create one as child of the main station location

**Verify:** `stock.quant` query for forecourt location returns expected products. Opening snapshot test: open a test shift, check fc_line.opening_qty populated from quant.

---

## Task FC-20: Full regression check

After FC-01 through FC-19 are complete:

**Core functionality:**
- [ ] `make upgrade` — no errors, no warnings
- [ ] Open existing 29-Aug-2026 shift — exactly four tabs: Meters, Dips, Non Fuel Sales, Floats/Drops
- [ ] No Expenses / Invoices / Receipts / Attendants tabs on shift form
- [ ] Create new shift → `action_open()` snapshots fc_line opening qty from stock.quant correctly

**Non Fuel Sales tab:**
- [ ] Add goods fc_line: opening auto-filled, enter delivery + closing → qty_sold computes, sales_amount computes
- [ ] Add service fc_line: amount field active, qty fields hidden → sales_amount = amount
- [ ] Subtotals below list: By Product table and By Attendant table update on save
- [ ] Tab locked (read-only) when state = 'closing'

**Floats / Drops tab:**
- [ ] Both floats and drops in one list with Type column
- [ ] Issue float → appears in tab, FC Cash DR increases
- [ ] Record drop → appears in tab, FC Cash CR decreases
- [ ] Float return as cash_drop → appears in drop row, nets correctly per attendant
- [ ] Subtotals: per-attendant floats in / drops out / net updates on post

**Meters and Dips subtotals:**
- [ ] Enter meter readings → By Product and By Attendant tables populate below list
- [ ] Enter closing dips → Dips summary table updates

**FC Cash and validation:**
- [ ] Post invoice (via Operations → Customer Invoices) → fc_variance reduces on that attendant
- [ ] Post receipt (via Operations → Sales Receipts) → fc_variance reduces further
- [ ] Post expense with attendant → fc_variance reduces; without attendant → ValidationError
- [ ] FC Cash stat button: red when variance, green when 0; clicking opens reconciliation wizard
- [ ] Validate Shift with all variance = 0 → state moves to 'closing' directly
- [ ] Validate Shift with variance → reconciliation wizard opens
- [ ] Post advance resolution → journal entry DR 115130, state moves to 'closing'
- [ ] Post write-off resolution (if prefs.allow=True, abs ≤ threshold) → DR writeoff account

**Immutability:**
- [ ] Shift close → Gate 5 fires, journals post, state = 'closed'
- [ ] Try to cancel closed-shift invoice → blocked with "Use Reverse" message
- [ ] Try to reset closed-shift invoice to draft → blocked
- [ ] Reverse closed-shift invoice → both entries visible in journal
- [ ] Try to edit fc_line on closed shift → blocked

**Operations menu:**
- [ ] Forecourt → Operations → Sales Receipts — correct, shows out_receipts
- [ ] Forecourt → Operations → Customer Invoices — correct, shows out_invoices
- [ ] Forecourt → Operations → Expenses — shows expense-context payments only
- [ ] Forecourt → Operations → Attendant Summary — shows attendant cash rows, filterable
- [ ] Receipts and Invoices stat buttons on shift form navigate to Operations lists filtered to this shift

**Reports and existing functionality:**
- [ ] Attendant reconciliation report → generates, per-attendant breakdown correct
- [ ] D-series regression: wetstock report, stock calculation report — unchanged, no regressions
- [ ] GL Account Setup Check warns on missing forecourt location and missing write-off account

**Quality:**
- [ ] No hardcoded currency symbols anywhere in new code — all use `company_id.currency_id`
- [ ] All security tests run as uid=2 — not as SUPERUSER
- [ ] All summary tables read-only — cannot be directly edited
