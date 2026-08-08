# FMS Report Catalogue

**System:** Forecourt Management System — Shell Maanzoni
**Version:** v3
**Purpose:** Definitive list of reports, with filters, groupings and build type

---

# ⛔ Read this first — blockers

**Six reports in this catalogue cannot be built today, and one data-model question blocks a dozen more.** If you have skipped to your report of interest, check this list before estimating it.

| Blocker | Blocks | Detail |
|---|---|---|
| **Product costing + automated AVCO valuation** | F10, F11, R19, R20 | Cost of Revenue currently posts as zero. Until COGS exists, no margin report can be built at any price |
| **Analytic plan design** | F10, F14, F15, and every island-filtered report | A decision taken once at chart-of-accounts time. Retrofitting analytic distribution across posted entries is painful — see §1.6 |
| **Island vs profit centre definition** | R4, R6 grouping, R18, R21, R22, R27, R29 | `island` is used as a filter throughout and has no home in the data model — see §1.6 |
| **`fms.price.period` model** | 7 date presets, R9, F11, all margin reports | See §1.5 |
| **Kenya chart of accounts + equity structure + suspense clearance** | F1–F9 | See §7.1 |
| **Strapping charts loaded** | R3, R6, F12 | See the callout in §2 |
| **Odometer capture decision** | R13 | See the scope warning on R13 |
| **Temperature and density capture at delivery** | R8 | See the scope warning on R8 |
| **`fms.incident` model missing** | R9, and R3's variance quality | Unmodelled incidents land in R3's variance and look like a leak — see the R9 scope warning in §3 |
| **Equipment downtime model missing** | R22, R27 accuracy | Downtime removed from R22's content; without it a downed nozzle reads as a weak attendant |

Three of these — costing, the analytic plan, and the island definition — are **data-model and configuration decisions, not reporting work**. They should be settled before a developer is asked to estimate anything in this document.

---

## 1. Filter conventions

Get these right once and most per-report filter work disappears.

### 1.1 Global filters — present on every report

| Filter | Type | Notes |
|---|---|---|
| Station | Multi-select | HQ users only. Station users are scoped by `ir.rule`, not by a filter — never let a station user *choose* their station |
| Date range | Date range + presets | Presets: Today · Yesterday · This shift · This week · This month · **This price period** · Last 30 days · Custom. See §1.5 — the price-period preset needs a backing model |
| Shift | Multi-select | Day / Evening / Night |
| Product | Multi-select | |
| Product category | Multi-select | White products · Lubricants · LPG · Filters · Accessories · Spares |
| Status | Multi-select | Draft / Open / Closing / Closed / Disputed — default to **Closed only** on financial reports |
| Comparison period | Toggle | Previous period, or same period last year. Needed on every trended report, not just R21 |
| Exception only | Boolean | Hide everything inside tolerance. Will end up being the most-used control in the suite — build it once as a mixin |

### 1.2 Five rules that matter more than the filter list

**Date means shift date, never create date.** A night shift crossing midnight belongs to the shift it opened on. If a report filters on `create_date` it will split night shifts across two days and nothing will ever reconcile.

**The product hierarchy is three levels deep, and every level subtotals.** This is not a design choice — it is the structure the legacy system already uses, verified against the stock valuation and cumulative sales reports, which foot correctly at all three levels.

```
Product Type          →  Product Class        →  Item
White Products        →  Diesel Extra         →  Diesel Extradisplay Structure
Lubricants            →  Engine Oils          →  Helix HX5 15W40 – T4
                      →  Transmission Oils    →  Spirax S2 ATF D2 – T4
                      →  Greases              →  Greasing Runs – T1
                      →  Car Care Products    →  Silicon Grey 85.2 g
LPG & Accessories     →  LPG Gas              →  Gas Load 13 kg
                      →  LPG Cylinders        →  Empty Cylinder 13 kg
Filters               →  Oil / Air / Fuel     →  Oil Filter 90915-10001
```

**Class is the tier most systems drop, and it's the one managers use.** "Lubricants sold KES 388,680" is not actionable; "Engine Oils 303k, Transmission Oils 112k, Car Care 10k" is. Build all three tiers or the reports lose the level people actually make decisions at.

