# FMS Report Catalogue

**System:** Forecourt Management System — Shell Maanzoni
**Purpose:** Definitive list of reports, with filters, groupings and build type

---

## 1. Filter conventions

Get these right once and most per-report filter work disappears.

### 1.1 Global filters — present on every report

| Filter | Type | Notes |
|---|---|---|
| Station | Multi-select | HQ users only. Station users are scoped by `ir.rule`, not by a filter — never let a station user *choose* their station |
| Date range | Date range + presets | Presets: Today · Yesterday · This shift · This week · This month · **This price period** · Last 30 days · Custom |
| Shift | Multi-select | Day / Evening / Night |
| Product | Multi-select | |
| Product category | Multi-select | White products · Lubricants · LPG · Filters · Accessories · Spares |
| Status | Multi-select | Draft / Open / Closing / Closed / Disputed — default to **Closed only** on financial reports |
| Comparison period | Toggle | Previous period, or same period last year. Needed on every trended report, not just R21 |
| Exception only | Boolean | Hide everything inside tolerance. Will end up being the most-used control in the suite — build it once as a mixin |

### 1.2 Four rules that matter more than the filter list

**Date means shift date, never create date.** A night shift crossing midnight belongs to the shift it opened on. If a report filters on `create_date` it will split night shifts across two days and nothing will ever reconcile.

**Category is a first-class dimension, with subtotals.** Every value report groups by product category, subtotals each category, and carries a grand total — the structure your legacy cumulative report already uses:

| Category | UoM captured | Subtotal in |
|---|---|---|
| White products | Litres (qty = volume) | Litres · KES |
| Lubricants | Units **and** volume (T1 / T1½ / T4 / T5 pack sizes) | Units · litres · KES |
| LPG and accessories | Units **and** kg (6 kg / 13 kg) | Units · kg · KES |
| Filters — oil, air, fuel | Units | Units · KES |
| Cabin filters | Units | Units · KES |
| Accessories | Units | Units · KES |
| Other spares | Units | Units · KES |

**The value grand total is always valid. The quantity grand total is not.** KES sums across every category. Quantity does not — 207,302 litres of fuel plus 388 bottles of oil plus 22 gas cylinders is a meaningless number, and your legacy report prints it. Either suppress the quantity grand total or emit one total per UoM. Category subtotals in quantity are fine, because a category shares a UoM.

**"This price period" is a first-class preset.** EPRA revises on the 14th, effective the 15th. Your commercial month runs 15th to 14th, not 1st to 31st. Every margin and price-comparison report needs this preset or the numbers blend two price regimes.

**Every filter dimension must also be a group-by dimension.** If a user can filter by attendant, they must be able to group by attendant. This is free in Odoo if you build on `_auto = False` views and don't hardcode filters.

### 1.3 Defaults beat options

A report that opens on the right question gets read. Each report below specifies its default state — treat that as part of the spec, not a nicety.

---

## 2. Daily operating reports — P0

### R1 · Shift Closure Sheet
**Printed, signed, filed.** The handover document.

| | |
|---|---|
| Type | QWeb PDF, immutable once posted |
| Grouping | Product → nozzle; then attendant |
| Content | Litres and value by product · meter readings all three types · dip readings · tenders by method · variances · gate outcomes · reason codes · signature blocks |
| Filters | Single shift (it *is* the shift) |
| Drill-down | n/a — it's the printed artefact |

### R2 · Daily Station Report
The page you read each morning.

| | |
|---|---|
| Type | QWeb PDF + on-screen |
| Grouping | Shift → product; plus day totals |
| Filters | Date · station |
| Extra filters | Include/exclude non-fuel · show comparison to previous day |
| Default | Yesterday, all shifts |
| Drill-down | Shift → R1 |

### R3 · Wetstock Reconciliation
**The single most important report in the system.**

| | |
|---|---|
| Type | QWeb PDF (for HQ/Shell) + pivot |
| Grouping | Tank → product → day; with rolling 7-day and 30-day cumulative |
| Content | Opening dip · receipts · metered sale · book stock · closing dip · variance L · variance % · cumulative variance |
| Filters | Date range · **tank** · product · variance threshold (`> x %`) · shift · include/exclude delivery days · **unexplained only** (exclude variances that already carry a reason code) · tolerance override (model a different threshold without touching config) |
| Default | Last 30 days, all tanks, cumulative view |
| Drill-down | Row → dip readings and meter lines for that shift |

