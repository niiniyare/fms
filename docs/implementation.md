# Shell Maanzoni — Forecourt Management System (FMS)
## Comprehensive Implementation Roadmap
### ERPNext v15 + Frappe Framework + PTS-2 Integration

**Version:** 1.0.0  
**Station:** Shell Maanzoni Service Station (Anika Global Limited)  
**Prepared for:** Claude Code CLI-assisted development  
**Currency:** KES  
**Date:** June 2026

---

## How to Read This Document

This roadmap is structured for a solo developer building with Claude Code CLI. Each phase produces a **working, testable deliverable** before the next begins. No phase assumes the next one exists.

The document is organized in four parts:

- **Part A** — Business analysis: what the existing system does and what must be preserved
- **Part B** — System design: architecture, DocTypes, data model, business logic
- **Part C** — Implementation plan: phase-by-phase work items with Claude Code prompts
- **Part D** — Reference material: calculations, SQL, test cases, migration guide

---

# PART A — BUSINESS ANALYSIS

## A.1 What the Existing System Produces

Two files were analyzed: the legacy Meter Movements PDF (26 Dec 2024) and the matching Excel workbook (Shift Entry + Meter Movements sheets, dated 15 Jun 2026).

### A.1.1 The Meter Movements Report — Column-by-Column

The report is the central daily accountability document. Each row is one pump-nozzle combination. Rows are grouped by product/tank: V-Power (T1), Unleaded Extra (T2), Diesel Extra (T3).

| Column | Header | Source | Business meaning |
|--------|--------|--------|-----------------|
| 1 | PUMP | Master | Pump-tank code e.g. P1-T1, U1-T2, L1-T3 |
| 2 | MANUAL MTR — OPEN | Attendant reads physical odometer wheels at shift start | Opening manual mechanical totalizer (litres, 0.01 L precision) |
| 3 | MANUAL MTR — CLOSE | Attendant reads physical odometer wheels at shift end | Closing manual mechanical totalizer |
| 4 | ELECTRONIC MTR — OPEN | Attendant reads digital display or PTS reads automatically | Opening electronic volume totalizer (litres, 0.001 L precision) |
| 5 | ELECTRONIC MTR — CLOSE | As above | Closing electronic volume totalizer |
| 6 | MANUAL LTRS | Computed: Close − Open (manual) | Volume dispensed per manual meter |
| 7 | ELEC LTRS | Computed: Close − Open (electronic) | Volume dispensed per electronic meter |
| 8 | DIFF LTRS | Computed: Manual Ltrs − Elec Ltrs | Divergence between the two meters |
| 9 | SHORT (EXCESS) | Conditional: only filled when Diff < 0 (short) | Negative divergence — electronic reads MORE than manual |
| 10 | METER AMOUNT (KES) — OPEN | Cash totalizer opening value | Cumulative KES totalizer at shift open |
| 11 | METER AMOUNT (KES) — CLOSE | Cash totalizer closing value | Cumulative KES totalizer at shift close |
| 12 | MTR SOLD AMT | Cash totalizer close − open | KES value per electronic cash meter |
| 13 | CASH LTRS | Computed or entered | Volume cross-check against cash amount |
| 14 | EXP PRICE | EPRA rate locked at shift open | Expected price per litre (KES) |
| 15 | EXP SALE AMT | Manual Ltrs × EXP PRICE | Expected sales value based on manual meter |
| 16 | CASH AMOUNT | Actual cash collected for this pump | Reconciled against EXP SALE AMT |

### A.1.2 Live Data From the December 2024 PDF

**V-Power (T1) — 8 pumps, price KES 187.90/L:**

| Pump | Man Open | Man Close | Man Ltrs | Elec Ltrs | Diff | Cash Collected |
|------|----------|-----------|----------|-----------|------|---------------|
| P1-T1 | 39,380 | 39,432 | 52.00 | 52.26 | −0.26 | 9,932.00 |
| P2-T1 | 60,865 | 60,955 | 90.00 | 89.94 | +0.06 | 16,900.00 |
| P5-T1 | 28,895 | 28,961 | 66.00 | 66.55 | −0.55 | 12,505.31 |
| P6-T1 | 41,862 | 41,878 | 16.00 | 15.96 | +0.04 | 3,000.00 |
| P8-T1 | 53,521 | 53,554 | 33.00 | 32.91 | +0.09 | 6,183.79 |
| **Subtotal** | | | **257.00** | **257.62** | **−0.62** | **48,521.10** |

**Unleaded Extra (T2) — 8 pumps, price KES 176.20/L:**
Total: 1,598.00 manual litres, 1,597.67 electronic litres, KES 281,521.82 collected.

**Diesel Extra (T3) — 8 pumps, price KES 165.00/L:**
Total: 3,177.00 manual litres, 3,178.37 electronic litres, KES 524,431.05 collected.

**Station Grand Total:** 5,032 manual litres, 5,033.67 electronic litres, KES 854,474.87 cash.

### A.1.3 The Short (Excess) Flag Logic

The `SHORT (EXCESS)` column (column 9) has a specific conditional:
- Filled only when Diff < 0 (i.e., electronic reads MORE than manual = "short")
- Positive Diff (manual > electronic) is NOT flagged — this is normal meter drift
- The "short" figure is always the negative Diff value carried forward

This is the primary per-pump variance signal in the current system.

### A.1.4 Calculations Verified Against Source Data

```
P1-T1 (V-Power, Dec 2024):
  Manual Ltrs  = 39,432 − 39,380           = 52.00
  Elec Ltrs    = 39,445.951 − 39,393.694   = 52.257
  Diff         = 52.00 − 52.257            = −0.257
  Short        = −0.257 (Elec > Manual → short)
  Exp Sale Amt = 52.00 × 187.90            = 9,770.80
  Cash Amount  = 9,932.00 (actual collected — differs from Exp by KES 161.20)

L1-T3 (Diesel Extra, Dec 2024):
  Manual Ltrs  = 1,250,349 − 1,249,119     = 1,230.00
  Elec Ltrs    = 1,250,384.248 − 1,249,153.256 = 1,230.992
  Diff         = 1,230.00 − 1,230.992      = −0.992
  Short        = −0.992
  Exp Sale Amt = 1,230.00 × 165.00         = 202,950.00
  Cash Amount  = 203,113.68
```

### A.1.5 The Shift Entry Sheet

The Excel workbook's second sheet (Shift Entry) is the **data entry form** — attendants type the four opening/closing totalizer values per pump and the cash amount. All derived columns compute automatically. The FMS must replicate this as a guided, validated digital form.

---

## A.2 What Must Be Preserved Exactly

1. **Pump naming convention:** `P[N]-T1` (V-Power), `U[N]-T2` (Unleaded), `L[N]-T3` (Diesel)
2. **Three meter types, always captured:** Manual (mechanical odometer), Electronic Volume (digital litre display), Electronic Cash (KES totalizer)
3. **The Short (Excess) conditional:** Only flag when Elec > Manual
4. **Product grouping:** V-Power → T1, Unleaded Extra → T2, Diesel Extra → T3
5. **EPRA price locked at shift open** — mid-shift price changes don't contaminate the shift
6. **Subtotals per product and a Grand Total row**
7. **Per-pump Cash Amount** — reconciled against Exp Sale Amount, not just totals
8. **Report header:** Station name, shift date, shift number, operator name

---

## A.3 Gaps in the Existing System

The existing system does NOT do:

| Gap | Business Risk | FMS Resolution |
|-----|--------------|----------------|
| No tank dip readings | Wetstock losses invisible | Tank Dip Reading DocType + shift-close wetstock reconciliation |
| No per-cashier cash breakdown | Cash shortfalls untraceable to individual | Cashier Session + Cash Reconciliation sheet |
| No delivery dip cross-check | Supplier short-delivery undetected | Fuel Delivery Dip DocType |
| No GL journal entries | Revenue/COGS never hits accounting ledger | Auto-posted JE at shift close |
| No fraud detection on dispensed-but-not-billed | Attendant can dispense without invoicing | POS Invoice vs Elec Cash totalizer reconciliation |
| No pump status monitoring | Pump failures discovered late | PTS-2 Status payload → Forecourt Alert |
| No historical variance trending | Calibration problems visible too late | Wetstock Variance Trend report |

---

# PART B — SYSTEM DESIGN

## B.1 High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  SHELL KENYA HQ (Optional multi-site layer)                          │
│  ERPNext Web — cross-site reporting, price management                │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
            ┌───────────────▼──────────────┐
            │   Frappe Bench Server         │
            │   ERPNext v15 Core + fms app  │
            │   MariaDB 10.6+               │
            │   Redis + Frappe RQ           │
            └──────┬──────────────┬─────────┘
                   │              │
      ┌────────────▼───┐    ┌─────▼──────────┐
      │  PTS-2          │    │  Manual Entry   │
      │  Controller     │    │  (Shift Entry   │
      │  (HTTP Push +   │    │   Form)         │
      │   WebSocket)    │    └─────────────────┘
      └────────────────┘
             │
    ┌────────┴──────────┐
    │  Pump Islands     │
    │  P1-P8 (T1 VP)   │
    │  U1-U8 (T2 UX)   │
    │  L1-L8 (T3 DX)   │
    └───────────────────┘