| Product type | UoM captured | Subtotal in |
|---|---|---|
| White products | Litres (qty = volume) | Litres · KES |
| Lubricants | Units **and** volume (T1 / T1½ / T4 / T5 pack sizes) | Units · litres · KES |
| LPG and accessories | Units **and** kg (6 kg / 13 kg) | Units · kg · KES |
| Filters — oil, air, fuel | Units | Units · KES |
| Cabin filters | Units | Units · KES |
| Accessories | Units | Units · KES |
| Other spares | Units | Units · KES |

> UoM is a property of the **type**, so quantity subtotals are valid at type and class level and invalid only at grand total. Unit cost is held per **pack**, not per litre — a 4 L pack carries the pack cost, and volume is derived. Preserve that; it is why the legacy valuation reconciles.

**The value grand total is always valid. The quantity grand total is not.** KES sums across every category. Quantity does not — 207,302 litres of fuel plus 388 bottles of oil plus 22 gas cylinders is a meaningless number, and your legacy report prints it. Either suppress the quantity grand total or emit one total per UoM. Category subtotals in quantity are fine, because a category shares a UoM.

**"This price period" is a first-class preset.** EPRA revises on the 14th, effective the 15th. Your commercial month runs 15th to 14th, not 1st to 31st. Every margin and price-comparison report needs this preset or the numbers blend two price regimes.

**Every filter dimension must also be a group-by dimension.** If a user can filter by attendant, they must be able to group by attendant. This is free in Odoo if you build on `_auto = False` views and don't hardcode filters.

### 1.3 Impossible values — validate at capture, not in the report

Three checks the legacy system does not make. Each one has produced a wrong number in a live report that footed perfectly.

| Rule | Enforce at | Evidence from the legacy system |
|---|---|---|
| **Cash sales can never be negative** | Credit entry, per product, per shift | Diesel showed −663.93 L and −KES 113,134 because keyed credit exceeded metered sales. Cash is derived as `meter − credit` and never checked |
| **Expected cash can never be negative** | Cashier reconciliation | A receipt keyed with the wrong sign gave one cashier expected cash of −11,000 against actual +11,000, reporting a phantom KES 22,000 station-level surplus |
| **Per-nozzle cash variance must be flagged** | Meter entry | One nozzle showed a KES 1,000.21 variance against every other nozzle's sub-5 — a digit transposition that propagated into the product-class total and shifted diesel's average price from 242.90 to 243.49 |

**The principle behind all three: a report that foots is not a report that's right.** Every legacy document reviewed reconciles to the shilling and still carries impossible values, because the arithmetic is applied to unvalidated input. Validation belongs at capture. A reporting layer that inherits bad input can only display it more attractively.

Corollary for the cashier reconciliation, taken verbatim from the legacy formula because it reconciles on every row:

```
Total Credits = Invoices + POS + VISA
Expected Cash = Sales − Total Credits + Receipts − Payments
```

Sign convention matters here and is the source of the second failure above: **receipts increase expected cash, payments reduce it.** Store them with signs that make that arithmetic natural, and reject an entry that drives expected cash below zero.

### 1.4 Defaults beat options

A report that opens on the right question gets read. Each report below specifies its default state — treat that as part of the spec, not a nicety.

### 1.5 The price-period model — a prerequisite, not a filter

`This price period` cannot be computed by hardcoding the 15th. EPRA occasionally extends a period or gazettes an out-of-cycle change, and any report that assumes a fixed calendar rule will silently blend two price regimes on exactly the months where the numbers matter most.

Build one small model before any report that uses the preset:

| Field | Purpose |
|---|---|
| `date_start`, `date_end` | Actual effective dates, entered from the gazette — never derived |
| `gazette_ref` | The EPRA notice, for audit |
| `pricelist_version_id` | Links the period to the prices that applied |
| `region` | Machakos cap differs from Nairobi |

This model is not only a filter source. **R9 (split shifts at a price change) and every margin report depend on it**, so it is a prerequisite for a good part of the suite. One table, high leverage — build it first.

### 1.6 Island and profit centre are two dimensions, not one

`island` is used as a filter across a dozen reports and has no home in the data model. The reason it resists definition is that **one word is carrying two unrelated concepts**:

