# 09 — Field Reference

Complete field reference for all FMS forms. Use when a field label is unclear or a value behaves unexpectedly.

---

## Shift Header (`fms.shift`)

| Field | Type | Description |
|---|---|---|
| Name | Char (auto) | Sequence-generated: FMS/YYYY/NNNN |
| Date | Date | Calendar date of the shift |
| Label | Selection | 1_day / 2_evening / 3_night (display: Day / Evening / Night) |
| Supervisor | Many2one (hr.employee) | Responsible supervisor — required before close |
| State | Selection | draft / open / closing / closed |
| Opened At | Datetime | Set when Open Shift clicked |
| Closed At | Datetime | Set when Start Closing clicked |
| Notes | Text | Free-form notes (incidents, deliveries, anomalies) |
| Total Meter Sales (KES) | Float (computed) | Sum of `elec_cash_sold` across all nozzle entries |
| Total Reported Sales (KES) | Float (computed) | Sum of `reported_sales` across all attendant cash lines |
| FC Cash Balance (KES) | Float (computed) | Sum of all attendant balances — must be 0 to close |
| Sales GL Entry | Many2one (account.move) | Journal entry posted on shift close |
| Linked POS Sessions | Many2many (pos.session) | Sessions whose sales are counted against this shift |

---

## Meter Entry (`fms.shift.meter.entry`)

One row per pump nozzle per shift. Created automatically on Open Shift.

| Field | Type | Editable | Description |
|---|---|---|---|
| Pump | Many2one (fms.pump) | No | Physical pump |
| Nozzle | Many2one (fms.pump.nozzle) | No | Pump nozzle (e.g. "1A") |
| Product | Many2one (product.product) | No | Fuel product (from nozzle) |
| Attendant | Many2one (hr.employee) | Yes | Who operated this nozzle |
| Opening Elec Cash (KES) | Float | No | Auto-filled from previous shift's meter log |
| Closing Elec Cash (KES) | Float | Yes | Read from pump electronic cash display |
| Opening Elec Vol (L) | Float | No | Auto-filled from previous shift's meter log |
| Closing Elec Vol (L) | Float | Yes | Read from pump electronic volume display |
| Opening Manual (L) | Float | No | Auto-filled from previous shift's meter log |
| Closing Manual (L) | Float | Yes | Read from pump mechanical odometer |
| RTT Volume (L) | Float | Yes | Litres returned to tank (default 0) |
| Cash Sold (KES) | Float (computed) | No | Closing − Opening Elec Cash |
| Qty Sold Elec (L) | Float (computed) | No | Closing − Opening Elec Vol − RTT |
| Qty Sold Manual (L) | Float (computed) | No | Closing − Opening Manual |
| Amount (KES) | Float (computed) | No | Qty Sold Elec × price period price |

---

## Dip Entry (`fms.shift.dip.entry`)

One row per fuel tank per shift. Created automatically on Open Shift.

| Field | Type | Editable | Description |
|---|---|---|---|
| Tank Location | Many2one (stock.location) | No | Location with `fms_is_fuel_tank = True` |
| Product | Many2one (product.product) | No | Fuel product stored in tank |
| Opening Volume (L) | Float | No | Auto-filled from previous shift's dip log |
| Closing Dip (L) | Float | Yes | Dipstick reading at shift end |
| Meter Sold (L) | Float (computed) | No | Total Qty Sold Elec for this product across all nozzles |
| Variance (L) | Float (computed) | No | Opening − Closing − Meter Sold |
| Variance % | Float (computed) | No | `abs(Variance) / Closing × 100` |

---

## Attendant Cash (`fms.shift.attendant.cash`)

One row per attendant who appears on any meter entry for this shift.

| Field | Type | Editable | Description |
|---|---|---|---|
| Attendant | Many2one (hr.employee) | No | Attendant name |
| Reported Sales (KES) | Float (computed) | No | Sum of Cash Sold for this attendant's nozzles |
| MPesa (KES) | Float (computed) | No | From linked POS sessions |
| Card (KES) | Float (computed) | No | From linked POS sessions |
| AR / Credit (KES) | Float (computed) | No | From linked POS sessions |
| Expenses (KES) | Float (computed) | No | Vendor bills linked to shift + this attendant |
| Cash Dropped (KES) | Float | **Yes** | Physical cash handed in by attendant |
| Balance (KES) | Float (computed) | No | Reported Sales − (Cash Dropped + MPesa + Card + AR + Expenses). Must be 0. |

---

## Residual Allocation (`fms.shift.residual.allocation`)

Generated automatically by the residual algorithm. Read-only after shift close.

| Field | Description |
|---|---|
| Source Product | Over-reported product (attendant lumped sales into this) |
| Target Product | Under-reported product (actual product sold) |
| Volume (L) | Litres reallocated |
| Amount (KES) | Volume × target product price |
| Journal Entry | GL entry posted on close (DR target COGS / CR source COGS) |

---

## Pump (`fms.pump`)

| Field | Description |
|---|---|
| Name | Pump label (e.g. "Pump 1") |
| Active | Whether this pump appears in new shifts |
| Nozzles | List of nozzles on this pump |

## Pump Nozzle (`fms.pump.nozzle`)

| Field | Description |
|---|---|
| Label | Nozzle identifier (e.g. "1A", "1B") |
| Product | Fuel product dispensed |
| Current Elec Cash (KES) | Last known cash totalizer — becomes opening reading for next shift |
| Current Elec Volume (L) | Last known volume totalizer |
| Current Manual Meter (L) | Last known mechanical odometer |

These "current" fields are updated automatically on every shift close. Correct them manually only when a nozzle is replaced or the meter rolls over.

---

## Site Preferences (`fms.site.preferences`)

One record per company. Forecourt → Configuration → Site Preferences.

| Field | Default | Description |
|---|---|---|
| FMS Journal | Required | Journal for shift GL entries |
| Clearing Account | Required | DR account on every shift sales entry |
| Variance Meniscus (%) | 0.5 | Max dip variance % before Gate 5 blocks close |
| Auto-sync Attendant Cash Lines | True | Auto-create attendant rows on Start Closing |
| Auto-open Next Shift | False | Automatically create and open next shift after close |
| Shift Duration | 8hr | Determines next shift period (8hr / 12hr / 24hr) |

---

## Meter Log (`fms.meter_log`) — Read-only

Written on shift close. Cannot be edited or deleted.

| Field | Description |
|---|---|
| Shift | Parent shift |
| Nozzle | Pump nozzle |
| Product | Fuel product |
| Opening Elec Cash (KES) | Totalizer at shift start |
| Closing Elec Cash (KES) | Totalizer at shift end |
| Opening Elec Volume (L) | Volume totalizer at shift start |
| Closing Elec Volume (L) | Volume totalizer at shift end |
| RTT Volume (L) | Returned to tank this shift |
| Net Cash Sold (KES) | Closing − Opening Elec Cash |
| Net Vol Sold Elec (L) | Closing − Opening Elec Volume − RTT |
| Net Vol Sold Manual (L) | Closing − Opening Manual |

View: Forecourt → Compliance → Meter Logs

---

## Dip Log (`fms.dip_log`) — Read-only

Written on shift close. Cannot be edited or deleted.

| Field | Description |
|---|---|
| Shift | Parent shift |
| Tank Location | Fuel tank |
| Product | Fuel product |
| Opening Volume (L) | Dip at shift start |
| Closing Volume (L) | Dipstick reading at shift end |
| Variance (L) | Opening − Closing − Meter Sold |
| Variance % | `abs(Variance) / Closing × 100` |

View: Forecourt → Wetstock → Dip Logs