```

## B.2 Technology Stack

| Layer | Choice | Notes |
|-------|--------|-------|
| ERP | ERPNext v15 / Frappe v15 | Python 3.11+ |
| Database | MariaDB 10.6+ | UTF8MB4 charset |
| Cache / Queue | Redis + Frappe RQ | Background jobs |
| PTS-2 Protocol | jsonPTS over HTTPS + WebSocket | Technotrade SDK |
| Serial (fallback) | pySerial 3.5+, pymodbus 3.x | For non-PTS sites |
| Web server | Gunicorn + Nginx | SSL via Certbot |

---

## B.3 Complete DocType Reference

### B.3.1 Master DocTypes

#### Pump Master

Fields:
- `pump_code` — Data, e.g. "P1-T1", "U5-T2", "L3-T3"
- `pump_prefix` — Select: P (V-Power) / U (Unleaded) / L (Diesel)
- `island_number` — Int, 1–4
- `tank` — Link → Warehouse (Tank 1/2/3)
- `fuel_product` — Link → Item
- `pts2_pump_number` — Int (hardware pump number in PTS-2)
- `is_active` — Check
- `pts2_device` — Link → PTS2 Device
- `company` — Link → Company

#### Nozzle (child table of Pump)

- `nozzle_number` — Int
- `is_active` — Check

#### Tank (Warehouse with custom fields)

- `fms_is_fuel_tank` — Check
- `fms_tank_code` — Select: T1 / T2 / T3
- `fms_fuel_product` — Link → Item
- `fms_capacity_litres` — Float
- `fms_pts2_tank_number` — Int
- `fms_reorder_level_ltrs` — Float

#### Fuel Price History

One record per EPRA price change.
- `effective_date` — Date
- `effective_shift` — Select: Current / Next Shift / Scheduled
- `price_pms_unl` — Currency (KES/L)
- `price_pms_vp` — Currency
- `price_ago` — Currency
- `epra_gazette_reference` — Data
- `approved_by` — Link → User

---

### B.3.2 Operational DocTypes

#### Shift (Master)

Status machine: `Draft → Open → Readings Captured → Closing → Closed` (or `Disputed`)

Key fields:
- `company`, `station`, `shift_date`, `shift_label`, `shift_number`
- `status`, `opened_at`, `closed_at`
- `cashier`, `supervisor` (must differ)
- `rate_vp`, `rate_ux`, `rate_dx` (EPRA rates locked at open)
- `float_amount`
- `meter_validation_ok` — Check (system-set)
- `gl_journal` — Link → Journal Entry

Validation rules:
- Only one Open or Closing shift per station at a time
- Cashier ≠ Supervisor
- Cannot move to Closed without gl_journal

---

#### Meter Reading (Three Types, One DocType)

Key design: `meter_type` field differentiates the three readings — no separate DocTypes.

Fields:
- `shift` — Link → Shift
- `pump` — Link → Pump
- `nozzle_number` — Int
- `meter_type` — Select: **Electronic Volume** / **Electronic Cash** / **Manual Mechanical**
- `reading_position` — Select: Shift Open / Shift Close / Spot Check / Amendment
- `totalizer_value` — Float
- `unit` — Auto-set: Litres (Elec Vol + Man Mech) or KES (Elec Cash)
- `observed_at` — Datetime
- `read_by` — Link → Employee
- `witnessed_by` — Link → Employee
- `superseded_by` — Link → Meter Reading (for amendments)
- `amendment_reason` — Text

Immutability rule: Once submitted, `totalizer_value` is locked. Corrections require an Amendment reading.

Closing > Opening validation: Totalizers only count forward — closing < opening throws.

---

#### Meter Reading Summary (computed, per shift close)

This is the FMS equivalent of the legacy Meter Movements Report. Auto-generated when "Compute Meter Summary" is triggered at shift close. One record per shift; child rows per pump.

**Child table — Pump Meter Summary:**

| Field | Computed from |
|-------|--------------|
| `pump` | Pump master |
| `pump_code` | e.g. "P1-T1" |
| `fuel_product` | From pump.fuel_product |
| `man_mtr_open` | Opening Manual Mech totalizer_value |
| `man_mtr_close` | Closing Manual Mech totalizer_value |
| `elec_mtr_open` | Opening Electronic Volume totalizer_value |
| `elec_mtr_close` | Closing Electronic Volume totalizer_value |
| `cash_mtr_open` | Opening Electronic Cash totalizer_value |
| `cash_mtr_close` | Closing Electronic Cash totalizer_value |
| `manual_ltrs` | man_mtr_close − man_mtr_open |
| `elec_ltrs` | elec_mtr_close − elec_mtr_open |
| `diff_ltrs` | manual_ltrs − elec_ltrs |
| `short_excess` | diff_ltrs if diff_ltrs < 0 else NULL |
| `mtr_sold_amt` | cash_mtr_close − cash_mtr_open |
| `cash_ltrs` | elec_ltrs (cross-check field) |
| `exp_price` | Shift rate for this product |
| `exp_sale_amt` | manual_ltrs × exp_price |
| `cash_amount` | From cashier reconciliation for this pump |
| `check_a_status` | Pass / Warning / Fail |
| `check_b_status` | Pass / Warning / Fail / Critical |

**Product subtotals** computed from child rows. Grand total across all products.

This DocType generates the print format that replicates the legacy Meter Movements Report exactly.

---

#### Cashier Session

One per cashier per shift.

- `shift` — Link → Shift
- `cashier` — Link → Employee
- `till_gl_account` — Link → Account
- `float_amount` — Currency
- `actual_cash_close` — Currency (entered when cashier counts till)
- `counted_by` — Link → Employee
- `verified_by` — Link → Employee (must differ)

Cash formula (mirrors paper Cash Reconciliation Sheet):
```
Expected Cash = Sales − Invoices − POS Payments − VISA Card + Receipts − Payments Out
Cash Over/Under = Actual Cash Close − Expected Cash
```

---

#### Cash Event

Every cash movement within a shift.

- `shift`, `cashier_session`
- `event_type` — Select: Float Issued / Cash Pickup / Payout / Safe Drop
- `amount` — Currency
- `authorised_by` — Link → Employee (must differ from session cashier)
- `occurred_at` — Datetime
- `envelope_reference` — Data (required for Pickup / Safe Drop)

---

#### Tank Dip Reading

- `shift`, `company`, `tank`
- `reading_datetime` — Datetime
- `reading_type` — Select: Shift Open / Shift Close / Delivery Before / Delivery After / Spot
- `reading_source` — Select: Manual Dipstick / ATG Electronic
- `dip_height_mm` — Float
- `volume_observed_l` — Float (auto-derived via calibration chart if dipstick)
- `water_level_mm` — Float (alert if > 20mm)
- `read_by` — Link → Employee

---

#### Tank Calibration Chart

EPRA-certified strapping table converting dip height to volume.

- `tank` — Link → Warehouse
- `calibration_date` — Date
- `certificate_number` — Data
- `certifying_body` — Data
- `next_calibration_due` — Date

Child table `Calibration Chart Row`:
- `dip_height_mm` — Float
- `volume_ltrs` — Float

Interpolation logic (linear between rows):
```python
def derive_volume(dip_mm, chart):
    rows = sorted(chart.chart_rows, key=lambda r: r.dip_height_mm)
    for i in range(len(rows) - 1):
        lo, hi = rows[i], rows[i+1]
        if lo.dip_height_mm <= dip_mm <= hi.dip_height_mm:
            ratio = (dip_mm - lo.dip_height_mm) / (hi.dip_height_mm - lo.dip_height_mm)
            return lo.volume_ltrs + ratio * (hi.volume_ltrs - lo.volume_ltrs)
    raise ValueError(f"Dip {dip_mm}mm out of calibration range")
```

---

#### Fuel Delivery Dip

Links a fuel delivery to its before/after dip readings.

- `shift`, `company`, `tank`, `fuel_product`
- `delivery_start`, `delivery_end` — Datetime
- `truck_reg`, `driver_name`, `docket_number`
- `docket_volume_l` — Float (from supplier document)
- `dip_before` — Link → Tank Dip Reading
- `dip_after` — Link → Tank Dip Reading
- `sales_during_offload_l` — Float
- `dip_measured_l` — Float (computed: after vol − before vol + sales during)
- `delivery_variance_l` — Float (docket − measured)
- `delivery_variance_pct` — Float
- `status` — Select: Pending / Accepted / Disputed
- `purchase_receipt` — Link → Purchase Receipt

Variance rule: |variance_pct| > 0.5% → status must be Disputed before GRN submission.

---

#### Shift Reconciliation

Computed at shift close. Aggregates all cashier, wetstock, and meter data.

**Child Table 1 — Cashier Summary** (mirrors the paper Cash Reconciliation Sheet):

| Field | Notes |
|-------|-------|
| `cashier` | Employee |
| `sales` | Σ POS Invoice amounts |
| `invoices` | Fleet/credit sales (non-cash deduction) |
| `pos_payments` | Mobile money (non-cash deduction) |
| `visa_card` | Card payments (non-cash deduction) |
| `total_credits` | invoices + pos_payments + visa_card |
| `receipts` | Adjustments in |
| `payments_out` | Cash pickups, safe drops |
| `expected_cash` | sales − total_credits + receipts − payments_out |
| `actual_cash` | Physically counted |
| `cash_over_under` | actual_cash − expected_cash |

**Child Table 2 — Tank Wetstock Summary:**

| Field | Computed from |
|-------|--------------|
| `tank` | Warehouse |
| `opening_stock_l` | Shift Open dip |
| `deliveries_l` | Σ accepted Fuel Delivery Dips |
| `elec_vol_sales_l` | Σ Elec Vol sold per pump on this tank |
| `theoretical_closing_l` | opening + deliveries − elec_vol_sales |
| `actual_closing_l` | Shift Close dip |
| `variance_l` | theoretical − actual |
| `variance_pct` | variance / (opening + deliveries) × 100 |
| `classification` | Normal / Elevated / Critical / Gain |
| `variance_kes` | variance_l × WAC |

---

#### Forecourt Transaction (PTS-2 Staging)

Every pump sale from PTS-2 lands here before becoming a POS Invoice.

- `pts_transaction_number` — Data (dedup key, unique per company)
- `company`, `shift`, `pump`, `fuel_grade`
- `posting_datetime`, `quantity_litres`, `unit_price`, `total_amount`
- `payment_mode` — Select: Cash / Fleet Card / MPesa / VISA
- `rfid_tag` — Data
- `status` — Select: Draft / Invoiced / Error

---

#### Drive-Off Record

Fuel dispensed but not paid.

- `shift`, `pump`, `fuel_product`
- `quantity_litres`, `unit_price`
- `total_kes` — Computed: qty × price
- `vehicle_description`, `vehicle_reg`
- `police_reference` — Required if total_kes ≥ 500
- `authorised_by` — Link → Employee (manager-level)

On submit: DR Drive-Off Losses / CR Fuel Sales — Account

---

#### PTS2 Device Registry

- `device_id` — Data (24-char hardware ID)
- `company` — Link → Company
- `location_description` — Data
- `is_active` — Check
- `last_seen` — Datetime (updated on every push)

---

#### Forecourt Site Preferences (Singleton per company)

All configurable thresholds per station.

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `wetstock_normal_pct` | 0.30 | Normal wetstock tolerance |
| `wetstock_elevated_pct` | 0.50 | Elevated threshold |
| `check_b_warn_pct` | 0.30 | Meter Check B warning |
| `check_b_fail_pct` | 0.50 | Meter Check B fail |
| `check_b_tamper_pct` | 1.00 | Auto-lock pump threshold |
| `check_a_warn_kes` | 5.00 | Cash meter discrepancy warning |
| `check_a_fail_kes` | 20.00 | Cash meter discrepancy fail |
| `cash_normal_kes` | 50 | Cashier variance normal |
| `cash_elevated_kes` | 200 | Cashier variance elevated |
| `till_pickup_threshold_kes` | 30,000 | Auto-trigger cash pickup |
| `delivery_settle_minutes` | 10 | Wait after delivery before after-dip |
| `auto_open_next_shift` | Yes | Auto-create next shift on close |
| `send_daily_summary` | Yes | Email shift report daily |

---

## B.4 Meter Validation Engine

### Check A — Electronic Volume vs Electronic Cash (per pump)

```python
expected_cash = elec_vol_sold × shift_rate
discrepancy   = abs(elec_cash_sold − expected_cash)