> Delivery-day exclusion matters: a dip taken before product settles is the most common false variance. Let the reader isolate clean days.

### R4 · Attendant Sales & Cash
| | |
|---|---|
| Type | Pivot |
| Grouping | Attendant → shift → product |
| Content | Litres · value · RTT · tenders by method · shortage/overage · cumulative shortage |
| Filters | Date range · **attendant** · shift · island · nozzle · product · shortage threshold · recovered / unrecovered |
| Default | This month, all attendants, sorted by shortage descending |
| Drill-down | Row → shift attendant lines |

### R5 · Stock Position & Days of Cover
Not currently in your suite. You cannot order fuel without it.

| | |
|---|---|
| Type | List / dashboard |
| Grouping | Tank → product |
| Content | Closing stock · ullage · average daily run rate (7/30-day) · **days of cover** · reorder flag · stock value at AVCO |
| Filters | Station · product · **below reorder point only** · tank |
| Default | Current, all tanks, reorder items first |

---

## 3. Loss and investigation — P0/P1

### R6 · Tank Loss Analysis (SIR)
The defensible answer when Shell asks about a persistent loss.

| | |
|---|---|
| Type | QWeb PDF + graph |
| Grouping | Tank → 30-day window |
| Content | Cumulative variance · variance as % of throughput · statistical confidence · leak/no-leak/inconclusive verdict · cost impact at AVCO |
| Filters | Tank · date range (min 30 days) · product · verdict · confidence level (95 % / 99 %) · exclude shifts flagged as bad readings |
| Default | Last 30 days, all tanks |

### R7 · Meter Variance Log
Catches the failing pulser that no single shift reveals.

| | |
|---|---|
| Type | Pivot + line graph |
| Grouping | Nozzle → date |
| Content | Electronic vs manual per nozzle · drift trend · days since calibration |
| Filters | Nozzle · pump · island · date range · **variance threshold** · product · calibration overdue |
| Default | Last 30 days, variance > 0.5 L, trend view |

### R8 · Delivery Reconciliation
| | |
|---|---|
| Type | QWeb PDF + pivot |
| Grouping | Delivery → compartment; and by transporter, driver, supplier |
| Content | Loaded vs received litres · temperature and density both ends · temperature-corrected comparison · in-transit loss L and % and value · seal check · retention observed y/n · claim status |
| Filters | Date range · **transporter** · driver · truck · supplier · product · tank · loss threshold · claim status |
| Default | Last 90 days, sorted by loss % descending |
| Drill-down | Delivery → GRN → stock moves |

### R9 · Drive-off & Incident Register
| | |
|---|---|
| Type | List |
| Content | Date · shift · attendant · nozzle · litres · value · plate · OB number · recovery status |
| Filters | Date range · type (drive-off / no-pay / spillage / wrong fuel / calibration test / own use / transfer) · attendant · recovery status · value threshold |
| Default | This month, unrecovered first |

### R10 · Residual & Attribution Exceptions
Replaces a standing residual report — see note in §7.

| | |
|---|---|
| Type | List, exception-only |
| Content | Shift · product · volume residual · cash residual · **net-to-zero test result** · diagnosed cause · document to correct · reason code · who cleared it |
| Filters | Date range · product · **residual type** (misattribution / wrong price / wrong rate / real) · cleared vs open · data-entry user · value threshold |
| Default | Open exceptions only, all dates |

---

## 4. Cash and credit — P0

### R11 · Cash Journey
Declared → safe drop → banked → bank statement.

| | |
|---|---|
| Type | Pivot |
| Grouping | Shift → attendant → stage |
| Content | Expected · declared · dropped · banked · bank-confirmed · gap at each stage |
| Filters | Date range · attendant · supervisor · shift · **stage where gap occurs** · unreconciled only |
| Default | This month, unreconciled only |

### R12 · Debtors Aging & Credit Exposure
| | |
|---|---|
| Type | Standard Odoo aging + FMS overlay |
| Grouping | Customer → invoice; buckets 0-30/31-60/61-90/90+ |
| Content | Balance · credit limit · **exposure vs limit** · days overdue · last payment · fuel volume this period |
| Filters | Customer · salesperson · **over limit only** · aging bucket · balance threshold · product · vehicle |
| Default | All customers, over-limit and 60+ days first |
| Drill-down | Customer → invoices → shift lines |

### R13 · Fleet Vehicle Consumption
Your fleet customers will ask for this in writing.