| Concept | What it is | Where it lives |
|---|---|---|
| **Island** | A physical forecourt structure with nozzles on it. Island 1, Island 2, Island 3 | A field on the nozzle or pump master. Purely physical |
| **Profit centre** | A place that earns money. The forecourt as a whole, the LPG bay, the lube counter, the shop | An analytic account |

Trying to make one field serve both is why the definition keeps slipping. An LPG bay is a profit centre but has no nozzles; Island 2 is a physical structure but usually isn't a profit centre on its own.

**Recommended resolution — two analytic plans, which Odoo supports natively:**

| Plan | Values | Answers |
|---|---|---|
| Business line | Fuel · Lubricants · LPG · Filters & spares · Shop | "Where do we make money?" (F10) |
| Sales point | Island 1 · Island 2 · Island 3 · LPG bay · Lube counter · Shop counter | "Which part of the site earns it?" |

> **The Sales Point values already exist — don't design them.** The legacy shift screen carries these as separate revenue buckets today: Lubes, FC Cards, LPG, Shop Services, Pitstop Services, Car Wash, Tyres/Tubes, Cafe Services, FC Shop, TYC, Staff Debt, FC JCards and Trade Debts, alongside Islands 1–4. That list is a working profit-centre model that has survived years of daily use. Port it and prune it; a clean-sheet design will only rediscover it.

The two plans cross, so you can ask for lubricant margin at the lube counter versus lubricants sold on the forecourt. Physical `island` stays a plain field on the nozzle, used for operational reports (R21, R22, R29); the profit-centre question is answered by the Sales Point analytic plan.

**This is the same decision as §7.1's analytic plan, not a second one.** Settle both together, before the chart of accounts is populated. Every report in this catalogue that filters by island is blocked until it is settled — and a developer who is not told this will invent a definition and hard-code it.

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

> ### ⚠️ Hard dependency — calibrated strapping charts
>
> **R3 cannot be built until each tank's calibration certificate is loaded as a millimetre-to-litre table.** Wetstock reconciliation running on a geometric volume formula produces variances of several hundred litres with no physical cause.
>
> The damage isn't the wrong number. It's that within a fortnight everyone learns to ignore the variance figure — and you do not get that trust back by fixing the chart later. This is the first item in the build order and the most important report in the system; do not start it on approximate volumes.
>
> Same dependency applies to R6 and F12.

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
| Type | **Overview dashboard card + scheduled alert**, with a list behind it |
| Grouping | Tank → product |
| Content | Closing stock · ullage · average daily run rate (7/30-day) · **days of cover** · reorder flag · stock value at AVCO |
| Filters | Station · product · **below reorder point only** · tank |
| Default | Current, all tanks, reorder items first |

> **This must push, not wait to be pulled.** A station that reorders from a report someone remembers to open will still run dry. Reorder point = supplier lead time + safety days, configured per tank, with an `ir.cron` that raises an activity when days of cover falls below it. The list is for investigation; the alert is the product.

---

## 3. Loss and investigation — P0/P1

### R6 · Tank Loss Analysis (SIR)
The defensible answer when Shell asks about a persistent loss.

| | |
|---|---|
| Type | **Algorithm + QWeb PDF + graph** — see warning below |
| Grouping | Tank → 30-day window |
| Content | Cumulative variance · variance as % of throughput · statistical confidence · leak/no-leak/inconclusive verdict · cost impact at AVCO |
| Filters | Tank · date range (min 30 days) · product · verdict · confidence level (95 % / 99 %) · exclude shifts flagged as bad readings |
| Default | Last 30 days, all tanks |

> **This is not a pivot report and must not be estimated as one.** "Statistical confidence" and a leak verdict mean implementing a statistical inventory reconciliation method — a control-chart or hypothesis test over the daily variance series, with a stated null hypothesis, a threshold leak rate, and a defensible confidence level. That is an algorithm with its own test suite, not a query over existing data.
>
> Decide the method before building: a CUSUM-style control chart is simpler to explain to an auditor; a t-test over the variance series is easier to justify statistically. Either way, write the acceptance test as "inject a known 0.2 L/hr leak into 30 days of synthetic data and confirm the verdict flips" — otherwise you cannot prove the thing works, and an unproven leak detector is worse than none.

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