if   discrepancy ≤ 5.00:   status = "Pass"
elif discrepancy ≤ 20.00:  status = "Warning"
else:                       status = "Fail"
```

### Check B — Electronic Volume vs Manual Mechanical (per pump)

```python
divergence_pct = abs(elec_vol − man_vol) / elec_vol × 100

if   divergence_pct ≤ 0.30: status = "Pass"
elif divergence_pct ≤ 0.50: status = "Warning"
elif divergence_pct ≤ 1.00: status = "Fail"
else:                        status = "Critical" → auto-lock pump
```

### Applying to Shell Maanzoni Dec 2024 Data

| Pump | Elec L | Man L | Diff % | Check B |
|------|--------|-------|--------|---------|
| P1-T1 | 52.257 | 52.00 | 0.49% | **Warning** |
| P2-T1 | 89.936 | 90.00 | 0.07% | Pass |
| P5-T1 | 66.553 | 66.00 | 0.83% | **Fail** |
| L1-T3 | 1,230.992 | 1,230.00 | 0.08% | Pass |
| L6-T3 | 730.625 | 730.00 | 0.09% | Pass |

P5-T1 (V-Power) at 0.83% divergence is a Fail — schedule calibration.

---

## B.5 Wetstock Reconciliation Formula

```
Theoretical Closing = Opening Dip + Deliveries − RTT Volumes − Σ Elec Vol Sold (per tank)
Variance            = Theoretical − Actual Closing Dip

RTT Volumes = Σ rtt_volume_l on Meter Reading WHERE reading_position='Shift Open'
              AND meter_type='Electronic Volume' AND pump.tank = this tank
              (Return to Tank: nozzle test volumes dispensed at shift start)

Classification:
  Normal:   |variance| ≤ 0.30% of (Opening + Deliveries)
  Elevated: 0.30% < |variance| ≤ 0.50%
  Critical: |variance| > 0.50% (loss) — blocks GL posting without FMS Manager override
  Gain:     variance > 0.30% (unexpected gain — investigate; may be delivery measurement error)
```

---

## B.6 GL Journal at Shift Close

The GL Journal posts only **variances** at shift close. Revenue and COGS are already posted in real time when each POS Invoice is submitted.

```
Journal Entry — Shift Close — SHIFT-SML-2026-017

# Revenue and COGS are NOT here — already posted by each POS Invoice on_submit.

# Cash variance per cashier (from 17-05-2026 data):
DR  Cash Short / Over - SML    1,100.70    (Swedi Abuti — short)
CR  Cash Short / Over - SML      116.50    (Peter Mbeve — over)
CR  Cash Short / Over - SML        0.77    (Joseph Matale — over)

# Safe drop (cash physically moved from till to safe):
DR  Safe — Main - SML         129,295.00   (Abdirahman AHM deposit)
CR  Till — Active - SML       129,295.00

# Wetstock variance (only if |variance_l| ≥ 1.0 L):
DR  Wetstock Variance — PMS - SML    [loss_l × WAC]
CR  Fuel Inventory — PMS Unleaded    [loss_l × WAC]

# PDQ card variance (Phase 5 — when PDQ terminals installed):
DR  Card Payment Variance - SML      [settlement_total − POS PDQ total, if < 0]
CR  PDQ Clearing - SML               [same amount]
```

Total DR = Total CR enforced before posting (`|DR − CR| ≤ KES 0.05`).
Any imbalance is a programming error — `frappe.throw()`, do not post.

---

## B.7 User Roles and Permissions

| Role | Company scope | Key permissions |
|------|---------------|-----------------|
| HQ Manager | All companies | Read all; write Item Price, Site Prefs, Pump Config |
| HQ Auditor | All companies | Read-only all |
| Site Manager | Own company | Full FMS access; approve variances; post GL |
| Site Supervisor | Own company | Open/close shifts; authorize cash events; run reconciliation |
| Site Cashier | Own company | POS Invoice; own Cashier Session; Cash Events (create) |
| Pump Attendant | Own company | Meter Readings; Dip Readings |

User Permission on Company field cascades to all FMS DocTypes. Every FMS DocType has a `company` field.

---

## B.8 Print Format — Meter Movements Report

The print format must exactly replicate the legacy report structure:

```
SHELL MAANZONI SERVICE STATION
METER MOVEMENTS BY PRODUCT
SHIFT DATE: [date]    SHIFT NO: [n]    USER/OPERATOR: [name]

PUMP  MAN MTR    ELEC MTR     MAN   ELEC  DIFF  SHORT  CASH METER      MTR SOLD  CASH  EXP    EXP SALE  CASH
      OPEN CLOSE OPEN  CLOSE  LTRS  LTRS  LTRS  (EXC)  OPEN    CLOSE   AMT       LTRS  PRICE  AMT       AMOUNT

V-POWER (Tank T1)
P1-T1  [...]
...
SUB TOTAL — V-POWER   [totals row]

UNLEADED EXTRA (Tank T2)
U1-T2  [...]
...
SUB TOTAL — UNLEADED EXTRA   [totals row]

DIESEL EXTRA (Tank T3)
L1-T3  [...]
...
SUB TOTAL — DIESEL EXTRA   [totals row]

GRAND TOTAL   [overall totals]
```

---

# PART C — IMPLEMENTATION PLAN

## Phase Overview

| Phase | Name | Duration | Deliverable |
|-------|------|----------|-------------|
| 0 | Foundation | 1 week | ERPNext installed, company configured, accounts/items/warehouses |
| 1 | Master Data | 1 week | All pumps, employees, site prefs, PDQ Terminal, Fleet Card; manual shift skeleton |
| 2 | Meter Entry | 1 week | Three-type meter reading form; Check A/B/E validation; Meter Movements Script Report |
| 3 | Reconciliation | 2 weeks | Cashier sessions, cash formula (with PDQ column), wetstock (with RTT), GL journal (variances only) |
| 4 | Shift Auto + Alerts | 1 week | Auto-open next shift with Carry Forward readings; Forecourt Alerts; stale shift watchdog |
| 5 | PDQ Settlement | 1 week | PDQ Settlement doctype; card terminal reconciliation; PDQ variance GL entry |
| 6 | Reporting | 1 week | All Script Reports; HQ dashboard; Station Workspace |
| 7 | Compliance | 1 week | VAT, eTIMS (async), EPRA price cap validation, bulk price update |
| 7B | Migration + Go-Live | 2 weeks | Parallel run; opening balances; go-live on manual entry |
| 8 | PTS-2 Integration | 2–3 weeks | HTTP push receiver; WebSocket commands; auto-invoice at shift close (OPTIONAL) |

**Total:** ~12–13 weeks for a solo developer using Claude Code CLI.

> **Design principle:** The system goes live at Phase 7B on fully manual entry with no
> external controller dependency. PTS-2 (Phase 8) is added after the manual system is
> proven stable. Every phase except Phase 8 produces a working system independently.

---

## Phase 0 — ERPNext Foundation

### Deliverable
Working ERPNext v15 site with Shell Maanzoni configured.

### Milestones

**0.1 — Install ERPNext**

```bash
# On Ubuntu 22.04 server (4GB RAM min)
sudo apt update && sudo apt install -y git python3-pip redis-server mariadb-server \
  nodejs npm wkhtmltopdf libssl-dev