| | |
|---|---|
| Type | Pivot + customer-facing PDF |
| Grouping | Customer → vehicle → date |
| Content | Litres · value · odometer · **km covered · litres per 100 km** · average price · discount given |
| Filters | Customer · **vehicle / plate** · date range · product · driver · consumption anomaly (outside x% of vehicle norm) · **fills per day above n** (catches card sharing) · tank capacity exceeded (a fill larger than the vehicle's tank) |
| Default | Last month, by customer |

### R14 · Customer Statement
| | |
|---|---|
| Type | QWeb PDF, emailed |
| Filters | Customer · date range · include vehicle detail y/n · open items vs all |
| Default | Last price period, open items |

---

## 5. Attendant reports — P0

An attendant sells fuel, lubricants and LPG from the same shift, so every report here reports **all categories**, not just white products. R4 stays as the daily supervisor view; these are the deeper cuts.

Two structural rules apply to this whole section:

- **A nozzle that changes hands mid-shift produces two lines**, one per attendant. Accountability follows the person holding the nozzle, not the shift.
- **Shortage data is employment-sensitive.** Restrict R26 and R28 to supervisor and above, and log who ran them. These reports end in payroll deductions and disciplinary conversations.

### R24 · Attendant Shift Statement
**Printed, signed by the attendant.** Their copy of the handover.

| | |
|---|---|
| Type | QWeb PDF, immutable once the shift closes |
| Grouping | Nozzle → product; then category → product for non-fuel; then tenders |
| Content | Nozzles held and hours on each · opening and closing meters (all three types) · RTT · litres and value by product · non-fuel items sold · tenders collected by method · cash declared · shortage or overage · cumulative position to date · signature blocks for attendant and supervisor |
| Filters | Single shift · single attendant |
| Options | Include nozzle detail y/n · include non-fuel lines y/n · include cumulative position y/n |
| Controls | Reprint reason logged |

### R25 · Attendant Sales by Category
The full picture of what one person sold, fuel and non-fuel together.

| | |
|---|---|
| Type | Pivot |
| Grouping | Attendant → **category → product**, with category subtotals and grand total |
| Content | Units · volume (litres or kg) · value · cash vs non-cash split · % of attendant total · % of station total |
| Filters | Date range · **attendant** · **product category** · product · shift · island · nozzle · tender type · UoM basis (units / volume) · value threshold |
| Group by | Attendant · category · product · shift · date · week · month · island |
| Default | This month, by attendant then category, value descending |
| Drill-down | Row → shift lines → source documents |

### R26 · Shortage & Overage Ledger
Running position per attendant, not a single shift's snapshot.

| | |
|---|---|
| Type | Pivot + list |
| Grouping | Attendant → date; with running cumulative balance |
| Content | Expected · declared · shortage or overage per shift · **cumulative position** · amount recovered · amount outstanding · payroll period deducted · write-offs |
| Filters | Date range · **attendant** · position (short / over / clear) · amount threshold · recovery status (outstanding / recovered / written off / in payroll) · payroll period · supervisor on duty |
| Default | Open shortages only, largest outstanding first |
| Drill-down | Row → R24 for that shift |

### R27 · Attendant Performance
| | |
|---|---|
| Type | Pivot + ranking view |
| Grouping | Attendant → period; ranked |
| Content | Litres per hour on shift · transactions per hour · average ticket · **product mix** (V-Power share of petrol, lubricant attach rate per 100 fuel sales, LPG units) · share of island throughput · cash accuracy rate |
| Filters | Date range · attendant · shift · island · **product category** · metric · **minimum hours on shift** (so a two-hour relief doesn't top the ranking) · active employees only |
| Default | This month, ranked by litres per hour, minimum 20 hours |

> The lubricant attach rate is the one number here with commercial value. Fuel margin is capped by EPRA; lubricants are not.

### R28 · Attendant Risk & Anomaly
The report that finds problems. Restricted access.

| | |
|---|---|
| Type | List, exception-only |
| Grouping | Attendant → anomaly type |
| Content | Meter variance concentrated on their nozzles · RTT frequency and volume · drive-offs on their watch · attribution residuals traced to their entries · **round-number meter readings** · duplicate readings across days · readings entered outside shift hours · shortage pattern (consistently short vs random) |
| Filters | Date range · attendant · **anomaly type** · occurrence threshold · value threshold · unexplained only · shift · island |
| Default | Last 90 days, anomalies only, ranked by occurrence count |

> Consistently short by a similar amount is a different signal from randomly short by varying amounts. The first is a process or a person; the second is usually a float or change-making problem. Let the report separate them.

### R29 · Nozzle Assignment & Handover Log
| | |
|---|---|
| Type | List |
| Content | Nozzle · attendant · assigned from and to · assigned by · meter reading at handover · mid-shift changes |
| Filters | Date range · attendant · nozzle · island · shift · **unassigned periods only** · **mid-shift handovers only** |
| Default | This week, mid-shift handovers first |

> Without this, a variance on nozzle UX2 can't be attributed to anyone, and every attendant on that island is equally implicated.

---

## 6. Compliance and audit — P0

### R15 · Shift Closure Audit Log
| | |
|---|---|
| Type | List, immutable |
| Content | Gate outcomes · failures · reason codes · overrides · who · when · **from which device/IP** · time between reading and entry |
| Filters | Date range · shift · supervisor · user · gate · pass/fail · override only · reason code |
| Default | Last 30 days, failures and overrides only |

### R16 · GL Reconciliation Journal
| | |
|---|---|
| Type | List + PDF |
| Grouping | Shift → journal entry → account |
| Content | Fuel sales traced to GL · variance entries · residual entries · cash variance entries |
| Filters | Date range · account · journal · shift · posted/unposted · entry type |
| Drill-down | Line → `account.move` |

### R17 · Calibration & Licence Register
| | |
|---|---|
| Type | List with expiry alerts |
| Content | Pump calibration certs · tank calibration certs · dip chart validity · EPRA / NEMA / fire / business permits · test-can log |
| Filters | Type · **expiring within 30/60/90 days** · expired only · asset · authority |
| Default | Expiring within 60 days |

### R18 · Tax Sales Summary (eTIMS handoff)
| | |
|---|---|
| Type | List + export |
| Grouping | Tax rate → product → date |
| Filters | Date range · tax rate · product · exported/not exported · document type |

---

## 7. Management and analytical — P1, all pivots

### R19 · Sales Summary
Your existing cumulative report, rebuilt properly.

| | |
|---|---|
| Grouping | Any combination: product category → product → island → attendant → shift → day → month |
| Content | **Units** and **volume** kept separate (T1/T4/T5 pack sizes) · value · cash vs non-cash split · % of total |
| Filters | All global · tender type · island · nozzle · attendant · customer · cash vs credit |
| Default | This price period, by category then product |

> Do not carry over the legacy grand-total quantity column that adds litres of fuel to bottles of oil to gas cylinders. Split totals by UoM.

### R20 · Margin by Product
| | |
|---|---|
| Content | Landed cost (AVCO) · EPRA cap · achieved price · discounts given · gross margin per litre and % |
| Filters | Product · date range · **price period** · customer · discount given y/n |

### R21 · Throughput Trend
| | |
|---|---|
| Grouping | Day / week / month / price period; by product, island, hour of day |
| Filters | All global · comparison to previous period · exclude delivery days |

### R22 · Pump & Nozzle Performance
| | |
|---|---|
| Content | Litres per nozzle · utilisation · downtime hours · variance history |
| Filters | Island · pump · nozzle · product · date range · downtime only |

### R23 · Non-fuel Sales & Margin
Shop, LPG, lubricants — often a third of gross margin.

| | |
|---|---|
| Grouping | Category → product; LPG separated into refill vs cylinder deposit |
| Content | Units · volume · value · cost · margin · shrinkage vs stock count |
| Filters | Category · product · date range · shift · attendant · below-margin-threshold only |

---

## 8. Build notes

**Only seven need QWeb** — the ones that get signed, filed, or sent to someone: R1 Shift Closure Sheet, R2 Daily Station Report, R3 Wetstock Reconciliation, R6 Tank Loss Analysis, R8 Delivery Reconciliation, R14 Customer Statement, R24 Attendant Shift Statement (plus R18's export).

**Everything else is `_auto = False` SQL views** with list, pivot and graph views. Odoo then gives you grouping, subtotals, grand totals, drill-down, CSV and XLSX export for free. Building those as QWeb is the difference between two weeks and five.

**Saved filters per user.** Each report should ship with 2–3 named favourites matching the defaults above, so nobody rebuilds the same filter set daily.

**Two exclusions from Phase 1.** Price-change elasticity is analysis, not operations — defer it. And residual allocation should never be a standing report; it becomes R10, an exception list. A report you run daily teaches everyone that residuals are normal.

**One report can kill a shift.** R3 and R15 are the two that get read by someone who isn't you. Build those to be handed to a Shell auditor without explanation.