> **Blocked on delivery data capture.** The delivery model has no temperature or density fields, so the temperature-corrected comparison — the part that turns an apparent loss into a claimable one — cannot be computed. Add to the delivery spec: observed temperature and density at loading (from the supplier's document) and at receipt (dip thermometer plus hydrometer), per compartment.
>
> Two practical points before committing: density readings need a hydrometer and someone trained to use it, so this is a process change as well as a field; and comparing loaded against received on different bases produces a variance that looks like loss and is arithmetic. Until both ends are captured, R8 ships as an uncorrected litres-in-versus-litres-out comparison — still useful, but it will not support a supplier claim.
| Drill-down | Delivery → GRN → stock moves |

### R9 · Drive-off & Incident Register
| | |
|---|---|
| Type | List |
| Content | Date · shift · attendant · nozzle · litres · value · plate · OB number · recovery status |
| Filters | Date range · type (drive-off / no-pay / spillage / wrong fuel / calibration test / own use / transfer) · attendant · recovery status · value threshold |
| Default | This month, unrecovered first |

> **Needs its own model — this is not a query over shift data.** Plate, OB number, incident type and recovery status exist nowhere today. R9 requires an `fms.incident` model with a create workflow (who reports it, who approves the write-off), an attendant and nozzle link, an optional attachment for the police abstract, and a stock move so the litres leave inventory as an incident rather than as an unexplained loss.
>
> That last part is the reason it can't wait: **every unmodelled incident lands in R3's variance and looks like a leak.** Parked in §10, but it is the cheapest item there and the one that most improves the quality of your most important report.

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

> **Scope warning.** Only the first stage — cash declared at shift close — is captured today. The rest splits in two:
> - **New capture needed:** the safe-drop event (a POS cash-out to a safe account) and the deposit-slip reference linking a drop to a banking.
> - **Already native:** bank deposit as an internal transfer, and statement matching through Odoo's own reconciliation. This is wiring, not modelling — don't budget it as a build.
>
> Phase 1 delivers **declared → safe drop** only. Say so explicitly, or the report will be signed off as covering a gap it doesn't close.

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

> **Blocked until the odometer source is decided.** No odometer field exists anywhere in the model today. Realistically it is keyed by the attendant or cashier onto the credit sale line at the point of fuelling; a fleet-card integration is the alternative.
>
> Two things must ship with it or the report is worse than useless:
> - **Validation.** Must exceed the vehicle's previous reading, and the implied km must be plausible for the elapsed interval. Without a constraint, attendants type 12345 or drop a digit, and the data is unusable within a month.
> - **Completeness detection.** Litres per 100 km is only meaningful if the vehicle fuels exclusively with you. A fleet that tops up elsewhere yields nonsense. The report must detect a gapped fuelling history and label the row as incomplete rather than print a wrong consumption figure.

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

> **Payroll write-back is not scoped.** The `payroll period deducted` field implies FMS pushes a deduction into payroll. It does not, and shouldn't without a decision. Phase 1: the report shows the outstanding amount and a manually-set status; recovery happens in payroll and someone marks it here. If you want the integration, scope it as generating a payroll input line for review — never a direct deduction.
>
> Worth confirming before designing either version: Kenyan employment law places statutory limits on deductions from wages and on what requires written consent. A system that automatically deducts a shortage could put you outside those limits without anyone noticing. Check the current position with whoever handles your HR compliance before automating this step.
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

> **Open question — answer before building.** Do attendants actually swap nozzles mid-shift at this station (breaks, prayers, covering a busy island)?
> - **If yes:** a handover event model is required, nozzle assignment becomes time-bounded, and the "two lines per nozzle" rule in this section's preamble stands.
> - **If no:** assignment is fixed at shift open, R29 collapses to a simple per-shift assignment list, and the meter entry can keep a single attendant field.
>
> The current model assumes the second. If reality is the first, every attendant report inherits a wrong attribution, so this is worth confirming on the forecourt rather than in a meeting.

---

## 6. Compliance and audit — P0

### R15 · Shift Closure Audit Log
| | |
|---|---|
| Type | List, immutable |
| Content | Gate outcomes · failures · reason codes · overrides · who · when · **from which device/IP** · time between reading and entry |
| Filters | Date range · shift · supervisor · user · gate · pass/fail · override only · reason code |
| Default | Last 30 days, failures and overrides only |

> **Device and IP are not captured by default.** Odoo's ORM tracking records who and when, not where from. Capturing it means reading the request context at shift close and writing it onto the log record — a small hook, but one that has to be designed in rather than added afterwards, because it cannot be reconstructed retrospectively.
>
> It earns its place: a closing dip entered at 03:00 from an off-site address is a signal you cannot get any other way. Decide now whether you want it; an auditor asking later is the wrong time to find out it was designed out.

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

> **Separate scope item — not a report.** Nothing here derives from shift data. It needs its own model: asset link, certificate type, issuing authority, issue and expiry dates, document attachment, and an `ir.cron` raising activities ahead of expiry. Small, cheap, and genuinely required before an inspection — but scope and estimate it as a feature, not as a report.

### R18 · Tax Sales Summary (eTIMS handoff)
| | |
|---|---|
| Type | List + export |
| Grouping | Tax rate → product → date |
| Filters | Date range · tax rate · product · exported/not exported · document type |

> **This is an integration, not a report, and it will be badly underestimated if listed here.** KRA eTIMS requires prescribed invoice formats, controlled sequence numbering, signed transmission and confirmation receipts held against each document. That is a compliance integration with its own failure modes — rejections, retries, sequence gaps — and it was already agreed to live in a separate app. What belongs in this catalogue is only the **handoff view**: what is pending transmission, what was accepted, what was rejected. Scope and estimate the integration separately.

---

## 7. Financial reports — P0

**Most of this section should not be built.** F1–F9 are standard accounting reports that ship with OCA modules; they are listed so the suite is complete and so nobody re-implements a trial balance from scratch. What genuinely needs building is F10–F15 — the station-specific financial analysis that no generic module can produce.

### 7.1 Prerequisites — nothing in this section works until these are fixed

Current accounting configuration will not support any of it. In order:

| Prerequisite | Why it blocks |
|---|---|
| Real company record and Kenya chart of accounts | Currently the demo company with a single generic expense account |
| **Products on automated real-time inventory valuation with AVCO, and costed** | Cost of Revenue is presently zero against six figures of sales. Until COGS posts, **no margin report in this catalogue can exist** |
| Equity section properly structured | The balance sheet currently has none; profit is nested under Liability |
| Bank suspense cleared and monitored | A large suspense balance means the bank figure is meaningless |
| Expense accounts broken out by nature | One catch-all account makes F14 impossible |
| **Analytic plan for business lines** | Fuel / lubricants / LPG / shop, applied by analytic distribution on products |

> **The analytic plan is a design decision, not a setting.** Per-business-line profitability cannot be derived from the chart of accounts alone — you would need duplicate account trees per line, which is unmaintainable. Set up one analytic plan with a distribution rule per product category, and F10 comes free while the statutory reports stay clean. Decide this before the chart of accounts is populated; retrofitting analytic distribution across posted entries is painful.

### 7.2 Statutory and standard — configure, don't build

> **Status of these module choices: confirmed on 18.0, pending on 19.0.**
>
> The 18.0 branches of `account_financial_report` and `mis-builder` are stable and available today — if you build on 18, treat the table below as decided and estimate accordingly.
>
> The 19.0 migrations were still in progress at last check, with open PRs on both. If the Odoo 19 upgrade proceeds, **re-verify the specific modules on the 19.0 branch before the port**, because an unported dependency blocks the whole upgrade, not just these reports.
>
> This is not a caveat to work around — it is a real input to the 18-vs-19 timing decision. Confirm branch readiness on the day you commit to an upgrade date, and record the answer here.

| # | Report | Source | Key filters |
|---|---|---|---|
| F1 | Balance Sheet | `mis_builder` + `mis_template_financial_report` | Date to · company · comparison period · posted only · **must show Equity** |
| F2 | Profit & Loss | same | Date from **and** to (never open-ended) · comparison · analytic (business line) · posted only |
| F3 | Cash Flow Statement | `mis_builder_cash_flow` | Period · company · comparison |
| F4 | Trial Balance | `account_financial_report` | Date range · account range · journal · with/without opening balance · hide zero balances |
| F5 | General Ledger | `account_financial_report` | Date range · account · journal · partner · analytic · posted vs all · centralised or detailed |
| F6 | Aged Receivable / Payable | `account_financial_report` | As-of date · partner · aging intervals · currency · overdue only |
| F7 | Open Items | `account_financial_report` | As-of date · partner · account · currency |
| F8 | Journal Ledger | `account_financial_report` | Period · journal · posted vs all · grouping |
| F9 | Tax report | `account_financial_report` / Kenya localisation | Period · tax rate · document type — feeds R18 |

> F6 overlaps R12 deliberately. **F6 is the accounting view** — aging by partner, for the accountant. **R12 is the operational view** — credit limits, exposure, vehicles, fuel volume, for you. Same underlying data, different questions; don't collapse them.

### 7.3 Station financial reports — build these

| # | Report | Content | Key filters |
|---|---|---|---|
| F10 | **Business Line P&L** | Revenue, COGS, gross margin, margin %, share of total — split fuel / lubricants / LPG / filters / shop. **The report that tells you where money is actually made** | Period · business line · comparison period · price period |
| F11 | Fuel Margin vs EPRA Cap | Landed cost at AVCO · gazetted cap · achieved price · margin per litre · discount leakage · margin erosion vs list | Price period · product · customer · discount scheme |
| F12 | Wetstock Loss Valued | R3's variance in litres valued at AVCO, per tank and product, monthly and cumulative, traced to the GL entry it produced | Period · tank · product · explained vs unexplained · cumulative basis |
| F13 | Cash & Bank Position | Bank balances · **suspense balance and its age** · unreconciled statement lines, count and oldest · cash in hand · unbanked cash from R11 | As-of date · journal · unreconciled only · older than *n* days |
| F14 | Expense Analysis | By category and period, with comparison and share of revenue | Period · account category · comparison · analytic line |
| F15 | Working Capital | Debtor days · stock days · creditor days · cash conversion cycle, monthly trend | Period · comparison · business line |

> **F12 is the report that makes wetstock a financial fact rather than an operational statistic.** R3 tells the station it lost 400 litres; F12 tells the business it lost KES 68,560 and shows the journal entry. That translation is what gets a leak funded for repair.

> **F13 exists because of the suspense problem.** A suspense account is meant to be a staging area, not a balance. Give it a permanent monitor with an age on it, or it silently becomes the place unexplained money lives.

### 7.4 Build stance for this section

A clean division that decides the build type for every report in the catalogue:

- **Anything sourced from the general ledger → a `mis_builder` template.** Period comparison, budgets, drill-down to journal items and Excel export come free, and the template is editable without a developer.
- **Anything sourced from operations — litres, meters, dips, nozzles → an `_auto = False` SQL view.** That data isn't in the GL and never will be.

F10 through F15 are all GL-based, so none of them is a new SQL view. F12 is the one hybrid: it takes litres from the operational side and values them at AVCO, so it reads from both.

## 8. Management and analytical — P1, all pivots

### R19 · Sales Summary
Your existing cumulative report, rebuilt properly.

| | |
|---|---|
| Type | `_auto = False` SQL view + pivot |
| Grouping | Any combination: product category → product → island → attendant → shift → day → month |
| Content | **Units** and **volume** kept separate (T1/T4/T5 pack sizes) · value · cash vs non-cash split · % of total |
| Filters | All global · tender type · island · nozzle · attendant · customer · cash vs credit |
| Default | This price period, by category then product |

> Do not carry over the legacy grand-total quantity column that adds litres of fuel to bottles of oil to gas cylinders. Split totals by UoM.

### R20 · Margin by Product
| | |
|---|---|
| Type | `mis_builder` template — GL-sourced (see §7.4) |
| Content | Landed cost (AVCO) · EPRA cap · achieved price · discounts given · gross margin per litre and % |
| Filters | Product · date range · **price period** · customer · discount given y/n |

### R21 · Throughput Trend
| | |
|---|---|
| Type | `_auto = False` SQL view + graph |
| Grouping | Day / week / month / price period; by product, island, hour of day |
| Filters | All global · comparison to previous period · exclude delivery days |

### R22 · Pump & Nozzle Performance
| | |
|---|---|
| Type | `_auto = False` SQL view + pivot |
| Content | Litres per nozzle · utilisation vs island peers · average fill size · transactions · variance history |
| Filters | Island · pump · nozzle · product · date range |

> **Downtime is deferred — nothing records when a pump goes out of service.** I've removed downtime hours from the content above rather than leave a field with no source. The rest of R22 ships today from meter data.
>
> Downtime needs an equipment event model (out-of-service from/to, reason, who reported it), parked in §10 alongside R9's incident model. It's worth building eventually for one reason: **without it, a nozzle that was down for six hours reads as an underperforming attendant.** R22 and R27 will both quietly blame a person for a mechanical fault until downtime exists.

### R23 · Non-fuel Sales & Margin
Shop, LPG, lubricants. Hybrid: units and volume come from operations, margin from the GL.

| | |
|---|---|
| Type | `_auto = False` SQL view for volumes + `mis_builder` for margin |
| Grouping | Category → product; LPG separated into refill vs cylinder deposit |
| Content | Units · volume · value · cost · margin · shrinkage vs stock count |
| Filters | Category · product · date range · shift · attendant · below-margin-threshold only |

> **How the two halves compose.** Don't surface these as two reports. The SQL view supplies units, volume and value by category; the `mis_builder` template supplies cost and margin from the GL. Join them on **product category + period**, which both sides already carry.
>
> Two workable patterns, in order of preference:
> - **One action, two tabs** — "Volumes" and "Margin". Cheapest, and honest about the fact that they refresh independently.
> - **Single view, GL-sourced** — put units and volume into the analytic side so `mis_builder` can render everything. Cleaner to read, but it means the volume figures depend on analytic distribution being correct, which couples this report to §1.6's plan design.
>
> Take the tabs unless F10 has already proved the analytic plan works. R23 is P1; it shouldn't be the report that discovers a problem with your analytic setup.

---

## 9. Build order

Sequenced by what stops the station working, not by what's interesting.

**Prerequisite — before any report:** the `fms.price.period` model (§1.5). Seven date presets and every margin report depend on it.

**Prerequisite — before any financial report:** the accounting configuration in §7.1, and the analytic plan decision in particular. Product costing with automated AVCO valuation is the hard blocker — without COGS posting, F10, F11, R19 and R20 cannot be built at all, however good the reporting addon is.

| Order | Reports | Why here |
|---|---|---|
| 1 | R1, R2, R3 | The morning routine. These three replace the manual spreadsheet |
| 2 | R4, R24 | Attendant accountability. Required for shift-close sign-off |
| 3 | **Credit limit block at point of sale** | Not a report — a control. ~90 % of fuel value is non-cash and diesel is 96 % credit. This protects more money than anything else on the list |
| 4 | R5 | Ordering. As an alert, not a list |
| 5 | R12, **F6** | Debtors. Mostly native Odoo aging, so cheap once the limit block exists |
| 6 | R11 (declared → drop only), **F13** | Cash control, scoped honestly — and a permanent watch on the suspense account |
| 7 | **F1–F9** | Statutory reporting. Configuration of OCA modules, not development |
| 8 | **F10, F11, F12** | Where the money is made, and what wetstock loss actually costs |
| 9 | Everything else | Useful, not blocking |

> **Build order 1 carries a hard dependency: calibrated strapping charts must be loaded before R3 starts.** Full note in the R3 entry in §2. It also blocks R6 and F12.

### Build order item 3 — the credit limit block

This sits above ordering and debtors in the sequence, and it is the only entry that isn't a report, so it needs a spec of its own.

**What it is.** A hard stop that prevents a credit sale being recorded against a customer who is over their limit, with a logged supervisor override.

**Where it lives.** At the point the credit sale is recorded — customer selection on the POS order or invoice creation, whichever route the forecourt actually uses. Not at invoice posting; by then the fuel is gone.

**The exposure calculation is the part that gets built wrong.** Checking posted receivables alone understates exposure during a shift, because that day's uninvoiced sales aren't posted yet. Exposure must be:

```
posted AR balance
+ unposted credit sales in open shifts
+ delivered-but-uninvoiced orders
```

A limit check against posted AR only will pass a customer who has already blown through their limit today.

**Behaviour.**

| Condition | Action |
|---|---|
| Within limit | Proceed silently |
| Within 90 % of limit | Warn the cashier, allow |
| Over limit | Block, with supervisor override requiring a reason code |
| Account on hold | Block, no override |

**The honest constraint.** Fuel is dispensed before the sale is recorded, so this check is advisory at the moment that matters most. It stops the *next* sale, not the one in progress. Closing that gap properly means authorising the customer at the pump before the nozzle is released, which is a PTS-2 and fleet-card question rather than an accounting one — worth noting as a Phase 2 ambition rather than pretending the Phase 1 control is complete.

**Why it ranks this high.** Around 90 % of fuel value is non-cash and diesel is 96 % credit. Every report in §4 tells you about exposure after it exists; this is the only item in the catalogue that prevents it.

## 10. Not reports — separate scope items

These appear in the catalogue because they belong on the same screens, but none of them derive from shift data. Estimating them alongside SQL views will underprice the project.

| Item | What it actually is |
|---|---|
| `fms.price.period` | A model. Prerequisite for the suite |
| R13 Fleet Consumption | Blocked on an odometer capture decision, plus validation and completeness logic |
| R17 Calibration & Licence Register | A document register with its own model and expiry cron |
| R18 eTIMS | A compliance integration in a separate app; only the handoff view is a report |
| R5 reorder alerting | A scheduled action and per-tank reorder configuration |
| R11 banking stages | Safe-drop capture is new; deposit and statement matching are native wiring |
| R29 handover | Depends on the open question above |
| Accounting configuration (§7.1) | Company, Kenya chart of accounts, product costing and AVCO valuation, equity structure, suspense clearance. Not a report — a setup project, and a blocker for six of them |
| Analytic plan for business lines | A design decision taken once, at chart-of-accounts time. Cheap now, expensive to retrofit across posted entries |
| OCA module evaluation | `account_financial_report` and `mis-builder` on staging, in parallel with the existing kit. Check the 19.0 branch readiness before committing to that upgrade date |
| **Island / profit-centre definition** | A data-model decision (§1.6), not a filter. Blocks every island-grouped report |
| **R6 SIR algorithm** | A statistical method with its own acceptance tests, not a pivot report |
| **R8 temperature & density capture** | New fields on the delivery model, plus a hydrometer and a trained process |
| **R26 payroll write-back** | Out of scope unless explicitly funded. Manual recovery, status marked in the report |
| **Credit limit block** | A control, not a report. Spec in §9 |
| **R9 Incident register** | Needs an `fms.incident` model with a create workflow and a stock move. Cheapest item in this table, and the one that most improves R3's variance quality |
| **Equipment downtime** | An out-of-service event model. Removed from R22's content until it exists. Protects attendants from being blamed for mechanical faults |
| **R15 device/IP capture** | A request-context hook at shift close. Cannot be reconstructed retrospectively — design it in or drop it deliberately |
| **Legacy data cleanup** | Five known warts to fix at migration, not after: zero-volume litre products (Spirax S5 ATF X T1); discounts encoded as fractional quantities (a car wash of 0.75); items filed under the wrong class (an oil filter under Cabin Filters, an air cleaner under Fuel Filters); LPG cylinders held as stock when exchange cylinders are a deposit liability; quantity grand totals mixing litres with bottles |

## 11. Build notes

**Only seven need QWeb** — the ones that get signed, filed, or sent to someone: R1 Shift Closure Sheet, R2 Daily Station Report, R3 Wetstock Reconciliation, R6 Tank Loss Analysis, R8 Delivery Reconciliation, R14 Customer Statement, R24 Attendant Shift Statement (plus R18's export).

**Everything else is `_auto = False` SQL views** with list, pivot and graph views. Odoo then gives you grouping, subtotals, grand totals, drill-down, CSV and XLSX export for free. Building those as QWeb is the difference between two weeks and five.

**Saved filters per user.** Each report should ship with 2–3 named favourites matching the defaults above, so nobody rebuilds the same filter set daily.

**Two exclusions from Phase 1.** Price-change elasticity is analysis, not operations — defer it. And residual allocation should never be a standing report; it becomes R10, an exception list. A report you run daily teaches everyone that residuals are normal.

**One report can kill a shift.** R3 and R15 are the two that get read by someone who isn't you. Build those to be handed to a Shell auditor without explanation.