pip install frappe-bench
bench init frappe-bench --frappe-branch version-15
cd frappe-bench
bench get-app erpnext --branch version-15
bench new-site maanzoni.local --install-app erpnext
bench --site maanzoni.local migrate
bench start
```

**0.2 — Company Hierarchy**

```
Shell Kenya Limited          (parent company, HQ reporting)
└── Shell Maanzoni (Anika Global Limited)   (operating company)
```

Configure on Shell Maanzoni:
- Abbreviation: SML
- Default Currency: KES
- Country: Kenya
- Fiscal Year: Jan–Dec

**0.3 — Chart of Accounts**

Income accounts under Sales:
- `Fuel Sales — V-Power - SML`
- `Fuel Sales — Unleaded Extra - SML`
- `Fuel Sales — Diesel Extra - SML`

COGS accounts:
- `COGS — Fuel V-Power - SML`
- `COGS — Fuel Unleaded Extra - SML`
- `COGS — Fuel Diesel Extra - SML`
- `Wetstock Variance — Petrol - SML`
- `Wetstock Variance — Diesel - SML`
- `Cash Short / Over - SML`
- `Drive-Off Losses - SML`

Asset accounts:
- `Fuel Inventory — V-Power - SML`
- `Fuel Inventory — Unleaded Extra - SML`
- `Fuel Inventory — Diesel Extra - SML`
- `MPesa Clearing - SML`
- `Card Payment Clearing - SML`
- `Fleet Card Clearing - SML`
- `Safe — Main - SML`
- `Till — Active - SML`

**0.4 — Fuel Items**

Three items, each as a separate ERPNext Item:

| Item Code | Item Name | UOM | Selling Rate (KES/L) | Valuation |
|-----------|-----------|-----|---------------------|-----------|
| FUEL-VP | V-Power | Litre | 187.90 | Moving Average |
| FUEL-UX | Unleaded Extra | Litre | 176.20 | Moving Average |
| FUEL-DX | Diesel Extra | Litre | 165.00 | Moving Average |

Custom fields on Item: `fms_is_fuel`, `fms_tank_code`

**0.5 — Tank Warehouses**

| Warehouse | Item | Tank Code |
|-----------|------|-----------|
| Tank 1 — V-Power | FUEL-VP | T1 |
| Tank 2 — Unleaded Extra | FUEL-UX | T2 |
| Tank 3 — Diesel Extra | FUEL-DX | T3 |

**0.6 — Roles**

Create via Role Manager: HQ Manager, HQ Auditor, Site Manager, Site Supervisor, Site Cashier, Pump Attendant.

**0.7 — Employees**

Create Employee records for all station staff:
- Swedi Abuti (cashier), Peter Mbeve (cashier), Joseph Matale (cashier)
- Joel Musembi (cashier), James Kitiapi, Shadrack Kimulu
- ABDI MUSA (operator/supervisor)
- All pump attendants

Add custom field on Employee: `fms_till_gl_account`, `fms_rfid_tag_id`, `fms_is_cashier`, `fms_is_supervisor`

### Claude Code Prompts for Phase 0

```
Prompt 0-A: Create a Frappe app named 'fms' for Shell Maanzoni forecourt 
management. Set up hooks.py with all doc_events for Shift, Meter Reading, 
Tank Dip Reading, Cash Event, Fuel Delivery Dip, Fuel Price History, 
POS Invoice, Sales Invoice, and Drive-Off Record. Include scheduler events 
for daily summary and PTS device watchdog. Set up the fixtures array for 
Custom Field on POS Invoice, Sales Invoice, Purchase Receipt, Warehouse, Item.
```

```
Prompt 0-B: Create fms/fixtures/custom_field.json defining all custom fields 
for the FMS app: 
- POS Invoice: fms_shift (Link→Shift), fms_pump (Link→Pump), 
  fms_pump_attendant (Link→Employee, required), fms_etims_number
- Sales Invoice: same plus fms_fleet_card_ref, fms_vehicle_number
- Purchase Receipt: fms_delivery section with truck_reg, docket_number, 
  docket_volume, received_qty, delivery_variance, linked_shift
- Warehouse: fms_is_fuel_tank (Check), fms_tank_code, fms_capacity_litres, 
  fms_fuel_product, fms_pts2_tank_number, fms_reorder_level_ltrs
- Employee: fms_till_gl_account, fms_rfid_tag_id, fms_is_cashier, fms_is_supervisor
- Item: fms_is_fuel (Check), fms_tank_code
```

---

## Phase 1 — Pump Master Data and Shift Skeleton

### Deliverable
All 24 pumps in the system; Shift DocType with state machine working; manual dip reading captured; site preferences configured.

### Milestones

**1.1 — Pump DocType**

```
Pump Master — Shell Maanzoni pumps:

V-Power (T1):  P1-T1 through P8-T1
Unleaded (T2): U1-T2 through U8-T2
Diesel (T3):   L1-T3 through L8-T3
```

**1.2 — Forecourt Site Preferences**

One record for "Shell Maanzoni (Anika Global Limited)". Configure all thresholds.

**1.3 — Shift DocType with State Machine**

```python
ALLOWED_TRANSITIONS = {
    "Draft":             ["Open"],
    "Open":              ["Readings Captured", "Disputed"],
    "Readings Captured": ["Closing", "Disputed"],
    "Closing":           ["Closed", "Disputed"],
    "Closed":            [],
    "Disputed":          ["Closing"],
}
```

**1.4 — Tank Calibration Charts**

Enter EPRA-certified strapping tables for all three tanks. (Until physical calibration data is available, use placeholder data for development.)

**1.5 — Tank Dip Reading**

Manual dip entry form with auto-derive from calibration chart.

### Claude Code Prompts for Phase 1

```
Prompt 1-A: Create fms/doctype/pump/pump.json — the Pump master DocType with 
fields: pump_code (Data, unique), pump_prefix (Select: P/U/L), tank (Link→Warehouse), 
fuel_product (Link→Item), pts2_pump_number (Int), island_number (Int), 
is_active (Check), pts2_device (Link→PTS2 Device), company (Link→Company).
Add child table Nozzle with fields nozzle_number and is_active.
Also create pump.py with validate() that enforces: pump_code matches regex 
^[PUL][0-9]+-T[123]$, pump_prefix matches the tank (P→T1, U→T2, L→T3).
```

```
Prompt 1-B: Create fms/doctype/shift/shift.json and shift.py.
Fields: company, station, shift_date, shift_label (Select: Day/Evening/Night), 
shift_number (Int), status (Select: Draft/Open/Readings Captured/Closing/Closed/Disputed),
opened_at, closed_at, cashier (Link→Employee), supervisor (Link→Employee),
float_amount (Currency), rate_vp, rate_ux, rate_dx (Currency — EPRA rates locked at open),
meter_validation_ok (Check), gl_journal (Link→Journal Entry), reconciliation_notes.
In shift.py: implement ALLOWED_TRANSITIONS state machine in before_save(), 
validate() with cashier≠supervisor check and conflict check (no two open shifts 
at same station), _assert_all_opening_readings_present() for Readings Captured transition.
```

```
Prompt 1-C: Create fms/doctype/tank_dip_reading/tank_dip_reading.py.
On validate(): if reading_source == "Manual Dipstick" and dip_height_mm is set 
and calibration_chart is set, call derive_volume_from_dip() and set volume_observed_l.
If water_level_mm > 20: create a Forecourt Alert with alert_type "Water High".
Validate volume_observed_l ≤ tank capacity. For Delivery After readings: 
check that reading_datetime ≥ delivery_end + 10 minutes.
```

---

## Phase 2 — Meter Reading and Validation

### Deliverable
Three-type meter entry form; Check A and Check B engine; Meter Movements Report print format that exactly matches the legacy PDF.

### Milestones

**2.1 — Meter Reading DocType**

Entry form with `meter_type` select. Validation: closing ≥ opening; immutability on submitted docs; Amendment flow.

**2.2 — Meter Validation Engine**

`fms/utils/meter.py` — implements Check A and Check B as described in B.4. Called when supervisor runs "Run Meter Validation" on the Shift.

**2.3 — Meter Movements Script Report**

The Meter Movements Report is implemented as a Frappe **Script Report** (`fms/report/meter_movements/`), not as a separate DocType. It queries `Meter Reading` directly for the given shift/date range. This avoids a redundant storage layer and keeps data in one place.

Report structure mirrors the legacy PDF exactly: PUMP | MAN MTR OPEN | MAN MTR CLOSE | ELEC MTR OPEN | ELEC MTR CLOSE | MAN LTRS | ELEC LTRS | DIFF LTRS | SHORT(EXCESS) | MTR SOLD AMT | EXP PRICE | EXP SALE AMT. Grouped by product (V-Power / Unleaded Extra / Diesel Extra) with subtotals and grand total. All SQL must include `WHERE company = %(company)s`.

### Claude Code Prompts for Phase 2

```
Prompt 2-A: Create fms/doctype/meter_reading/meter_reading.py.
Fields: shift, pump, nozzle_number (Int), meter_type (Select: Electronic Volume/
Electronic Cash/Manual Mechanical), reading_position (Select: Shift Open/Shift Close/
Spot Check/Amendment), totalizer_value (Float, 6 decimal places), unit (auto-set),
observed_at, read_by (Link→Employee), witnessed_by (Link→Employee), 
superseded_by (Link→Meter Reading), amendment_reason.
In validate(): 
  - Set unit = "KES" if meter_type == "Electronic Cash" else "Litres"
  - totalizer_value > 0 required
  - For Shift Close: find the matching Shift Open reading; if closing < opening, throw
  - For submitted docs: if totalizer_value changed, throw (create Amendment instead)
  - Amendment reading requires amendment_reason
```

```
Prompt 2-B: Create fms/utils/meter.py with:
1. check_a(elec_vol_sold, elec_cash_sold, shift_rate) → dict with expected_cash, 
   discrepancy, status (Pass/Warning/Fail) using thresholds from Site Preferences
2. check_b(elec_vol_sold, man_vol_sold) → dict with divergence_pct, status 
   (Pass/Warning/Fail/Critical) using thresholds from Site Preferences
3. run_meter_validation(shift_name) → creates one Meter Validation Result doc 
   per active pump-nozzle, calls _lock_pump() for Critical, returns overall_status
4. _lock_pump(pump_name) — sets is_active=0 on Pump, publishes realtime event
Apply Shell Maanzoni Dec 2024 data as validation test data in docstring.
```

```
Prompt 2-C: Create the Meter Movements Script Report at fms/report/meter_movements/.
Files needed: meter_movements.json (report definition) + meter_movements.py (data function).

The report queries Meter Reading directly (NO Meter Reading Summary doctype).
Filters: company (required), shift (Link→Shift), date_from / date_to.
All queries must include WHERE company = %(company)s to respect User Permissions.

Columns matching legacy PDF:
PUMP | MAN MTR OPEN | MAN MTR CLOSE | ELEC MTR OPEN | ELEC MTR CLOSE |
MAN LTRS | ELEC LTRS | DIFF LTRS | SHORT(EXCESS) | CASH MTR OPEN |
CASH MTR CLOSE | MTR SOLD AMT | EXP PRICE | EXP SALE AMT

Sections: V-POWER (pump.tank = Tank 1) / UNLEADED EXTRA (Tank 2) / DIESEL EXTRA (Tank 3)
Subtotal row per section in bold. Grand Total row.
SHORT(EXCESS) column: blank when diff ≥ 0; show absolute diff when diff < 0.
Litres: 2 decimal places. KES: 2 decimal places with thousands separator.

Verify against Dec 2024 data:
  V-Power subtotal: Man=257.00, Elec=257.62, Diff=−0.62
  Grand Total: Man=5,032.00, Cash=KES 854,474.87
```

---

## Phase 3 — Cash Reconciliation and Wetstock

### Deliverable
Complete shift close workflow: per-cashier cash reconciliation matching the paper Cash Rec Sheet; wetstock formula; GL journal.

### Milestones

**3.1 — Cashier Session and Cash Event**

Entry forms with dual-control validation (counted_by ≠ cashier; authorised_by ≠ session cashier).

**3.2 — Cash Reconciliation Engine**

`fms/utils/cash.py` — computes expected cash per cashier, over/under, validates against the formula verified with 17-05-2026 data.

**3.3 — Wetstock Engine**

`fms/utils/wetstock.py` — complete formula: theoretical = opening + deliveries − sales; variance classification.

**3.4 — Shift Reconciliation DocType**

Three child tables (cashier summary, tank wetstock, nozzle MVR). Computed when supervisor clicks "Compute Reconciliation."

**3.5 — GL Journal Engine**

`fms/utils/gl.py` — posts only variance entries at shift close; balance-checks before posting.

### Claude Code Prompts for Phase 3

```
Prompt 3-A: Create fms/utils/cash.py with:
1. compute_cashier_expected_cash(cashier_session_name) → reads from:
   - POS Invoices linked to the shift for this cashier (Sales total)
   - Sales Invoices linked to the shift for this cashier (Invoices = credit, non-cash)
   - POS payments (MPesa/card) for this cashier (non-cash deductions)
   - Cash Events for this cashier's session (Receipts in, Payments out)
   Returns: {sales, invoices, pos_payments, visa_card, total_credits, 
             receipts, payments_out, expected_cash}
2. Verify against Shell Maanzoni 17-05-2026 data:
   Swedi Abuti: 219118.70 − 200868.00 + (−1000.00) − 2950.00 = 14300.70
   Peter Mbeve: 149724.50 − 136131.00 + 0 − 410.00 = 13183.50
   Joseph Matale: 252498.23 − 250849.00 + 0 − 0 = 1649.23
Add these as unit test assertions in the docstring.
```

```
Prompt 3-B: Create fms/utils/wetstock.py with compute_tank_wetstock(shift_name, tank).
Query: 
- Opening dip (Shift Open, submitted)
- Deliveries (Accepted Fuel Delivery Dips for this tank and shift)
- Elec Vol sales (sum of Closing Elec Vol − Opening Elec Vol for all pumps on this tank)
- Closing dip (Shift Close, submitted)
Compute: theoretical, variance_l, variance_pct, classification.
Classification: Normal (≤0.30%), Elevated (0.30–0.50%), Critical (>0.50% loss), 
Gain (>0.30% gain). WAC from ERPNext Bin table.
Return full dict for child table population.
```

```
Prompt 3-C: Create fms/utils/gl.py with post_shift_journal_entry(shift_reconciliation_name).
Rules:
- Only posts variances (NOT revenue or COGS — those were posted with POS Invoices)
- Cash variance per cashier: DR or CR Cash Short/Over account per cashier row
- Wetstock variance per tank: DR Wetstock Variance / CR Fuel Inventory (or reverse for gains)
- Safe drop: DR Safe—Main / CR Till—Active for each Pickup/SafeDrop Cash Event
- Balance check: |total_DR − total_CR| ≤ 0.05 before posting, else throw
- Set gl_journal on Shift Reconciliation and Shift docs after posting
- Use get_account() helper from fms/utils/accounts.py for all account lookups
```

---

## Phase 4 — Shift Auto-Open + Alerts

### Deliverable
Automatic next-shift creation on close with Carry Forward readings; Forecourt Alert system; stale shift watchdog.

### Milestones

**4.1 — Shift Auto-Open (`fms/api/shift_auto.py`)**

On shift close: if `auto_open_next_shift = True` in Forecourt Site Preferences, immediately create next shift. Carry closing meter readings forward as `reading_position = "Carry Forward"` (not "Shift Open"). `read_by = closing supervisor` (not Administrator). Carry closing dips forward with `reading_source = "Carry Forward"`.

**4.2 — Forecourt Alert DocType**

Created by: Check B Critical (pump locked), water level > 20mm, stale shift, eTIMS failure, PTS Buffer retry exhausted, delivery variance > 0.5%.

**4.3 — Scheduler Tasks (`fms/tasks.py`)**

`check_stale_shifts()` — hourly: alert if Open shift exceeds `stale_shift_hours`.  
`send_daily_summary()` — 6 AM: email summary to Forecourt Site Report Recipients.

### Claude Code Prompts for Phase 4

```
Prompt 4-A: Implement fms/api/shift_auto.py:
  open_next_shift(closed_shift_name):
    1. Check auto_open_next_shift pref
    2. Compute next shift_date / shift_number based on shifts_per_day
    3. Create new Shift in Draft; set previous_shift = closed_shift_name
    4. _carry_forward_meter_readings(): copy Shift Close readings as 
       reading_position="Carry Forward", read_by=closing supervisor (NOT Administrator)
    5. _carry_forward_dip_readings(): copy Shift Close dips as 
       reading_type="Shift Open", reading_source="Carry Forward",
       recorded_by=closing supervisor (NOT Administrator)
  get_current_shift(company): returns open shift dict or None
```

```
Prompt 4-B: Implement fms/tasks.py scheduled functions.
Register in hooks.py:
  scheduler_events = {
    "cron": {
      "0 * * * *":  ["fms.tasks.check_stale_shifts"],
      "0 6 * * *":  ["fms.tasks.send_daily_summary"],
    }
  }
check_stale_shifts(): for each company, find Open shifts where
  TIMESTAMPDIFF(HOUR, opening_at, NOW()) > prefs.stale_shift_hours → create Forecourt Alert
```

---

## Phase 5 — PDQ Settlement

### Deliverable
PDQ Terminal and PDQ Settlement doctypes; card terminal reconciliation in Shift Reconciliation; card variance GL entry.

### Milestones

**5.1 — PDQ Terminal and PDQ Settlement DocTypes**

PDQ Terminal: terminal_id, merchant_id, terminal_model, island, company, is_active.  
PDQ Settlement: terminal, settlement_date, total_amount, transaction_count, shift, status, expected_card_total (computed), card_variance_kes (computed).

**5.2 — PDQ Reconciliation in Shift Reconciliation**

Add `pdq_settlement_recon` child table to Shift Reconciliation. `compute_reconciliation()` auto-links PDQ Settlements for the shift and computes `expected_card_total = Σ POS Invoice payments WHERE mode_of_payment = 'PDQ'` for each terminal.

**5.3 — PDQ Variance in GL Journal**

`post_shift_variances()` in `fms/utils/gl.py` posts DR Card Payment Variance / CR PDQ Clearing when `|card_variance_kes| > pdq_variance_warn_kes`.

**5.4 — API Endpoint (optional automated push)**

`POST /api/method/fms.api.pdq.receive_settlement` — accepts settlement JSON. Idempotent: `merchant_ref + terminal` unique. Returns existing record on duplicate.

### Claude Code Prompts for Phase 5

```
Prompt 5-A: Create PDQ Terminal and PDQ Settlement doctypes with naming series
PDQT-{company_abbr}-{##} and PDQS-{YYYY}-{MM}-{DD}-{#####}.
PDQ Settlement: on save, compute expected_card_total from POS Invoices with
mode_of_payment='PDQ' for the linked shift. Set card_variance_kes = total_amount - expected.
```

```
Prompt 5-B: Create fms/api/pdq.py with receive_settlement() endpoint.
@frappe.whitelist(allow_guest=False)
Idempotency: check merchant_ref + terminal uniqueness before creating.
On duplicate: return {"success": true, "pdq_settlement": existing_name, "duplicate": true}
```

---

## Phase 6 — Deliveries, Drive-Offs, Alerts

### Deliverable
Fuel Delivery Dip workflow with variance check; Drive-Off record with GL; Forecourt Alert DocType.

### Milestones

**5.1 — Fuel Delivery Dip Workflow**

Entry form → links Dip Before and Dip After → computes variance → submits to Purchase Receipt if ≤ 0.5%.

**5.2 — Drive-Off Record**

Entry form with manager auth requirement; on submit posts DR Drive-Off Losses / CR Fuel Sales.

**5.3 — Forecourt Alert DocType**

Receives pump and tank alerts from PTS-2 and meter validation engine.

### Claude Code Prompts for Phase 5

```
Prompt 5-A: Create fms/doctype/fuel_delivery_dip/fuel_delivery_dip.py.
Fields: shift, company, tank, fuel_product, delivery_start, delivery_end,
truck_reg, driver_name, docket_number, docket_volume_l, dip_before (Link→Tank Dip Reading),
dip_after (Link→Tank Dip Reading), sales_during_offload_l, dip_measured_l (computed),
delivery_variance_l (computed), delivery_variance_pct (computed), status, purchase_receipt.
In validate():
  dip_measured_l = dip_after.volume - dip_before.volume + sales_during_offload_l
  delivery_variance_l = docket_volume_l - dip_measured_l
  delivery_variance_pct = delivery_variance_l / docket_volume_l * 100
  If abs(delivery_variance_pct) > 0.5 and status == "Accepted":
    throw("Variance >0.5% — must be Disputed before acceptance")
  If delivery_variance_pct > 0.5 and status == "Pending": set status = "Disputed"
```

---

## Phase 6 — Deliveries, Drive-Offs, Additional Reporting

> *(Previously Phase 5 — renumbered to accommodate PDQ Settlement phase)*

### Deliverable
Fuel Delivery Dip workflow with variance check; Drive-Off record with GL; reporting suite; HQ dashboard.

---

## Phase 7 — Reporting Suite

### Deliverable
All six custom Script Reports. HQ Dashboard. Per-station and HQ Workspaces.

### Reports to Build

**Report 1 — Daily Shift Summary**
One row per shift. Columns: Date, Station, Shift, Cashier, VP Litres, VP Revenue, UX Litres, UX Revenue, DX Litres, DX Revenue, Total Revenue, Cash Variance, Wetstock Var L, Status.
Source: POS Invoices + Shift Reconciliation.

**Report 2 — Meter Movements Report (Script Report)**
Reproduces the legacy PDF as an interactive ERPNext report with filters for date range and station. Downloadable as Excel.

**Report 3 — Per-Cashier Cash Reconciliation**
Filter by Shift. Exactly replicates the paper Cash Rec Sheet with TOTAL row.

**Report 4 — Wetstock Variance Trend**
Filter by date range and station. Shows variance %, classification, KES value.

**Report 5 — Cashier Performance Summary**
Filter by date range and station. Shows shift count, total cash handled, net variance, short count, over count, largest single variance per cashier.

### Claude Code Prompts for Phase 6

```
Prompt 6-A: Create fms/report/meter_movements/meter_movements.py — a Frappe 
Script Report that replicates the legacy Meter Movements Report.
Filters: from_date, to_date, company, shift (optional).
Columns: Pump | Man Open | Man Close | Elec Open | Elec Close | Man Ltrs | 
Elec Ltrs | Diff Ltrs | Short(Excess) | Cash Meter Open | Cash Meter Close | 
Mtr Sold Amt | Cash Ltrs | Exp Price | Exp Sale Amt | Cash Amount
Data source: Meter Reading docs for the selected shift(s), grouped by product.
Include subtotal rows (is_group=True) for each product section and a grand total row.
Short(Excess) = diff if diff < 0 else None.
Format numbers: litres 2dp, KES 2dp, thousands separator.
```

```
Prompt 6-B: Create the HQ Forecourt Dashboard using Frappe Dashboard DocType.
Python source functions (in fms/dashboard_chart/):
1. get_fuel_stock_by_site() — from tabBin, filter fms_is_fuel_tank=1 warehouses
2. get_open_shifts_status() — open/closing/disputed shifts with hours_open
3. get_today_revenue_by_site() — from POS Invoice items, grouped by company+item_code
4. get_wetstock_alerts() — elevated/critical from last 48h Shift Reconciliation 
5. get_meter_check_fails() — recent Check B fails/warnings from Meter Validation Result
Return format: list of dicts with consistent keys for chart rendering.
```

---

## Phase 7A — Kenya Compliance

### Deliverable
VAT 16% on all fuel POS Invoices; eTIMS integration; EPRA price cap validation.

### Milestones

**7.1 — VAT**

Tax template `Kenya Fuel VAT 16%`. Apply to POS Profile and Sales Invoice template. VAT Payable account.

**7.2 — eTIMS**

On POS Invoice and Sales Invoice `on_submit`: POST to KRA eTIMS API. Store returned eTIMS number in `fms_etims_number`. Log failures without blocking. Flag for manual retry.

**7.3 — EPRA Price Validation**

On Fuel Price History validate: if new_rate > epra_max and not approved_by: throw.

### Claude Code Prompts for Phase 7

```
Prompt 7-A: Create fms/api/etims.py with:
submit_invoice_to_etims(invoice_name, invoice_type="POS") — called on_submit.
Builds eTIMS payload from the invoice (invoice number, date, items, VAT, totals, 
customer PIN if available). POSTs to KRA sandbox/production endpoint.
On success: sets fms_etims_number on the invoice doc.
On failure: creates a Frappe Error Log, adds comment to the invoice, 
sets a Forecourt Alert "eTIMS submission failed — retry required".
Never throw or block invoice submission — eTIMS is async.
```

---

## Phase 7B — Migration and Go-Live

### Deliverable
Parallel run completed; opening stock entered; all staff trained; legacy system set read-only.

### Migration Steps

**8.1 — Opening Stock Entry**

At cutover date, take physical dips of all three tanks. Create `Stock Entry → Material Receipt` for each tank with the dip volume at the current WAC from the most recent supplier invoice.

```
Stock Entry — Opening Balance — Cutover Date
  Tank 1 — V-Power:       [dip_litres] L at WAC [cost]/L
  Tank 2 — Unleaded Extra: [dip_litres] L at WAC [cost]/L
  Tank 3 — Diesel Extra:  [dip_litres] L at WAC [cost]/L
```

**8.2 — Totalizer Seeding**

Seed the Meter Readings for the first FMS shift as "Amendment" type readings capturing the legacy system's closing totalizer values. These become the opening readings for Shift 1 in FMS.

**8.3 — Parallel Run (2 weeks minimum)**

Run both systems simultaneously:
- All meter readings entered in BOTH legacy system AND FMS
- Compare daily: does FMS Meter Movements Report match legacy PDF for same day?
- Discrepancies investigated before cutting over

**8.4 — Go-Live**

Day 1 legacy close → totalizers recorded → Day 1 FMS open using those totalizers → legacy set to read-only archive.

### Claude Code Prompts for Phase 8

```
Prompt 8-A: Create fms/api/migration.py with:
seed_opening_totalizers(shift_name, pump_totalizers: list[dict]) — for migration.
pump_totalizers format: [{"pump": "P1-T1", "elec_vol": 39380.000, 
"elec_cash": 5699970.04, "man_mech": 39380.0}]
For each pump: create three Meter Reading docs (one per type) with 
reading_position="Shift Open", notes="Migration: Opening totalizer from legacy system".
Submit all readings. Validate: if all three types for all active pumps are present,
transition shift to "Readings Captured".
Include a dry_run=True option that validates without creating docs.
```

---

# PART D — REFERENCE MATERIAL

## D.1 Shell Maanzoni Pump Map

| Pump Code | Tank | Product | EPRA Rate (Dec 2024) | Island |
|-----------|------|---------|---------------------|--------|
| P1-T1 | T1 | V-Power | KES 187.90/L | 1 |
| P2-T1 | T1 | V-Power | KES 187.90/L | 1 |
| P3-T1 | T1 | V-Power | KES 187.90/L | 2 |
| P4-T1 | T1 | V-Power | KES 187.90/L | 2 |
| P5-T1 | T1 | V-Power | KES 187.90/L | 3 |
| P6-T1 | T1 | V-Power | KES 187.90/L | 3 |
| P7-T1 | T1 | V-Power | KES 187.90/L | 4 |
| P8-T1 | T1 | V-Power | KES 187.90/L | 4 |
| U1-T2 | T2 | Unleaded Extra | KES 176.20/L | 1 |
| U2-T2 | T2 | Unleaded Extra | KES 176.20/L | 1 |
| U3-T2 | T2 | Unleaded Extra | KES 176.20/L | 2 |
| U4-T2 | T2 | Unleaded Extra | KES 176.20/L | 2 |
| U5-T2 | T2 | Unleaded Extra | KES 176.20/L | 3 |
| U6-T2 | T2 | Unleaded Extra | KES 176.20/L | 3 |
| U7-T2 | T2 | Unleaded Extra | KES 176.20/L | 4 |
| U8-T2 | T2 | Unleaded Extra | KES 176.20/L | 4 |
| L1-T3 | T3 | Diesel Extra | KES 165.00/L | 1 |
| L2-T3 | T3 | Diesel Extra | KES 165.00/L | 1 |
| L3-T3 | T3 | Diesel Extra | KES 165.00/L | 2 |
| L4-T3 | T3 | Diesel Extra | KES 165.00/L | 2 |
| L5-T3 | T3 | Diesel Extra | KES 165.00/L | 3 |
| L6-T3 | T3 | Diesel Extra | KES 165.00/L | 3 |
| L7-T3 | T3 | Diesel Extra | KES 165.00/L | 4 |
| L8-T3 | T3 | Diesel Extra | KES 165.00/L | 4 |

Note: Pumps P3, P4, P7, U3, U4, L3, L4 had zero sales in the Dec 2024 shift — they may be inactive or on standby. The FMS must handle zero-sales pumps gracefully (no divide-by-zero in Check B).

---

## D.2 Business Calculation Reference

### D.2.1 Per-Pump Calculations

```
Manual Litres    = Manual MTR Close  − Manual MTR Open
Elec Litres      = Elec MTR Close    − Elec MTR Open
Diff Litres      = Manual Litres     − Elec Litres
Short (Excess)   = Diff Litres if Diff Litres < 0 else NULL
Mtr Sold Amt     = Cash MTR Close    − Cash MTR Open
Exp Sale Amt     = Manual Litres     × Exp Price
Cash Variance    = Cash Amount       − Exp Sale Amt
```

### D.2.2 Check A (Elec Cash vs Elec Vol)

```
Expected Cash (from vol) = Elec Litres × Shift Rate
Check A Discrepancy      = |Mtr Sold Amt − Expected Cash|
```

### D.2.3 Check B (Elec Vol vs Man Mech)

```
Check B Divergence % = |Elec Litres − Manual Litres| / Elec Litres × 100
```

Handle zero: if Elec Litres = 0 and Manual Litres = 0: divergence = 0, status = Pass.
If Elec Litres = 0 and Manual Litres > 0: status = Critical (no electronic count for manual fuel).

### D.2.4 Subtotal and Grand Total

```
Subtotal Manual Ltrs = Σ Manual Litres for all pumps in product group
Subtotal Elec Ltrs   = Σ Elec Litres for all pumps in product group
Subtotal Diff        = Σ Diff Litres
Subtotal Short       = Σ Short (Excess) — sum of negatives only
Subtotal Cash Amt    = Σ Cash Amount
Grand Total          = Σ across all three product groups
```

### D.2.5 December 2024 Verification Values

V-Power subtotal: Man=257.00, Elec=257.62, Diff=−0.62, Cash=48,521.10
Unleaded Extra subtotal: Man=1,598.00, Elec=1,597.67, Diff=+0.33, Cash=281,521.82
Diesel Extra subtotal: Man=3,177.00, Elec=3,178.37, Diff=−1.37, Cash=524,431.05 (PDF shows 524,431.05 but KES column differs slightly — rounding at row level)
Grand Total: Man=5,032.00, Elec=5,033.65, Cash=854,474.87

---

## D.3 UAT Test Cases

Before go-live, all of the following must pass:

### D.3.1 Meter Reading Tests

```
[ ] Shift blocks to "Readings Captured" only after all three types entered for all active pumps
[ ] Closing < Opening throws validation error
[ ] Submitted totalizer_value is immutable — throws if modified
[ ] Amendment reading accepted with amendment_reason; creates audit trail
[ ] Zero-sales pump (P3-T1): no divide-by-zero in Check B; status = Pass
```

### D.3.2 Check A and Check B Tests

Using Dec 2024 data:
```
[ ] P1-T1: Diff=−0.257, Divergence%=0.49% → Check B = Warning ✓
[ ] P2-T1: Diff=+0.06, Divergence%=0.07% → Check B = Pass ✓
[ ] P5-T1: Diff=−0.55, Divergence%=0.83% → Check B = Fail ✓
[ ] P3-T1: 0 litres both meters → Check B = Pass, no error ✓
[ ] Pump at 1.5% divergence → Check B = Critical, pump auto-locked ✓
```

### D.3.3 Cash Reconciliation Tests

Using 17-05-2026 data:
```
[ ] Swedi Abuti:   expected = 219,118.70 − 200,868.00 − 1,000.00 − 2,950.00 = 14,300.70 ✓
[ ] Peter Mbeve:   expected = 149,724.50 − 136,131.00 − 0 − 410.00 = 13,183.50 ✓
[ ] Joseph Matale: expected = 252,498.23 − 250,849.00 − 0 − 0 = 1,649.23 ✓
```

### D.3.4 Wetstock Tests

```
[ ] Balanced shift: theoretical = actual → variance = 0, classification = Normal ✓
[ ] 0.35% loss: classification = Elevated ✓
[ ] 0.6% loss: classification = Critical, blocks GL posting without approval ✓
[ ] Delivery included: theoretical = opening + delivery − sales ✓
[ ] Delivery variance >0.5%: blocks GRN submission without approval ✓
```

### D.3.5 Meter Movements Report Tests

```
[ ] Report matches legacy PDF for same shift date
[ ] V-Power section subtotals correct
[ ] Short(Excess) column blank for positive Diff (P2-T1: +0.06 → blank) ✓
[ ] Short(Excess) filled for negative Diff (P1-T1: −0.26 → shows −0.26) ✓
[ ] Inactive pumps (P3, P4, P7) show zero across all columns, not NULL ✓
[ ] Grand Total row = sum of three subtotals ✓
```

### D.3.6 PTS-2 Integration Tests

```
[ ] Pump transaction appears within 30 seconds of dispense
[ ] Duplicate TransactionNumber: silently skipped, returns {"status": "ok"}
[ ] Invalid HMAC: returns 401
[ ] Price push: new price appears on pump display within 5 seconds
[ ] RFID sync: UpdateTagList sent when Employee record with rfid_tag saved
[ ] Offline 8 hours: reconnect replays all buffered transactions, no duplicates
```

### D.3.7 GL Journal Tests

```
[ ] DR = CR within KES 0.05 tolerance — any imbalance throws before posting
[ ] Revenue NOT re-posted (already on POS Invoices)
[ ] Cash Short/Over per cashier appears correctly
[ ] Wetstock variance only posted if |variance_l| ≥ 1.0 L
[ ] Safe drop: DR Safe / CR Till ✓
```

---

## D.4 Diagnostic SQL Queries

```sql
-- 1. Open shifts (should be max 1 per station)
SELECT name, status, cashier, opened_at,
       TIMESTAMPDIFF(HOUR, opened_at, NOW()) AS hours_open
FROM `tabShift`
WHERE status IN ('Open', 'Closing')
ORDER BY opened_at DESC;

-- 2. Missing closing meter readings for a shift
SELECT p.pump_code, pn.nozzle_number, mr.meter_type
FROM `tabPump` p
JOIN `tabNozzle` pn ON pn.parent = p.name AND pn.is_active = 1
CROSS JOIN (
    SELECT 'Electronic Volume' mt UNION SELECT 'Electronic Cash' UNION SELECT 'Manual Mechanical'
) types
LEFT JOIN `tabMeter Reading` mr
    ON mr.pump = p.name AND mr.nozzle_number = pn.nozzle_number
   AND mr.meter_type = types.mt
   AND mr.shift = 'SHIFT-2026-00001'
   AND mr.reading_position = 'Shift Close'
   AND mr.docstatus = 1
WHERE p.is_active = 1 AND mr.name IS NULL;

-- 3. Wetstock variance trend (last 30 days)
SELECT s.shift_date, s.company, tws.tank, tws.fuel_product,
    ROUND(tws.variance_l, 2) AS var_l,
    ROUND(tws.variance_pct, 4) AS var_pct,
    tws.classification,
    ROUND(tws.variance_kes, 2) AS var_kes
FROM `tabShift Reconciliation Tank Wetstock` tws
JOIN `tabShift Reconciliation` sr ON sr.name = tws.parent
JOIN `tabShift` s ON s.name = sr.shift
WHERE s.shift_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY s.shift_date DESC, tws.classification DESC;

-- 4. Per-cashier variance history
SELECT cashier,
    COUNT(*) AS shifts,
    ROUND(SUM(cash_over_under), 2) AS net_variance,
    SUM(CASE WHEN cash_over_under < 0 THEN 1 ELSE 0 END) AS short_count,
    ROUND(MAX(ABS(cash_over_under)), 2) AS max_single
FROM `tabShift Reconciliation Cashier Summary`
GROUP BY cashier ORDER BY ABS(SUM(cash_over_under)) DESC;

-- 5. PTS transactions missing from invoices (dispensed but not billed)
SELECT ft.pump, ft.posting_datetime, ft.quantity_litres, ft.total_amount
FROM `tabForecourt Transaction` ft
WHERE ft.status = 'Draft' AND ft.shift IN (
    SELECT name FROM `tabShift` WHERE status = 'Closed'
);

-- 6. Pump Check B history — recent fails
SELECT s.shift_date, mvr.pump, mvr.nozzle_number,
    ROUND(mvr.check_b_divergence_pct, 4) AS div_pct,
    mvr.check_b_status
FROM `tabMeter Validation Result` mvr
JOIN `tabShift` s ON s.name = mvr.shift
WHERE mvr.check_b_status != 'Pass'
ORDER BY s.shift_date DESC, mvr.check_b_divergence_pct DESC
LIMIT 50;
```

---

## D.5 Bench Commands Reference

```bash
# Development
bench new-app fms
bench --site maanzoni.local install-app fms
bench --site maanzoni.local migrate
pip install pyserial pymodbus websocket-client --break-system-packages
bench restart

# Testing
bench --site maanzoni.local run-tests --app fms --module fms.tests.test_meter
bench --site maanzoni.local run-tests --app fms --module fms.tests.test_wetstock
bench --site maanzoni.local run-tests --app fms --module fms.tests.test_cash

# Fixtures
bench --site maanzoni.local export-fixtures --app fms
bench --site maanzoni.local import-fixtures --app fms

# Maintenance
bench --site maanzoni.local clear-cache
bench --site maanzoni.local backup --with-files
bench --site maanzoni.local execute fms.tasks.watchdog_check_pts_devices

# Go-live migration
bench --site maanzoni.local execute fms.api.migration.seed_opening_totalizers
```

---

## D.6 PTS-2 Configuration Checklist (Pre-Deployment)

```
Hardware:
[ ] DIP-1 OFF (HTTPS mode — required for production)
[ ] DIP-2 OFF (Digest authentication)
[ ] CR2032 battery installed and voltage ≥ 3.0V
[ ] microSD Class 10 FAT32 formatted and inserted
[ ] 12V DC adapter rated ≥ 2A connected

Network:
[ ] Static IP assigned (or DHCP reservation by MAC)
[ ] Gateway matches router IP
[ ] DNS: 8.8.8.8 and 8.8.4.4
[ ] Can ping fms.yourdomain.co.ke from PTS-2 (use web UI Diagnostics)

Software:
[ ] Admin password changed from default "admin"
[ ] Dedicated user created for FMS receiver (Monitoring + Control permissions)
[ ] Secret key set (64 hex chars, generated with secrets.token_hex(32))

Upload settings (ALL required):
[ ] Save pump transactions to SD: Enabled
[ ] Save tank measurements to SD: Enabled
[ ] Save alerts to SD: Enabled
[ ] Remote server domain: fms.yourdomain.co.ke
[ ] Remote server port: 443
[ ] URI: /api/method/fms.api.pts2.receive
[ ] Upload period: 1 second

Pump setup:
[ ] All 24 pumps configured on correct ports
[ ] Decimal digits match dispenser display (volume 3dp, price 3dp)
[ ] Read pump totals automatically: Enabled (for totalizer theft detection)

Grade setup:
[ ] Grade 1: V-Power, price 187.90, TC coefficient 0.00110
[ ] Grade 2: Unleaded Extra, price 176.20, TC coefficient 0.00110
[ ] Grade 3: Diesel Extra, price 165.00, TC coefficient 0.00084

Nozzle setup:
[ ] Each nozzle linked to correct grade and tank

SD card logging:
[ ] PUMPTRN.CSV exists and row count increases after test transaction
[ ] SERVER.LOG shows green connectivity to FMS endpoint
```

---

## D.7 Variance Tolerance Quick Reference

| Metric | Normal (Auto-approve) | Elevated (Review) | Critical (Block) |
|--------|----------------------|-------------------|-----------------|
| Wetstock loss % | ≤ 0.30% | 0.30–0.50% | > 0.50% |
| Wetstock gain % | — | Any > 0.30% | — |
| Delivery variance % | ≤ 0.30% | 0.30–0.50% | > 0.50% |
| Cashier cash variance KES | ≤ 50 | 50–200 | > 200 |
| Meter Check A KES | ≤ 5 | 5–20 | > 20 |
| Meter Check B % | ≤ 0.30% | 0.30–0.50% | > 0.50%; > 1.0% = lock pump |

---

## D.8 Daily Operating Checklist (Laminate for Station)

**SHIFT OPENING — Incoming Cashier + Supervisor**

```
□  Previous shift confirmed Closed (or Disputed with written explanation)
□  Create Shift: date, label, EPRA rates locked, cashier, supervisor assigned
□  Cashier Session created; float issued → Cash Event: Float Issued (supervisor witnesses)
□  Opening dips — EVERY active tank:
     □  Tank 1 (V-Power)       □  Tank 2 (Unleaded)    □  Tank 3 (Diesel)
     □  Water level noted — alert supervisor if >20mm
□  Opening meter readings — EVERY active pump, ALL THREE TYPES:
     □  Manual Mechanical: read number wheels physically, write ALL digits
     □  Electronic Volume: read digital display litres, write ALL digits + decimal
     □  Electronic Cash: read digital display KES, write ALL digits
□  Transition shift → "Readings Captured" → "Open"
□  Brief all pump attendants: do not dispense until system shows Open
```

**DURING THE SHIFT**

```
□  All POS sales: correct payment type + named pump attendant (NEVER N/A or blank)
□  Fleet/credit sales → Sales Invoice (not POS) — feeds "Invoices" column in cash rec
□  Till > KES 30,000: Cash Event "Cash Pickup" + supervisor sign + envelope number
□  Fuel delivery: Dip Before → wait 15 min → Dip After → check variance → GRN
□  Drive-off: Drive-Off Record with manager authorisation, police ref if >KES 500
```

**SHIFT CLOSING — Cashier + Supervisor**

```
□  Closing meter readings — EVERY active pump, ALL THREE TYPES
□  Closing dips — every active tank
□  Each cashier physically counts till; enters actual_cash_close in Cashier Session
□  Enter non-cash totals per cashier: Invoices / POS (MPesa) / VISA
□  Shift status → Closing
□  Run Meter Validation → resolve any Check B Fail/Critical → re-run
□  Compute Reconciliation → review per-cashier summary → compare to paper sheet
□  Review per-tank wetstock
□  If all within tolerance: Approve → Post GL → Shift status → Closed
□  If Critical variance: Shift status → Disputed → investigate before GL
□  Brief incoming shift
```

---

## Phase 8 — PTS-2 Integration (Optional, Post Go-Live)

### Deliverable
Pump transactions from PTS-2 controller auto-creating Forecourt Transaction staging docs; batch-converted to POS Invoices at shift close; price push working; RFID fleet auth working.

> This phase is implemented AFTER the manual system (Phase 7B) is proven stable in production.
> Every workflow in Phases 0–7B continues to function without PTS-2. PTS-2 is an enhancement
> that automates data entry — it does not replace any accountability process.

### Milestones

**8.1 — PTS2 Device + Pump Configuration DocTypes**

`PTS2 Device`: device_id, hmac_secret (Password field), company, last_seen.  
`Pump Configuration`: pts_pump_id, fuel_grade_id → maps to ERPNext Pump + Item.

**8.2 — HTTP Push Receiver (`fms/api/pts2.py`)**

HMAC-SHA256 verification using `hmac.compare_digest` (constant-time). Dispatch by RecordType: PumpTransaction → Forecourt Transaction; TankMeasurement → Tank Dip Reading; Alert → Forecourt Alert. Idempotency: `pts_transaction_number + pts_device` unique constraint.

**8.3 — PTS Buffer DocType (replaces /tmp file)**

On database write failure during receive: save raw payload to `PTS Buffer` (status = Pending). `fms.tasks.retry_pts_buffer` runs every 30 min. Max 5 retries then Failed + Alert.

**8.4 — WebSocket Command Layer (`fms/api/pts2_commands.py`)**

SetGradePrices triggered on Item Price change when `fms_effective_shift = Current`.  
UpdateTagList triggered on Employee RFID update.  
AuthorizePump for fleet card RFID pre-auth flow.  
Nginx WebSocket proxy block required (not in default bench config).

**8.5 — Shift Close Invoicing (`fms/api/shift_close_invoicing.py`)**

`batch_create_invoices_from_pts(shift_name)` converts all Draft Forecourt Transactions for the shift into submitted POS Invoices. Triggered by "Convert FTs to Invoices" button on Shift form when status = Closing.

### Claude Code Prompts for Phase 8

```
Prompt 8-A: Create PTS2 Device and Pump Configuration doctypes.
Create fms/api/pts2.py with:
  @frappe.whitelist(allow_guest=True)
  def receive_transaction():
    1. Read raw body bytes and X-PTS-Signature header
    2. HMAC verify: hmac.compare_digest(
         hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest(),
         received_signature
       ) — throw 400 if fails
    3. device = frappe.get_doc("PTS2 Device", {"device_id": data["DeviceId"]})
    4. Dedup: if Forecourt Transaction exists for pts_transaction_number+device → return duplicate:true
    5. Look up Pump Configuration for pts_pump_id
    6. Find open Shift for device.company
    7. Create Forecourt Transaction (Draft) — never auto-submit
    8. Return {"success": true, "forecourt_transaction": ft.name, "duplicate": false}
    On exception: save to PTS Buffer (status=Pending), return {"success": true} to PTS-2
```

```
Prompt 8-B: Create fms/api/shift_close_invoicing.py with:
  batch_create_invoices_from_pts(shift_name):
    For each Forecourt Transaction (docstatus=0) for this shift:
      1. Create POS Invoice: fms_shift=shift, fms_pump=ft.pump,
         fms_nozzle_number=ft.nozzle_number, fms_pump_attendant=attendant_from_rfid(ft.rfid_tag_id),
         fms_forecourt_transaction=ft.name, item=ft.fuel_grade, qty=ft.volume_total_l,
         rate=ft.price_per_litre, payment=appropriate_mode
      2. Submit POS Invoice
      3. frappe.db.set_value Forecourt Transaction → docstatus=1, pos_invoice=inv.name
    Return count of invoices created.
```

---

## D.9 Known Limitations and Mitigations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Frappe 50–200ms HTTP latency | Prepay pump authorisation too slow | Use PTS-2 local OPT module for prepay; FMS handles post-pay only |
| Custom SQL reports bypass User Permissions | HQ query shows all sites | Add explicit `WHERE company IN (...)` to every FMS SQL report — no exceptions |
| WAC contamination on disputed delivery | Wrong fuel cost if GRN posted at docket volume | Always use dip-measured volume for GRN; Purchase Receipt.validate() enforces this |
| ERPNext upgrade breaks custom fields | Fixtures survive upgrades; hooks may break | Test `bench update` on staging before production; maintain fms app as separate git repo |
| WebSocket per-command latency | Price push delayed on mobile networks | Acceptable for once-per-shift price changes; persistent connection pool for high-volume sites |
| No N/A pump attendant allowed | Legacy system accepted blank attendant | Intentional breaking change — eliminates accountability gap. Train staff before Phase 7B |
| /tmp buffer lost on reboot (old design) | Replayed PTS-2 transactions lost | Resolved: use PTS Buffer doctype (Phase 8) — MariaDB is durable |
| Meter Reading Summary doctype (old design) | Redundant storage layer | Resolved: Meter Movements is a Script Report querying Meter Reading directly |

---

*End of FMS Implementation Roadmap v2.0.0*

**Document prepared for:** Shell Maanzoni Service Station (Anika Global Limited)  
**Based on:** Legacy Meter Movements PDF (26 Dec 2024), Excel Meter Movements Workbook (15 Jun 2026), ERPNext FMS Architecture v3.0.0, PTS-2 API Guide v2.0.0, FMS Production Spec v2.0  
**Design principle:** System goes live on manual entry (Phase 7B) before any external integration. PTS-2 (Phase 8) is additive, never required.  
**Ready for:** Claude Code CLI-assisted development — use Part C prompts directly in Claude Code sessions
