# ERPNext Forecourt Management System (FMS)
## Comprehensive Implementation Guide — Shell Maanzoni Service Station

**Version:** 3.0.0  
**Platform:** ERPNext v15 / Frappe Framework v15  
**Station Reference:** Shell Maanzoni Service Station (Anika Global Limited)  
**Network:** Shell Kenya Limited — Multi-Site  
**Currency:** KES  
**Last Updated:** May 2026

---

## Table of Contents

1. [Introduction & Business Context](#1-introduction--business-context)
2. [The Golden Rules](#2-the-golden-rules)
3. [The Three Meter Types — Core Concept](#3-the-three-meter-types--core-concept)
4. [Cross-Validation — How the Three Meters and the Dip Check Each Other](#4-cross-validation)
5. [Architecture Overview](#5-architecture-overview)
6. [ERPNext Foundation Setup](#6-erpnext-foundation-setup)
7. [Data Model — Complete Doctype Reference](#7-data-model--complete-doctype-reference)
8. [Custom Fields on Native ERPNext Doctypes](#8-custom-fields-on-native-erpnext-doctypes)
9. [Manual Station Workflows](#9-manual-station-workflows)
10. [PTS Controller Integration](#10-pts-controller-integration)
11. [Shift Lifecycle & Cash Reconciliation](#11-shift-lifecycle--cash-reconciliation)
12. [Fuel Delivery (GRN) Workflow](#12-fuel-delivery-grn-workflow)
13. [Wetstock Reconciliation](#13-wetstock-reconciliation)
14. [Fleet Cards & Credit Customers](#14-fleet-cards--credit-customers)
15. [Kenya Compliance](#15-kenya-compliance)
16. [Security & Data Isolation](#16-security--data-isolation)
17. [Offline Resilience & Error Handling](#17-offline-resilience--error-handling)
18. [Server Infrastructure & DevOps](#18-server-infrastructure--devops)
19. [Implementation Phases](#19-implementation-phases)
20. [Testing & Quality Assurance](#20-testing--quality-assurance)
21. [Known Limitations](#21-known-limitations)
22. [Appendix](#22-appendix)

---

## 1. Introduction & Business Context

### 1.1 What Problem Are We Actually Solving?

A petrol station appears simple — buy fuel, sell fuel. Three silent problems can destroy a station financially before management notices.

**Problem 1 — Cash Leakage.** On 17-05-2026 at Shell Maanzoni, cashier Swedi Abuti had expected cash of KES 14,300.70 but declared KES 13,200.00 — a KES 1,100.70 shortage on one shift. Across five cashiers that same shift the total over/under was (KES 983.43). Without a system that reconciles cash collected against fuel dispensed per cashier per shift, these shortfalls remain invisible in aggregate and are never traced to source.

**Problem 2 — Fuel Losses.** With 2,658.43 litres sold on the shift shown (KES 619,312.14 value: Unleaded Extra 955.99 L @ KES 204,785.65 + Diesel Extra 1,702.44 L @ KES 414,526.49), even a 0.3% wetstock loss is 8 litres — KES 1,900 per shift. Annualised: over KES 690,000 in unexplained stock shrinkage.

**Problem 3 — Delivery Fraud.** The supplier docket says 8,000 litres. The before/after dip says 7,796 litres arrived. Without both dip readings, you cannot dispute the docket and the KES 30,600 shortfall goes unrecovered.

### 1.2 The Legacy System: What It Does Well

The existing system already captures all three meter types per nozzle — the `Elect(Cash)`, `Elec(Ltrs)`, and `Man(Ltrs)` columns are visible in the live screen. It also produces a per-cashier Daily Shift Cash Reconciliation Sheet with Invoices, POS, VISA, Receipts, Payments, Expected Cash, Actual Cash, and Over/Under columns per cashier row — exactly the level of accountability needed.

The ERPNext FMS will:
- Replicate the three-meter capture and the per-cashier reconciliation sheet exactly
- Add the wetstock reconciliation (theoretical vs actual dip) that the legacy system handles manually
- Add automated GL journal entries that the legacy system never produces
- Add PTS controller integration for partially automated data capture
- Add EPRA and KRA eTIMS compliance

### 1.3 Real Data Reference — Shell Maanzoni

All examples in this guide use actual Shell Maanzoni data.

**Station configuration:**

| Element | Detail |
|---|---|
| Products | Unleaded Extra (UX), V-Power (VP), Diesel Extra (DX) |
| EPRA Prices (May 2026) | UX: KES 214.20/L, VP: KES 229.00/L, DX: KES 242.90/L |
| Tanks | T1 (V-Power), T2 (Unleaded), T3 (Diesel) |
| Islands | 4 islands; pumps named UX/DX/VP with island suffix |
| Typical shift | ~2,658 litres, ~KES 619,000 revenue |
| Cashiers per shift | 4–5 cashiers plus supervisor/manager row |

**Observed meter variances from live legacy screen (Elec Vol vs Man Mech):**

| Pump | Elec Ltrs | Man Ltrs | Var (Ltrs) | Var % |
|---|---|---|---|---|
| U5 (Island 3 UX) | 80.99 | 81.00 | −0.00 | 0.01% |
| U6 (Island 3 UX) | 320.56 | 321.00 | −0.43 | 0.13% |
| L5 (Island 3 DX) | 50.24 | 50.00 | +0.23 | **0.46%** → approaching warning |
| L6 (Island 3 DX) | 212.04 | 212.00 | +0.04 | 0.02% |
| U7 (Island 4 UX) | 80.53 | 80.00 | +0.52 | 0.65% → **Warning** |
| U8 (Island 4 UX) | 349.65 | 349.00 | +0.65 | 0.19% |
| L7 (Island 4 DX) | 304.11 | 304.00 | +0.11 | 0.04% |
| L8 (Island 4 DX) | 214.49 | 215.00 | −0.51 | 0.24% |

> Note: U7 at 0.65% exceeds the 0.50% Check B fail threshold. In the ERPNext system this would be flagged as **Fail** and require an Amendment reading or pump inspection before the shift can close.

**Cash reconciliation data — 17-05-2026:**

| Cashier | Sales | Invoices | POS | VISA | PDQ | Total Credits | Recpts | Pymts | Expected Cash | Actual Cash | Over/(Under) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SWEDI ABUTI | 219,118.70 | 175,168.00 | 5,000.00 | 20,700.00 | 0.00 | 200,868.00 | (1,000.00) | 2,950.00 | 14,300.70 | 13,200.00 | **(1,100.70)** |
| JOEL MUSEMBI | 250.00 | — | — | — | — | — | 0.00 | — | 250.00 | 250.00 | — |
| ABDIRAHMAN AHM | — | — | — | — | — | — | 0.00 | 129,295.00 | (129,295.00) | (129,295.00) | — |
| PETER MBEVE | 149,724.50 | 124,021.00 | — | 12,110.00 | 0.00 | 136,131.00 | 0.00 | 410.00 | 13,183.50 | 13,300.00 | **116.50** |
| JOSEPH MATALE | 252,498.23 | 238,349.00 | 11,500.00 | 1,000.00 | 0.00 | 250,849.00 | 0.00 | — | 1,649.23 | 1,650.00 | **0.77** |
| **TOTAL** | **621,591.43** | **537,538.00** | **16,500.00** | **33,810.00** | **0.00** | **587,848.00** | **(1,000.00)** | **132,465.00** | **(99,911.57)** | **(100,895.00)** | **(983.43)** |

> **PDQ column** = card terminal payments (Ingenico/Verifone). Separate from VISA (manual card entry). PDQ = 0 at Shell Maanzoni until PDQ terminals are installed (Phase 5).

> ABDIRAHMAN AHM row represents the manager/supervisor float pool — large Pymts out = safe deposits or float redistribution. The negative Expected Cash in this row is by design (supervisor holds no till; they receive cash from cashiers and deposit to safe).

### 1.4 Terminology

| Term | Definition |
|---|---|
| **ATG** | Automatic Tank Gauge |
| **DX** | Diesel Extra — AGO grade at Shell Maanzoni |
| **Elec Cash** | Electronic Cash meter — cumulative KES totalizer on pump display |
| **Elec Vol** | Electronic Volume meter — cumulative litre totalizer on pump display |
| **EPRA** | Energy & Petroleum Regulatory Authority (Kenya) |
| **eTIMS** | Electronic Tax Invoice Management System (KRA) |
| **FMS** | Forecourt Management System — the custom Frappe app |
| **GRN** | Goods Received Note — ERPNext Purchase Receipt |
| **Island** | Physical forecourt position grouping pump units |
| **jsonPTS** | Technotrade PTS-2 proprietary JSON protocol |
| **Man Mech** | Manual Mechanical — physical number wheels on pump body |
| **PMS / UX / VP** | Premium Motor Spirit; UX = Unleaded Extra, VP = V-Power |
| **PTS-2** | Technotrade LLC forecourt controller |
| **RTT** | Return to Tank — volume dispensed back to tank during testing |
| **Shift** | A defined operating period; one accountability contract per cashier |
| **Totalizer** | Non-resettable cumulative counter in each pump |
| **UX** | Unleaded Extra — standard petrol grade at Shell Maanzoni |
| **VP** | V-Power — premium petrol grade at Shell Maanzoni |
| **WAC** | Weighted Average Cost — ERPNext inventory valuation method |
| **Wetstock** | Fuel stored in underground tanks |

---

## 2. The Golden Rules

Every doctype, every field, every validation exists to enforce one of these rules.

**Rule 1 — The Shift Is the Unit of Everything.** A shift is a bounded accountability contract. Every litre dispensed, every shilling collected, every delivery, every dip — all belongs to a shift.

**Rule 2 — Three Meters, One Truth.** Every modern dispensing pump has three independent measurement systems. All three must be read at open and close. Divergence between them is either a data entry error or evidence of tampering.

**Rule 3 — Dip Readings Are the Tank's Bank Statement.** A dip reading measures physical fuel independently of pump meters. It catches meter drift, unrecorded sales, theft, and leaks.

**Rule 4 — Cash and Fuel Reconcile Separately.** Cash: did each cashier collect the right amount? Wetstock: did the right volume leave the tanks? Computed independently; never merged.

**Rule 5 — No Opening Reading, No Sales.** Sales cannot begin before all three opening meter readings are captured per nozzle.

**Rule 6 — Deliveries Need Before and After Dips.** Never accept a delivery on docket volume alone.

**Rule 7 — Dual Control on All Cash Movements.** Float, pickup, safe drop — two people, two user accounts, every time.

**Rule 8 — Each Cashier Reconciles Independently.** The cash formula runs per Cashier Session, matching the current paper reconciliation sheet row by row.

---

## 3. The Three Meter Types — Core Concept

This is the foundation of all wetstock integrity and fraud detection. The legacy system already captures all three types. The ERPNext system replicates this exactly.

### 3.1 Physical Layout

```
┌────────────────────────────────────────────────────────┐
│                    DISPENSING PUMP                      │
│                                                         │
│  ┌──────────────────┐   ┌────────────────────────┐     │
│  │  DIGITAL DISPLAY  │   │  MECHANICAL DRUMS       │     │
│  │  Vol: 171,275,183 │   │  (Physical Number Wheels│     │
│  │  Cash: 29,387,277 │   │   — no power needed)    │     │
│  └──────────────────┘   └────────────────────────┘     │
│   Electronic Vol + Cash    Manual Mechanical             │
└────────────────────────────────────────────────────────┘
```

### 3.2 Type 1 — Electronic Volume (Elec Vol)

Cumulative digital counter: total litres dispensed since installation. The primary legal measurement.

- Counts forward only; never resets; sealed by Weights & Measures
- 3 decimal places: e.g. 171,275,183.070 (actual UX8 totalizer at Shell Maanzoni)
- Primary figure used in all wetstock and sales calculations

`Elec Vol Sold = Closing Elec Vol − Opening Elec Vol`

### 3.3 Type 2 — Electronic Cash (Elec Cash)

Cumulative KES value of fuel dispensed — mathematically linked to Elec Vol via the programmed EPRA price.

`Elec Cash Sold = Closing Elec Cash − Opening Elec Cash`

**Cross-check (same-rate shift):**
```
Expected Cash = Elec Vol Sold × EPRA Rate
Discrepancy = |Elec Cash Sold − Expected Cash|

Shell Maanzoni 17-05-2026 example:
  U7 Island 4: 80.53 L × 214.20 = KES 17,249.63 expected
               Legacy shows KES 17,248.46 → discrepancy KES 1.17 → Pass ✓
  U8 Island 4: 349.65 L × 214.20 = KES 74,895.03 expected
               Legacy shows KES 74,895.24 → discrepancy KES 0.21 → Pass ✓
```

Why store this if we can compute it? Because it is a **physically independent sensor inside the pump**. If someone miskeys the Elec Vol reading, the Cash meter immediately exposes the discrepancy.

### 3.4 Type 3 — Manual Mechanical (Man Mech)

Physical odometer-style counter — rotating drums driven by the flow mechanism. Completely independent of electronics; requires no power; cannot be reset without a KEBS physical key.

Less precise (0.1 L vs 0.001 L for electronic), but immune to electronic tampering. Last line of defence when tampering is suspected.

`Mech Vol Sold = Closing Man Mech − Opening Man Mech`  
Must be within 0.5% of Elec Vol Sold. Above 1.0%: lock pump, notify KEBS.

### 3.5 Summary Table

| Attribute | Elec Vol | Elec Cash | Man Mech |
|---|---|---|---|
| Display | Digital screen | Digital screen | Physical number wheels |
| Unit | Litres | KES | Litres |
| Precision | 0.001 L | KES 0.01 | 0.1 L |
| Power required | Yes | Yes | No |
| Primary use | Volume sold | Cash cross-check | Tampering detection |

---

## 4. Cross-Validation

### 4.1 The Four-Way Check

At shift close, four independent data sources must agree about how much fuel was sold:

```
                   ┌────────────────────┐
                   │   DIP READING (L)  │  ← Physical reality in tank
                   └─────────┬──────────┘
                             │ must agree with
             ┌───────────────┼───────────────┐
   ┌──────────▼──┐  ┌─────────▼────┐  ┌──────▼──────────┐
   │ Elec Vol    │  │ Elec Cash    │  │ Man Mech        │
   │ (L)         │  │ ÷ Rate = (L) │  │ (L)             │
   └─────────────┘  └──────────────┘  └─────────────────┘
         └────────────────┴────────────────────┘
                  All must agree within tolerance
```

### 4.2 Check A — Volume vs Cash (per nozzle)

```python
discrepancy = abs(elec_cash_sold - (elec_vol_sold * shift_rate))
# Pass: ≤ KES 5    Warning: KES 5–20    Fail: > KES 20
```

### 4.3 Check B — Volume vs Mechanical (per nozzle)

```python
divergence_pct = abs(elec_vol_sold - mech_vol_sold) / elec_vol_sold * 100
# Pass: ≤ 0.30%   Warning: 0.30–0.50%   Fail: 0.50–1.00%   Critical > 1.00% → lock pump
```

**Applying this to the live Shell Maanzoni data:**

| Pump | Elec | Mech | Divergence | Status |
|---|---|---|---|---|
| U7 | 80.53 | 80.00 | 0.65% | **Fail** — requires Amendment or inspection |
| L5 | 50.24 | 50.00 | 0.48% | **Warning** — schedule calibration |
| U8 | 349.65 | 349.00 | 0.19% | Pass ✓ |
| L8 | 214.49 | 215.00 | 0.24% | Pass ✓ |

### 4.4 Check D — Tank Wetstock

```
Theoretical Closing = Opening Dip + Deliveries − RTT Volumes − Tank Elec Vol Sold
Wetstock Variance   = Theoretical − Actual Closing Dip

RTT Volumes = Σ rtt_volume_l on Meter Reading (reading_position = Shift Open,
              meter_type = Electronic Volume) for pumps feeding this tank.
              RTT = Return to Tank — nozzle test volumes dispensed back to tank
              at shift start to purge air. If not subtracted, formula overstates sales.
```

Classification:
| Range | Status |
|---|---|
| loss ≤ 0.30% | Normal |
| loss 0.30–0.50% | Elevated |
| loss > 0.50% | Critical — blocks GL posting without FMS Manager override |
| gain > 0.30% | Gain — investigate (possible delivery measurement error) |

### 4.5 Check E — Elec Cash vs POS Invoices (anti-fraud, per nozzle)

```
elec_cash_sold    = Closing Elec Cash − Opening Elec Cash (physical pump totalizer)
pos_invoice_total = Σ POS Invoice grand_total WHERE fms_shift=shift AND fms_pump=pump
                                                AND fms_nozzle_number=nozzle AND docstatus=1
check_e_variance  = |elec_cash_sold − pos_invoice_total|
```

| Variance | Status | Meaning |
|---|---|---|
| ≤ KES 10 | Pass | Normal rounding |
| KES 10–50 | Warning | Review with attendant |
| > KES 50 | Fail | Fuel dispensed without invoicing — investigate |

Check E is computed in `fms/utils/meter.py:run_meter_validation()` and stored in
`Meter Validation Result` alongside Check A and Check B. It cannot be bypassed.

---

## 5. Architecture Overview

### 5.1 Design Principles

1. One source of truth per concept — shift date on Shift; not repeated on children.
2. Three meter types, one Meter Reading doctype — `meter_type` is a field, not separate doctypes.
3. Per-cashier accountability — cash formula runs per Cashier Session, not per shift.
4. Extend native doctypes, never replace — FMS adds fields and hooks to GRN, POS Invoice, Stock Entry.
5. Company field on every FMS document — User Permission cascades automatically.
6. Frappe inside bench — PTS integration lives inside the Frappe app.

### 5.2 Architecture

```
┌──────────────── Shell Kenya HQ ─────────────────────┐
│     ERPNext Web — full cross-site visibility          │
└──────────────────────┬──────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │     Frappe Bench Server     │
         │  ERPNext Core + fms app     │
         └─────────────┬──────────────┘
                       │
         ┌─────────────┼──────────────┐
  ┌──────▼──────┐ ┌────▼──────┐ ┌────▼──────────┐
  │ PTS-2 Site  │ │Generic PTS│ │ Manual Site   │
  │ (jsonPTS)   │ │ (RS-485)  │ │ (no ATG/PTS)  │
  └─────────────┘ └───────────┘ └───────────────┘
```

### 5.3 Technology Stack

| Layer | Technology |
|---|---|
| ERP Platform | ERPNext v15 / Frappe Framework v15 |
| Language | Python 3.11+ |
| Database | MariaDB 10.6+ |
| Background Jobs | Redis + Frappe RQ |
| Serial / Modbus | pySerial 3.5+, pymodbus 3.x |
| PTS-2 Protocol | jsonPTS over HTTPS + WebSocket (RFC 6455) |

---

## 6. ERPNext Foundation Setup

### 6.1 Company Hierarchy

```
Shell Kenya Limited                (Parent)
├── Shell Maanzoni (Anika Global)  (Sub-company)
├── Shell Mombasa Road
└── Shell Westlands
```

### 6.2 Chart of Accounts

**Income (parent: Sales)**

| Account | Purpose |
|---|---|
| Fuel Sales — PMS Unleaded (UX) | Unleaded Extra revenue |
| Fuel Sales — PMS V-Power (VP) | V-Power revenue (separate — different EPRA price) |
| Fuel Sales — AGO Diesel (DX) | Diesel Extra revenue |
| Fuel Sales — DPK | Kerosene revenue |

**COGS**

| Account | Purpose |
|---|---|
| COGS — Fuel PMS Unleaded | Cost of UX sold |
| COGS — Fuel PMS V-Power | Cost of VP sold |
| COGS — Fuel AGO Diesel | Cost of DX sold |
| Wetstock Variance — PMS | Petrol losses |
| Wetstock Variance — AGO | Diesel losses |
| Cash Short / Over | Cashier variances (per-cashier posting) |
| Drive-Off Losses | Fuel dispensed, not paid |

**Assets**

| Account | Purpose |
|---|---|
| Fuel Inventory — PMS Unleaded | Physical UX in Tank 2 |
| Fuel Inventory — PMS V-Power | Physical VP in Tank 1 |
| Fuel Inventory — AGO Diesel | Physical DX in Tank 3 |
| MPesa Clearing | MPesa collections |
| Card Payment Clearing | VISA/card settlements |
| Fleet Card Clearing | Shell/fleet card |
| Safe — Main | Site safe balance |
| Till — Active | Active cashier till |

### 6.3 Fuel Grade Items

> **Critical:** Keep V-Power and Unleaded as **separate ERPNext Items** — different EPRA price schedule, different revenue accounts, potentially different WAC from different depot batches.

| Field | FUEL-PMS-UNL | FUEL-PMS-VP | FUEL-AGO |
|---|---|---|---|
| Item Code | `FUEL-PMS-UNL` | `FUEL-PMS-VP` | `FUEL-AGO` |
| UOM | Litre | Litre | Litre |
| Valuation | Moving Average (WAC) | Moving Average (WAC) | Moving Average (WAC) |
| Selling Rate | 214.20 | 229.00 | 242.90 |
| Default Warehouse | Tank 2 — Unleaded | Tank 1 — V-Power | Tank 3 — Diesel |

**Why WAC?** Each delivery arrives at a slightly different cost. WAC blends automatically. This is the only correct valuation for bulk liquid fuel.

**Custom fields on Item:** `fms_is_fuel_product` (Check), `fms_fuel_grade` (Select: UX/VP/DX/DPK).

### 6.4 Tank Warehouses — Shell Maanzoni

| Warehouse | Product | Nozzle type on pumps |
|---|---|---|
| Tank 1 — V-Power | FUEL-PMS-VP | VP / P nozzles |
| Tank 2 — Unleaded | FUEL-PMS-UNL | UX / U nozzles |
| Tank 3 — Diesel | FUEL-AGO | DX / L nozzles |

**Custom fields on Warehouse:** `fms_is_fuel_tank` (Check), `fms_capacity_litres` (Float), `fms_pts2_tank_number` (Int).

### 6.5 User Roles

| Role | Access | Permissions |
|---|---|---|
| Shell HQ Manager | All companies | Read/Write all, all sites |
| Shell HQ Auditor | All companies | Read-only, all sites |
| Site Manager | Own company | Full access; approve variances; post GL |
| Site Supervisor | Own company | Open/close shifts; authorise cash events |
| Site Cashier | Own company | Own sessions, POS, cash events |
| Pump Attendant | Own company | Meter readings, dip readings |

### 6.6 User Permissions

For every site-level user: one User Permission record, `Document Type: Company`, `Value: Shell Maanzoni`, `Apply to All Doctypes: ✅`.

HQ Manager and HQ Auditor have no User Permission records — unrestricted access is the absence of a restriction.

### 6.7 Forecourt Site Preferences (Single Doctype)

Per-station configuration so variance thresholds and account names are configurable without touching Python.

| Field | Default | Purpose |
|---|---|---|
| `company` | — | Name field — one record per company |
| `default_fuel_supplier` | — | Auto-populate on GRN |
| `wetstock_normal_pct` | 0.30 | Normal tolerance % |
| `wetstock_elevated_pct` | 0.50 | Elevated tolerance % |
| `cash_normal_kes` | 50 | Normal cash variance |
| `cash_elevated_kes` | 200 | Elevated cash variance |
| `meter_check_a_warn_kes` | 5 | Check A warning threshold |
| `meter_check_b_warn_pct` | 0.30 | Check B warning % |
| `meter_check_b_fail_pct` | 0.50 | Check B fail % |
| `meter_check_b_tamper_pct` | 1.00 | Lock pump threshold |
| `cash_pickup_threshold` | 30,000 | Till threshold for pickup |
| `min_settle_minutes` | 10 | Delivery dip settle time |
| `send_daily_summary` | ✅ | Email shift report daily |
| `report_recipients` | Table | Recipient list |
| *(account name overrides)* | — | Override default GL account names |


---

## 7. Data Model — Complete Doctype Reference

### 7.1 Entity Relationship Diagram

```
Island ──< Pump ──< Nozzle (child table)
                      │
                      │ draws from (nozzle.tank)
                      ▼
Tank (Warehouse) ←──── Tank Dip Reading
                              │
Shift (master) ───────────────┼──────────────────────────┐
    │                         │ (reconcile)               │
    ├── Meter Reading         ▼                           │
    │   (3 types ×       Tank Wetstock                   Forecourt
    │    open+close)                                      Transaction
    ├── Cash Event ──── Cashier Session ────────────────────(PTS)
    └── Fuel Delivery Dip → Purchase Receipt
              │
              └──────────────────► Shift Reconciliation
                                          │
                                    Per-Cashier Summaries
                                    Per-Tank Summaries
                                    Nozzle MVR Summaries
                                          │
                                    Journal Entry (GL)
```

### 7.2 App File Structure

```
frappe-bench/apps/fms/
├── fms/
│   ├── hooks.py
│   ├── tasks.py
│   ├── api/
│   │   ├── pts2.py                  ← PTS-2 HTTP receiver
│   │   ├── pts2_commands.py         ← WebSocket back-commands
│   │   ├── pts_generic.py           ← Generic RS-232/TCP receiver
│   │   └── offline_buffer.py
│   ├── utils/
│   │   ├── accounts.py              ← get_account() helper
│   │   ├── gl.py                    ← Journal Entry creation
│   │   ├── hr.py                    ← Employee validation
│   │   ├── meter.py                 ← Check A + Check B engine
│   │   ├── pos.py                   ← POS/Sales Invoice aggregation
│   │   ├── stock.py                 ← WAC and stock balance
│   │   └── wetstock.py              ← Wetstock formula engine
│   ├── doctype/
│   │   ├── shift/
│   │   ├── meter_reading/           ← Three types in one doctype
│   │   ├── meter_validation_result/ ← Check A + B per nozzle
│   │   ├── tank_dip_reading/
│   │   ├── tank_calibration_chart/
│   │   ├── forecourt_transaction/   ← PTS staging
│   │   ├── pump_configuration/      ← Hardware ID → ERPNext mapping
│   │   ├── cashier_session/
│   │   ├── cash_event/
│   │   ├── fuel_delivery_dip/
│   │   ├── shift_reconciliation/
│   │   ├── drive_off_record/
│   │   ├── fleet_card/
│   │   ├── forecourt_alert/
│   │   ├── pts2_device/
│   │   ├── fuel_price_history/
│   │   └── fms_settings/
│   ├── overrides/
│   │   ├── pos_invoice.py
│   │   └── sales_invoice.py
│   └── fixtures/
│       ├── custom_field.json
│       └── role_permission.json
└── requirements.txt
```

### 7.3 Shift (Master Record)

**Status state machine — new `Readings Captured` state gates the shift:**

```
Draft → Open → Readings Captured → Closing → Closed
                      ↓                ↓
                  Disputed ←──────────→ Closing  (manager re-opens)
```

`Readings Captured` means all three opening meter readings for all active nozzles have been submitted. Without it, a shift could move to Closing with incomplete readings.

| Field | Type | Notes |
|---|---|---|
| `name` | Auto | e.g. `SHIFT-2026-00001` |
| `company` | Link → Company | Drives User Permission filtering |
| `station` | Link → Branch | Physical station |
| `shift_date` | Date | Calendar date |
| `shift_label` | Select | Day / Evening / Night |
| `status` | Select | Draft / Open / Readings Captured / Closing / Closed / Disputed |
| `opened_at` | Datetime | |
| `closed_at` | Datetime | |
| `cashier` | Link → Employee | Primary cashier |
| `supervisor` | Link → Employee | Must differ from cashier |
| `float_amount` | Currency | Opening float |
| `rate_pms_unl` | Currency | EPRA UX rate locked at shift open |
| `rate_pms_vp` | Currency | EPRA VP rate locked at shift open |
| `rate_ago` | Currency | EPRA DX rate locked at shift open |
| `rate_dpk` | Currency | EPRA DPK rate locked at shift open |
| `meter_validation_ok` | Check | System-set after MVR passes |
| `gl_journal` | Link → Journal Entry | Set after GL posting |
| `reconciliation_notes` | Small Text | |

**Status transition enforcement:**

```python
# fms/doctype/shift/shift.py

ALLOWED_TRANSITIONS = {
    "Draft":             ["Open"],
    "Open":              ["Readings Captured", "Disputed"],
    "Readings Captured": ["Closing",           "Disputed"],
    "Closing":           ["Closed",            "Disputed"],
    "Closed":            [],
    "Disputed":          ["Closing"],
}

def before_save(doc, method):
    if doc.is_new():
        return
    old = frappe.db.get_value("Shift", doc.name, "status")
    if old == doc.status:
        return
    allowed = ALLOWED_TRANSITIONS.get(old, [])
    if doc.status not in allowed:
        frappe.throw(
            f"Cannot move shift from \'{old}\' to \'{doc.status}\'. "
            f"Allowed: {allowed or 'none — terminal state'}.",
            title="Invalid Status Transition"
        )
    if doc.status == "Readings Captured":
        _assert_all_opening_readings_present(doc)
    if doc.status == "Closing":
        _assert_closing_readings_present(doc)
    if doc.status == "Closed" and not doc.gl_journal:
        frappe.throw("GL Journal must be posted before shift can be Closed.")

def validate(doc, method):
    if doc.cashier and doc.supervisor and doc.cashier == doc.supervisor:
        frappe.throw("Cashier and Supervisor must be different employees.")
    if doc.status in ("Open", "Closing"):
        conflict = frappe.db.get_value("Shift", {
            "station": doc.station, "status": ("in", ["Open", "Closing"]),
            "name": ("!=", doc.name)}, "name")
        if conflict:
            frappe.throw(f"Shift {conflict} is already open at this station.")
```

### 7.4 Meter Reading (Three Types, One Doctype)

The `meter_type` field is the differentiator — not separate doctypes.

**Immutability:** Once submitted, `totalizer_value` cannot be changed. To correct: create an `Amendment` reading. The original remains as evidence.

| Field | Type | Notes |
|---|---|---|
| `name` | Auto | e.g. `MR-2026-0001` |
| `shift` | Link → Shift | |
| `pump` | Link → Pump | |
| `nozzle_number` | Int | Which nozzle on this pump |
| **`meter_type`** | **Select** | **Electronic Volume / Electronic Cash / Manual Mechanical** |
| `reading_position` | Select | **Shift Open / Shift Close / Carry Forward** |
| `observed_at` | Datetime | |
| `totalizer_value` | Float | Raw number from display or wheels |
| `unit` | Select | Auto-set: Litres (Elec Vol / Man Mech) or KES (Elec Cash) |
| `read_by` | Link → User | Who physically read the meter (or closing supervisor for Carry Forward) |
| `witnessed_by` | Link → Employee | Supervisor or second attendant |
| `rtt_volume_l` | Float | Return-to-Tank volume (litres); visible only for Elec Vol + Shift Open |
| `notes` | Text | Unusual observations (flickering display, etc.) |
| `amendment_of` | Link → Meter Reading | Set by ERPNext Amend flow (not a manual field) |

> **Carry Forward** readings are created programmatically by `shift_auto.py` when a shift
> closes and the next shift auto-opens. They are read-only once submitted. Supervisors can
> supersede a Carry Forward by submitting a fresh Shift Open reading after re-taping.
>
> **Correction flow:** Use ERPNext's native **Amend** button on a submitted Meter Reading.
> This creates an amendment copy (`amendment_of` links to original). Cancel the original,
> correct values in the amendment, then submit. The `amendment_of` link provides the audit trail.

```python
# fms/doctype/meter_reading/meter_reading.py
def validate(doc, method):
    doc.unit = "KES" if doc.meter_type == "Electronic Cash" else "Litres"
    if frappe.utils.flt(doc.totalizer_value) <= 0:
        frappe.throw("Totalizer value must be greater than zero.")
    if doc.reading_position == "Shift Close":
        # Look for Shift Open or Carry Forward opening reading
        opening = frappe.db.get_value("Meter Reading", {
            "shift": doc.shift, "pump": doc.pump,
            "nozzle_number": doc.nozzle_number, "meter_type": doc.meter_type,
            "reading_position": ["in", ["Shift Open", "Carry Forward"]], "docstatus": 1
        }, "totalizer_value")
        if opening is None:
            frappe.throw(f"No Shift Open reading for {doc.pump} / N{doc.nozzle_number} / {doc.meter_type}.")
        if frappe.utils.flt(doc.totalizer_value) < frappe.utils.flt(opening):
            frappe.throw(f"Closing ({doc.totalizer_value}) < opening ({opening}). Meters only count forward.")
    # Immutability on submitted records — use Amend button, not re-save
    if doc.docstatus == 1 and not doc.amendment_of:
        old_val = frappe.db.get_value("Meter Reading", doc.name, "totalizer_value")
        if old_val is not None and frappe.utils.flt(old_val) != frappe.utils.flt(doc.totalizer_value):
            frappe.throw(f"Submitted Meter Reading {doc.name} is immutable. Use the Amend button.")
```

### 7.5 Meter Validation Result

Computed output of Check A and Check B per nozzle. Auto-generated; never manually edited.

| Field | Type | Notes |
|---|---|---|
| `shift` | Link → Shift | |
| `pump` | Link → Pump | |
| `nozzle_number` | Int | |
| `fuel_product` | Link → Item | |
| `shift_rate` | Currency | EPRA rate locked on shift |
| `elec_vol_sold` | Float | Close − Open Elec Vol |
| `elec_cash_sold` | Currency | Close − Open Elec Cash |
| `mech_vol_sold` | Float | Close − Open Man Mech |
| `expected_cash` | Currency | Elec Vol × Shift Rate |
| `check_a_discrepancy` | Currency | `abs(Elec Cash − Expected Cash)` |
| `check_a_status` | Select | Pass / Warning / Fail |
| `check_b_divergence_pct` | Float | % divergence Elec vs Mech |
| `check_b_status` | Select | Pass / Warning / Fail / Critical |
| `overall_status` | Select | Pass / Warning / Fail / Critical |

**Meter validation Python engine:**

```python
# fms/utils/meter.py

CHECK_A_PASS_KES   = 5.0
CHECK_A_WARN_KES   = 20.0
CHECK_B_PASS_PCT   = 0.30
CHECK_B_WARN_PCT   = 0.50
CHECK_B_TAMPER_PCT = 1.00

def _validate_nozzle(nd, shift):
    rate = _get_rate(shift, nd.fuel_product)
    elec_vol  = frappe.utils.flt(nd.elec_vol_sold)
    elec_cash = frappe.utils.flt(nd.elec_cash_sold)
    mech_vol  = frappe.utils.flt(nd.mech_vol_sold)

    expected_cash  = elec_vol * rate
    check_a_disc   = abs(elec_cash - expected_cash)
    check_b_pct    = abs(elec_vol - mech_vol) / elec_vol * 100 if elec_vol else 0.0

    check_a = "Pass" if check_a_disc <= CHECK_A_PASS_KES else (
              "Warning" if check_a_disc <= CHECK_A_WARN_KES else "Fail")
    check_b = "Pass" if check_b_pct <= CHECK_B_PASS_PCT else (
              "Warning" if check_b_pct <= CHECK_B_WARN_PCT else (
              "Critical" if check_b_pct > CHECK_B_TAMPER_PCT else "Fail"))

    severity = {"Pass": 0, "Warning": 1, "Fail": 2, "Critical": 3}
    overall  = max(check_a, check_b, key=lambda s: severity[s])

    if check_b == "Critical":
        _lock_pump(nd.pump)

    return {
        "pump": nd.pump, "nozzle_number": nd.nozzle_number,
        "shift_rate": rate, "elec_vol_sold": elec_vol,
        "elec_cash_sold": elec_cash, "mech_vol_sold": mech_vol,
        "expected_cash": expected_cash,
        "check_a_discrepancy": check_a_disc, "check_a_status": check_a,
        "check_b_divergence_pct": round(check_b_pct, 4), "check_b_status": check_b,
        "overall_status": overall,
    }

def _lock_pump(pump_name):
    frappe.db.set_value("Pump", pump_name, "is_active", 0)
    frappe.logger().warning(f"Pump {pump_name} AUTO-LOCKED: Check B > 1% tamper threshold.")
    frappe.publish_realtime("pump_locked", {"pump": pump_name,
        "reason": "Meter Check B Critical — possible tampering"})
```

### 7.6 Tank Dip Reading

Single doctype for all scenarios. `reading_type` and `reading_source` differentiate them.

| Field | Type | Notes |
|---|---|---|
| `shift` | Link → Shift | |
| `company` | Link → Company | |
| `tank` | Link → Warehouse | |
| `reading_datetime` | Datetime | |
| `reading_type` | Select | Shift Open / Shift Close / Delivery Before / Delivery After / Spot |
| `reading_source` | Select | Manual Dipstick / ATG Electronic |
| `dip_height_mm` | Float | Raw dipstick measurement |
| `volume_observed_l` | Float | From ATG or derived via calibration chart |
| `water_level_mm` | Float | Alert threshold: 20mm |
| `calibration_chart` | Link → Tank Calibration Chart | Required for manual |
| `read_by` | Link → Employee | |

Validation: volume ≤ tank capacity; water > 20mm raises alert; Delivery After dip ≥ 10 minutes after delivery end.

### 7.7 Tank Calibration Chart

Converts dip height (mm) to volume (litres) via EPRA-certified strapping table.

```python
def derive_volume_from_dip(dip_height_mm, chart_name):
    chart = frappe.get_doc("Tank Calibration Chart", chart_name)
    rows = sorted(chart.chart_readings, key=lambda r: r.dip_height_mm)
    if dip_height_mm < rows[0].dip_height_mm or dip_height_mm > rows[-1].dip_height_mm:
        frappe.throw(f"Dip {dip_height_mm}mm is outside calibration chart range.")
    for i in range(len(rows) - 1):
        lo, hi = rows[i], rows[i + 1]
        if lo.dip_height_mm <= dip_height_mm <= hi.dip_height_mm:
            ratio = (dip_height_mm - lo.dip_height_mm) / (hi.dip_height_mm - lo.dip_height_mm)
            return lo.volume_ltrs + ratio * (hi.volume_ltrs - lo.volume_ltrs)
```

### 7.8 Cashier Session

One session per cashier per shift. Multiple sessions per shift are normal at Shell Maanzoni (4–5 per shift). Each cashier reconciles independently — matching the paper Cash Reconciliation Sheet.

| Field | Type | Notes |
|---|---|---|
| `shift` | Link → Shift | |
| `cashier` | Link → Employee | |
| `till_id` | Data | e.g. "TILL-01" |
| `is_primary` | Check | First cashier of the shift |
| `float_amount` | Currency | Opening float |
| `actual_cash_close` | Currency | Physically counted |
| `counted_by` | Link → Employee | The cashier |
| `verified_by` | Link → Employee | Supervisor (different person) |

### 7.9 Cash Event

Every cash movement: float, pickup, payout, safe drop.

| Field | Type | Notes |
|---|---|---|
| `shift` | Link → Shift | |
| `cashier_session` | Link → Cashier Session | Active session |
| `event_type` | Select | Float Issued / Cash Pickup / Payout / Safe Drop |
| `amount` | Currency | |
| `authorised_by` | Link → Employee | Must differ from session cashier |
| `occurred_at` | Datetime | |
| `reference` | Data | Envelope number — required for Pickup/Safe Drop |

### 7.10 Shift Reconciliation

Computed summary. Fix source data, then recompute.

**Child Table 1 — Per-Cashier Cash Summaries** (replicates paper Cash Reconciliation Sheet exactly):

| Field | Type | Notes |
|---|---|---|
| `cashier` | Link → Employee | |
| `cashier_session` | Link → Cashier Session | |
| `sales` | Currency | Total sales billed to this cashier |
| `invoices` | Currency | Credit invoices — non-cash, deducted |
| `pos_payments` | Currency | POS/mobile money — non-cash, deducted |
| `visa_card` | Currency | VISA/card — non-cash, deducted |
| `total_credits` | Currency | `invoices + pos_payments + visa_card` |
| `receipts` | Currency | Adjustments in (negative = out) |
| `payments_out` | Currency | Cash pickups and safe drops |
| `expected_cash` | Currency | `sales − total_credits + receipts − payments_out` |
| `actual_cash` | Currency | Physically counted |
| `cash_over_under` | Currency | `actual − expected` |

**Cash formula — verified against 17-05-2026 paper sheet:**
```
Swedi Abuti:   219,118.70 − 200,868.00 + (−1,000.00) − 2,950.00 = 14,300.70 ✓
Peter Mbeve:   149,724.50 − 136,131.00 + 0 − 410.00 = 13,183.50 ✓
Joseph Matale: 252,498.23 − 250,849.00 + 0 − 0 = 1,649.23 ✓
```

**Child Table 2 — Tank Wetstock Summaries:**

| Field | Type | Notes |
|---|---|---|
| `tank` | Link → Warehouse | |
| `fuel_product` | Link → Item | |
| `opening_stock_l` | Float | From Shift Open dip |
| `deliveries_l` | Float | From accepted Fuel Delivery Dips |
| `elec_vol_sales_l` | Float | Σ Elec Vol for all nozzles on this tank |
| `mech_vol_sales_l` | Float | Σ Man Mech (cross-check) |
| `theoretical_closing_l` | Float | Opening + Deliveries − Sales |
| `actual_closing_l` | Float | From Shift Close dip |
| `variance_l` | Float | Theoretical − Actual |
| `variance_pct` | Float | |
| `classification` | Select | Normal / Elevated / Critical / Gain |
| `variance_kes` | Currency | `variance_l × WAC` |

**Child Table 3 — Nozzle Meter Validation Summary:**

| Field | Type | Notes |
|---|---|---|
| `pump` | Link → Pump | |
| `nozzle` | Int | |
| `elec_vol_sold` | Float | |
| `elec_cash_sold` | Currency | |
| `mech_vol_sold` | Float | |
| `check_a_status` | Select | Pass / Warning / Fail |
| `check_b_status` | Select | Pass / Warning / Fail / Critical |

### 7.11 Other Key Doctypes

**Fuel Delivery Dip** — links Purchase Receipt to before/after dip readings; tracks truck reg, docket number, dip-measured vs docket variance; Accepted / Disputed status.

**Drive-Off Record** — fuel dispensed but not paid; auto-computes KES from volume × shift rate; requires manager authorisation; police reference required if ≥ KES 500; on submit posts `DR Drive-Off Losses / CR Fuel Sales`.

**Forecourt Transaction** — PTS staging record; every PTS pump sale lands here before becoming a POS/Sales Invoice at shift close; `pts_transaction_number` is the deduplication key.

**Fuel Price History** — tracks every EPRA price change; `approved_by` required if new price exceeds EPRA cap; triggers WebSocket push to PTS controllers on submit.

**PTS-2 Device Registry** — maps hardware `device_id` to ERPNext company; `last_seen` updated on every push.

**Pump Configuration** — maps `pts_pump_id` hardware to ERPNext Pump record with JSON fuel grade and tank mappings.

**Fleet Card** — card number, customer, grade restriction, credit limit, volume/amount limit per fill, RFID tag ID for PTS-2 authorisation.

---

## 8. Custom Fields on Native ERPNext Doctypes

All defined in `fms/fixtures/custom_field.json`, loaded via `bench migrate`.

### 8.1 POS Invoice — "FMS — Forecourt" Section

| Field | Type | Notes |
|---|---|---|
| `fms_shift` | Link → Shift | Auto-linked to open shift on submit |
| `fms_pump` | Link → Pump | |
| `fms_pump_attendant` | Link → Employee | **Required — no N/A or blank** |
| `fms_etims_invoice_number` | Data | KRA eTIMS confirmation |

### 8.2 Sales Invoice — "FMS — Forecourt" Section

Same as POS Invoice plus `fms_fleet_card_ref`, `fms_vehicle_number`, `fms_etims_invoice_number`.

### 8.3 Purchase Receipt — "FMS — Fuel Delivery" Section

Fields for: transporter, vehicle reg, docket number, driver name, expected quantity, dip before/after offload, sales during offload, computed received quantity, delivery variance, linked shift, variance approved by.

### 8.4 Warehouse — "FMS Tank" Section

`fms_is_fuel_tank` (Check), `fms_capacity_litres` (Float), `fms_pts2_tank_number` (Int), `fms_fuel_grade` (Link → Item).

---

## 9. Manual Station Workflows

### 9.1 Tank Calibration Chart Setup (One-Time Per Tank)

1. Obtain strapping table from EPRA-certified surveyor
2. `FMS → Tank Calibration Chart → New`; enter tank, capacity, calibration date, certifier, certificate number
3. Enter every row from the strapping table
4. Save — volume auto-derives from dip height thereafter. Recalibrate annually.

### 9.2 Manual Dip Reading

1. Take 3 tape readings, average
2. `FMS → Tank Dip Reading → New` on any mobile device
3. Select Tank, Reading Type, `reading_source = Manual Dipstick`
4. Enter `dip_height_mm` and `water_level_mm`
5. `volume_observed_l` auto-calculated via calibration chart on save

### 9.3 Meter Reading Entry Procedure

*Print and laminate for each pump island:*

```
┌──────────────────────────────────────────────────────────┐
│  SHIFT OPEN / CLOSE — METER READING PROCEDURE            │
│                                                          │
│  For EACH active nozzle, record THREE readings:          │
│                                                          │
│  1. Electronic Volume (L)                                │
│     Read LITRES from the digital display                 │
│     Write ALL digits including decimals                  │
│     Example: 171,275,183.070                             │
│                                                          │
│  2. Electronic Cash (KES)                                │
│     Read KES from the digital display                    │
│     The number will be in the millions — write it all    │
│     Example: 29,387,277.20                               │
│                                                          │
│  3. Manual Mechanical (L)                                │
│     Read the number wheels in the panel window           │
│     Use a torch if needed — NEVER estimate               │
│     Example: 171,275,182.0                               │
│                                                          │
│  Before submitting: Elec Cash ÷ Elec Vol ≈ EPRA price   │
│  Man Mech should be close to Elec Vol                    │
│  Any mismatch → call your supervisor BEFORE closing      │
└──────────────────────────────────────────────────────────┘
```

---

## 10. PTS Controller Integration

### 10.1 Account Name Helper (centralised GL account resolution)

```python
# fms/utils/accounts.py
import frappe

_DEFAULTS = {
    "till_active":        "Till — Active",
    "safe_main":          "Safe — Main",
    "mpesa_clearing":     "MPesa Clearing",
    "card_clearing":      "Card Payment Clearing",
    "fleet_card_clearing":"Fleet Card Clearing",
    "fuel_sales_pms_unl": "Fuel Sales — PMS Unleaded",
    "fuel_sales_pms_vp":  "Fuel Sales — PMS V-Power",
    "fuel_sales_ago":     "Fuel Sales — AGO Diesel",
    "cogs_pms_unl":       "COGS — Fuel PMS Unleaded",
    "cogs_pms_vp":        "COGS — Fuel PMS V-Power",
    "cogs_ago":           "COGS — Fuel AGO Diesel",
    "fuel_inv_pms_unl":   "Fuel Inventory — PMS Unleaded",
    "fuel_inv_pms_vp":    "Fuel Inventory — PMS V-Power",
    "fuel_inv_ago":       "Fuel Inventory — AGO Diesel",
    "wetstock_var_pms":   "Wetstock Variance — PMS",
    "wetstock_var_ago":   "Wetstock Variance — AGO",
    "cash_short_over":    "Cash Short / Over",
    "drive_off_losses":   "Drive-Off Losses",
}

FUEL_ACCOUNT_KEYS = {
    "FUEL-PMS-UNL": ("fuel_sales_pms_unl","cogs_pms_unl","fuel_inv_pms_unl","wetstock_var_pms"),
    "FUEL-PMS-VP":  ("fuel_sales_pms_vp", "cogs_pms_vp", "fuel_inv_pms_vp", "wetstock_var_pms"),
    "FUEL-AGO":     ("fuel_sales_ago",     "cogs_ago",    "fuel_inv_ago",    "wetstock_var_ago"),
}

def get_account(short_name: str, company: str) -> str:
    try:
        prefs = frappe.get_doc("Forecourt Site Preferences", company)
        name = prefs.get(short_name) or _DEFAULTS.get(short_name)
    except frappe.DoesNotExistError:
        name = _DEFAULTS.get(short_name)
    if not name:
        frappe.throw(f"No account mapping for '{short_name}'.")
    abbr = frappe.get_cached_value("Company", company, "abbr")
    full = f"{name} - {abbr}"
    if not frappe.db.exists("Account", full):
        frappe.throw(f"Account '{full}' does not exist in ERPNext.")
    return full

def get_fuel_accounts(item_code: str, company: str) -> dict:
    if item_code not in FUEL_ACCOUNT_KEYS:
        frappe.throw(f"Unknown fuel item: {item_code}.")
    s, c, i, w = FUEL_ACCOUNT_KEYS[item_code]
    return {"sales": get_account(s, company), "cogs": get_account(c, company),
            "inventory": get_account(i, company), "wetstock_variance": get_account(w, company)}
```

### 10.2 PTS-2 HTTP Receiver

```python
# fms/api/pts2.py
import frappe, json, hmac, hashlib

@frappe.whitelist(allow_guest=True)
def receive():
    secret = frappe.db.get_single_value("FMS Settings", "pts2_secret_key")
    body = frappe.request.data
    sig  = frappe.request.headers.get("X-Signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        frappe.throw("Invalid signature", frappe.AuthenticationError)

    data = json.loads(body)
    device = frappe.db.get_value("PTS2 Device",
        {"device_id": data.get("DeviceId"), "active": 1},
        ["company", "name"], as_dict=True)
    if not device:
        frappe.throw(f"Unknown device: {data.get('DeviceId')}")
    frappe.db.set_value("PTS2 Device", device.name, "last_seen", frappe.utils.now())

    handlers = {
        "PumpTransaction": _handle_pump_transaction,
        "TankMeasurement":  _handle_tank_measurement,
        "Alert":            _handle_alert,
    }
    handler = handlers.get(data.get("RecordType"))
    if handler:
        handler(data, device.company)
    frappe.db.commit()
    return {"status": "ok"}

def _handle_pump_transaction(data, company):
    tx_number = data.get("TransactionNumber")
    # Deduplication — silently skip PTS retries
    if tx_number and frappe.db.exists("Forecourt Transaction",
            {"pts_transaction_number": tx_number, "company": company}):
        return

    config = frappe.db.get_value("Pump Configuration",
        {"pts_pump_id": str(data.get("PumpNumber")), "company": company, "is_active": 1},
        ["erpnext_pump", "fuel_grade_mapping"], as_dict=True)
    if not config:
        frappe.log_error(f"No pump config for pump {data.get('PumpNumber')}, {company}")
        return

    fuel_grade = frappe.parse_json(config.fuel_grade_mapping or "{}").get(
        str(data.get("FuelGradeId")))
    shift = frappe.db.get_value("Shift",
        {"company": company, "status": "Open"}, "name", order_by="opened_at desc")

    frappe.get_doc({
        "doctype": "Forecourt Transaction",
        "company": company, "shift": shift,
        "pump": config.erpnext_pump, "fuel_grade": fuel_grade,
        "posting_datetime": data.get("SaleEnd"),
        "quantity_litres": data.get("Volume"),
        "unit_price": data.get("Price"),
        "total_amount": (data.get("Volume") or 0) * (data.get("Price") or 0),
        "pts_transaction_number": tx_number,
        "payment_mode": "Cash", "status": "Draft",
    }).insert(ignore_permissions=True)
```

### 10.3 PTS-2 Station Configuration

| Setting | Value |
|---|---|
| Domain Name | `fms.shelldomain.co.ke` |
| URI | `/api/method/fms.api.pts2.receive` |
| Port | 443 (HTTPS) |
| Secret Key | From FMS Settings |
| SD Card Logging | ✅ **Required for upload retry** |
| WebSocket URI | `/api/method/fms.api.pts2.ws` |

### 10.4 hooks.py (Complete)

```python
# fms/hooks.py
app_name  = "fms"
app_title = "Forecourt Management System"

doc_events = {
    "Shift":            {"validate": "fms.doctype.shift.shift.validate",
                         "before_save": "fms.doctype.shift.shift.before_save"},
    "Meter Reading":    {"validate": "fms.doctype.meter_reading.meter_reading.validate"},
    "Tank Dip Reading": {"validate": "fms.doctype.tank_dip_reading.tank_dip_reading.validate",
                         "before_save": "fms.api.calibration.auto_derive_volume"},
    "Cash Event":       {"validate": "fms.doctype.cash_event.cash_event.validate"},
    "Fuel Price History":{"on_submit": "fms.api.price_push.push_to_pts",
                          "validate":  "fms.doctype.fuel_price_history.validate_epra_price"},
    "POS Invoice":      {"before_submit": "fms.overrides.pos_invoice.before_submit",
                         "on_submit":     "fms.overrides.pos_invoice.on_submit"},
    "Sales Invoice":    {"before_submit": "fms.overrides.sales_invoice.before_submit"},
    "Drive-Off Record": {"on_submit": "fms.doctype.drive_off_record.drive_off_record.on_submit"},
}

scheduler_events = {
    "all":    ["fms.tasks.watchdog_check_pts_devices"],
    "daily":  ["fms.tasks.send_daily_shift_summary",
               "fms.tasks.check_calibration_due_dates"],
    "hourly": ["fms.tasks.check_stale_open_shifts"],
}

fixtures = [
    {"dt": "Custom Field", "filters": [["dt", "in", [
        "POS Invoice", "Sales Invoice", "Purchase Receipt", "Warehouse", "Item"
    ]]]},
    {"dt": "Role", "filters": [["name", "in", [
        "Shell HQ Manager", "Shell HQ Auditor", "Site Manager",
        "Site Supervisor", "Site Cashier", "Pump Attendant"
    ]]]},
]
```

---

## 11. Shift Lifecycle & Cash Reconciliation

### 11.1 Opening a Shift

1. Supervisor creates `Shift → New`: company, date, label, cashier, supervisor
2. Lock EPRA rates: `rate_pms_unl = 214.20`, `rate_pms_vp = 229.00`, `rate_ago = 242.90`
3. Create `Cashier Session` for each cashier; issue floats → `Cash Event: Float Issued`
4. Opening dips for every active tank → `Tank Dip Reading: Shift Open`
5. Opening meter readings for every active nozzle — **all three types each**:
   - Electronic Volume (L) — from digital display
   - Electronic Cash (KES) — from digital display
   - Manual Mechanical (L) — from number wheels
6. Once all opening readings submitted → transition to `Readings Captured`
7. Status → `Open` — sales can begin

### 11.2 During the Shift

- All POS sales: correct payment method and named pump attendant (never blank/N/A)
- Fleet/credit sales → Sales Invoice (not POS) — these populate the `Invoices` column in reconciliation
- Cash pickup when till > KES 30,000: `Cash Event: Cash Pickup` + supervisor sign + envelope number — populates `Pymts` column
- Fuel delivery: Section 12
- Drive-off: `Drive-Off Record` with manager authorisation
- If second cashier takes over: new `Cashier Session`, not a new Shift

### 11.3 Closing a Shift

1. Read all pump displays — enter **all three closing meter readings** per nozzle
2. Take closing dips for all active tanks
3. Each cashier physically counts till and enters `actual_cash_close` in their Cashier Session
4. Enter non-cash totals per cashier: Invoices (credit sales), POS (mobile money), VISA (card)
5. Status → `Closing`
6. Supervisor runs "Run Meter Validation" → `Meter Validation Result` per nozzle
7. Resolve any Check B Fail/Critical (Amendment reading or pump inspection) and re-run
8. Supervisor runs "Compute Reconciliation" → `Shift Reconciliation` document created
9. Review per-cashier summaries (matches the paper Cash Rec Sheet)
10. Review per-tank wetstock summaries
11. If all balanced → Approve → Post GL Journal → Status → `Closed`
12. If Critical variance → Status → `Disputed` → investigate before GL

### 11.4 Automated GL Journal Entry — Variances Only

> **Critical rule: the shift-close GL Journal posts VARIANCES ONLY.**
>
> Revenue (CR Fuel Sales) and COGS (DR COGS, CR Fuel Inventory) are posted by each
> POS Invoice / Sales Invoice on_submit throughout the shift. Posting them again at shift
> close would double-count every shilling of sales. The shift-close JE handles only what
> did NOT get posted by those invoices: cash short/over, wetstock loss/gain, safe drops,
> and PDQ card variances.

```python
# fms/utils/gl.py

def post_shift_variances(shift_reconciliation_name: str) -> str:
    """
    Post VARIANCES ONLY at shift close.
    Revenue/COGS already posted by POS Invoice on_submit. Do not re-post.
    """
    sr    = frappe.get_doc("Shift Reconciliation", shift_reconciliation_name)
    shift = frappe.get_doc("Shift", sr.shift)
    if sr.gl_journal:
        frappe.throw("Journal Entry already posted.")
    if not sr.approved_by:
        frappe.throw("Shift Reconciliation must be approved before posting GL.")

    company  = shift.company
    prefs    = frappe.get_doc("Forecourt Site Preferences", company)
    accounts = []

    # 1. Cash Short / Over per cashier
    for cs in sr.cashier_summary:
        cv = frappe.utils.flt(cs.cash_variance)
        if abs(cv) > 0.01:
            accounts.append({
                "account": prefs.cash_over_account,
                "debit_in_account_currency":  abs(cv) if cv < 0 else 0,   # short
                "credit_in_account_currency": cv       if cv > 0 else 0,   # over
                "party_type": "Employee", "party": cs.cashier,
            })

    # 2. Safe Drops
    safe_drops = frappe.get_all("Cash Event", {
        "shift": sr.shift, "event_type": "Safe Drop", "docstatus": 1
    }, ["amount", "name"])
    for sd in safe_drops:
        accounts += [
            {"account": prefs.safe_main_account,
             "debit_in_account_currency": sd.amount,
             "remarks": f"Safe Drop {sd.name}"},
            {"account": prefs.till_active_account,
             "credit_in_account_currency": sd.amount,
             "remarks": f"Safe Drop {sd.name}"},
        ]

    # 3. Wetstock variance per tank (only if >= 1.0 L to avoid rounding noise)
    for ts in sr.tank_wetstock_summary:
        var_kes = frappe.utils.flt(ts.variance_kes)
        if abs(var_kes) >= 1.0:
            accts = get_fuel_accounts(ts.fuel_grade, company)
            if ts.variance_l < 0:   # loss
                accounts += [
                    {"account": accts["wetstock_variance"],
                     "debit_in_account_currency": abs(var_kes)},
                    {"account": accts["inventory"],
                     "credit_in_account_currency": abs(var_kes)},
                ]
            else:                   # gain
                accounts += [
                    {"account": accts["inventory"],
                     "debit_in_account_currency": abs(var_kes)},
                    {"account": accts["wetstock_variance"],
                     "credit_in_account_currency": abs(var_kes)},
                ]

    # 4. PDQ card variance per terminal
    for row in sr.pdq_settlement_recon:
        cv = frappe.utils.flt(row.card_variance_kes)
        if abs(cv) > frappe.utils.flt(prefs.pdq_variance_warn_kes):
            accounts += [
                {"account": prefs.card_variance_account,
                 "debit_in_account_currency":  abs(cv) if cv < 0 else 0},
                {"account": prefs.pdq_clearing_account,
                 "credit_in_account_currency": abs(cv) if cv < 0 else 0},
            ]

    if not accounts:
        frappe.msgprint("No material variances to post.")
        return None

    # Balance check — mandatory before posting
    total_dr = sum(frappe.utils.flt(a.get("debit_in_account_currency", 0))  for a in accounts)
    total_cr = sum(frappe.utils.flt(a.get("credit_in_account_currency", 0)) for a in accounts)
    if abs(total_dr - total_cr) > 0.05:
        frappe.throw(f"GL imbalance: DR {total_dr:.2f} ≠ CR {total_cr:.2f} — do not post")

    je = frappe.new_doc("Journal Entry")
    je.voucher_type = "Journal Entry"
    je.posting_date = shift.shift_date
    je.company      = company
    je.cheque_no    = shift.name
    je.user_remark  = f"Shift Close Variances — {shift.name}"
    for row in accounts:
        je.append("accounts", row)
    je.insert(ignore_permissions=True)
    je.submit()

    frappe.db.set_value("Shift Reconciliation", sr.name, {
        "gl_journal": je.name, "status": "GL Posted"
    })
    frappe.db.set_value("Shift", sr.shift, {
        "status": "Closed", "closing_at": now_datetime(), "gl_journal": je.name
    })
    return je.name
```

**GL template for a Shell Maanzoni-style shift close (variances only):**

```
# WHAT IS NOT HERE (already posted by POS Invoices):
#   CR Fuel Sales — PMS Unleaded  204,785.65
#   CR Fuel Sales — AGO Diesel    414,526.49
#   DR COGS, CR Fuel Inventory    (stock deducted per transaction)

# WHAT IS POSTED AT SHIFT CLOSE:

# Cash short per cashier (short = debit the variance account)
DR  Cash Short / Over - SML          1,100.70   (Swedi Abuti — short KES 1,100.70)

# Cash over per cashier (over = credit the variance account)
CR  Cash Short / Over - SML            116.50   (Peter Mbeve — over)
CR  Cash Short / Over - SML              0.77   (Joseph Matale — over)

# Safe drops (cash physically moved from till to safe)
DR  Safe — Main - SML              129,295.00   (Abdirahman AHM safe deposit)
CR  Till — Active - SML            129,295.00

# Wetstock variance (if |variance_l| >= 1.0 L)
DR  Wetstock Variance — PMS - SML    (loss_l × WAC)   — only if material
CR  Fuel Inventory — PMS Unleaded    (loss_l × WAC)

# PDQ card variance (Phase 5, if terminals installed)
DR  Card Payment Variance - SML      (settlement_total − expected) if < 0
```

> **Rule:** `|total_DR − total_CR| ≤ KES 0.05` before the entry is posted.
> Any imbalance is a programming error — throw, do not post.

---

## 12. Fuel Delivery (GRN) Workflow

### 12.1 Delivery Variance Formula

```
received_qty = (dip_after − dip_before) + sales_during_offload
variance     = expected_qty − received_qty
```

Positive variance = supplier delivered less than docket. Negative = excess (rare, also investigate).

### 12.2 Workflow

1. Truck arrives → record truck reg, driver, docket number, fuel product, docket volume
2. `Tank Dip Reading → Delivery Before`
3. Offloading begins; normal dispensing continues
4. Offloading ends → wait 10–15 minutes for fuel to settle
5. `Tank Dip Reading → Delivery After`
6. System computes `dip_measured = after − before`
7. For PTS sites: `sales_during_offload` auto-calculated; for manual: read pump meters before/after offload
8. If `|variance| ≤ 0.5%`: Accept → raise Purchase Receipt at dip volume
9. If `|variance| > 0.5%`: Dispute → call supplier with dip evidence → do not post GRN until resolved

---

## 13. Wetstock Reconciliation

### 13.1 Complete Formula

```python
# fms/utils/wetstock.py

def compute_tank_wetstock(shift_name, tank):
    opening = frappe.db.get_value("Tank Dip Reading",
        {"shift": shift_name, "tank": tank, "reading_type": "Shift Open", "docstatus": 1},
        "volume_observed_l")

    deliveries = frappe.db.sql("""
        SELECT COALESCE(SUM(dip_measured_l), 0) FROM `tabFuel Delivery Dip`
        WHERE shift=%s AND tank=%s AND status='Accepted' AND docstatus=1
    """, (shift_name, tank))[0][0]

    # RTT (Return to Tank) volumes — test dispensing at shift open, returned to tank
    # Must be subtracted or the formula overstates elec_vol_sold vs actual throughput
    rtt_volumes = frappe.db.sql("""
        SELECT COALESCE(SUM(mr.rtt_volume_l), 0)
        FROM `tabMeter Reading` mr
        JOIN `tabPump` p ON p.name = mr.pump
        WHERE mr.shift = %s AND p.tank = %s
          AND mr.reading_position = 'Shift Open'
          AND mr.meter_type = 'Electronic Volume'
          AND mr.docstatus = 1
    """, (shift_name, tank))[0][0]

    sales = frappe.db.sql("""
        SELECT
          COALESCE(SUM(ev_c.totalizer_value - ev_o.totalizer_value), 0) AS elec_vol
        FROM `tabMeter Reading` ev_c
        JOIN `tabMeter Reading` ev_o
            ON ev_o.shift=ev_c.shift AND ev_o.pump=ev_c.pump
           AND ev_o.nozzle_number=ev_c.nozzle_number
           AND ev_o.meter_type='Electronic Volume'
           AND ev_o.reading_position IN ('Shift Open','Carry Forward')
           AND ev_o.docstatus=1
        JOIN `tabPump` p ON p.name=ev_c.pump AND p.tank=%s
        WHERE ev_c.shift=%s AND ev_c.meter_type='Electronic Volume'
          AND ev_c.reading_position='Shift Close' AND ev_c.docstatus=1
    """, (tank, shift_name), as_dict=True)

    elec_vol    = frappe.utils.flt(sales[0].elec_vol if sales else 0)
    rtt         = frappe.utils.flt(rtt_volumes)
    # RTT subtracted: volumes returned to tank do not reduce stock
    theoretical = frappe.utils.flt(opening) + frappe.utils.flt(deliveries) - rtt - elec_vol

    actual = frappe.db.get_value("Tank Dip Reading",
        {"shift": shift_name, "tank": tank, "reading_type": "Shift Close", "docstatus": 1},
        "volume_observed_l")

    variance_l   = theoretical - frappe.utils.flt(actual)
    denom        = frappe.utils.flt(opening) + frappe.utils.flt(deliveries)
    variance_pct = (variance_l / denom * 100) if denom else 0.0
    abs_pct      = abs(variance_pct)

    if variance_l < 0 and abs_pct > 0.50:   cl = "Critical"
    elif variance_l < 0 and abs_pct > 0.30: cl = "Elevated"
    elif variance_l > 0 and abs_pct > 0.30: cl = "Gain"
    else:                                    cl = "Normal"

    return {
        "opening_stock_l": frappe.utils.flt(opening),
        "deliveries_l":    frappe.utils.flt(deliveries),
        "rtt_volumes_l":   rtt,
        "elec_vol_sold_l": elec_vol,
        "theoretical_closing_l": theoretical,
        "actual_closing_l": frappe.utils.flt(actual),
        "variance_l": variance_l, "variance_pct": round(variance_pct, 4),
        "classification": cl,
    }
```

### 13.2 Variance Classification

| Metric | Normal (Auto-Approve) | Elevated (Review) | Critical (Block) |
|---|---|---|---|
| Wetstock loss % | ≤ 0.30% | 0.30–0.50% | > 0.50% — blocks GL (FMS Manager override) |
| Wetstock gain % | — | Any > 0.30% | — (always flag) |
| Cash variance (KES) | ≤ 50 | 50–200 | > 200 — blocks GL |
| PDQ card variance (KES) | ≤ 50 | 50–200 | > 200 — blocks GL |
| Check A discrepancy | ≤ KES 5 | KES 5–20 | > KES 20 |
| Check B divergence | ≤ 0.30% | 0.30–0.50% | 0.50–1.00% Fail; > 1.00% Critical (lock pump) |
| Check E billed gap | ≤ KES 10 | KES 10–50 | > KES 50 — investigate attendant |

### 13.3 Meter-Based Theft Detection (Check E)

**Check E** compares the physical pump cash totalizer increment against total POS Invoice
amounts for that nozzle. If a nozzle's Elec Cash shows KES 45,290 dispensed but only KES
45,230 appears in submitted POS Invoices for that nozzle, KES 60 of fuel was dispensed
without being billed — a specific attendant accountability issue.

Check E is computed in `fms/utils/meter.py:run_meter_validation()` and stored in the
`Meter Validation Result` doctype. It uses `fms_nozzle_number` on POS Invoice — this is
why the field is Required (not optional) on POS Invoice.

---

## 14. Fleet Cards & Credit Customers

**Fleet Card doctype:** card number, customer, grade restriction, credit limit, volume/amount limit per fill, RFID tag for PTS-2 authorisation, expiry date.

**Authorisation flow (PTS-2):** Driver presents card → PTS-2 reads RFID → FMS checks active/limit/grade → `AuthorizePump` back to PTS-2 → pump unlocks → Forecourt Transaction with `payment_mode = Fleet Card` → Sales Invoice at shift close.

**Monthly cycle:** Sales Invoices for credit customers at shift close → monthly statement → Payment Entry clears AR.

---

## 15. Kenya Compliance

**VAT (16%):** Create tax template `Kenya Fuel VAT 16%`, rate 16%, account `VAT Payable`. Apply to all POS Profiles and Sales Invoice defaults.

**Excise Duty:** Embedded in supplier invoice price. Model as Landed Cost on GRN — after submitting Purchase Receipt, create `Landed Cost Voucher` and add excise component. ERPNext adjusts WAC upward.

**eTIMS Integration:** On POS Invoice and Sales Invoice `on_submit`, POST to KRA eTIMS API. Store returned invoice number and QR code. Log failures but do not block invoice submission — flag for manual retry.

**EPRA Price Cap Validation:** On `Fuel Price History.validate`, if `new_price > epra_max_price` and `approved_by` is empty, throw. If approved, allow with warning.

---

## 16. Security & Data Isolation

**ERPNext User Permissions** on `Company` filter all list views, reports, and forms.  
**FMS Company field** on every doctype — PTS receivers set it from the device registry.

> **Critical for SQL reports:** User Permissions do not filter raw Query Reports. Every custom FMS SQL report must include `WHERE company IN %(companies)s`.

**PTS-2 HMAC:** `hmac.compare_digest()` (constant-time) prevents timing attacks.

### Role Permission Matrix

| DocType | HQ Mgr | HQ Audit | Site Mgr | Supervisor | Cashier |
|---|---|---|---|---|---|
| Shift | RW/C/S | R | RW/C/S | RW/C/S | R |
| Meter Reading | RW/C/S/Amend | R | RW/C/S | RW/C/S | R |
| Cash Event | RW/C/S/Cancel | R | RW/C/S | RW/C/S | Create |
| Shift Reconciliation | RW | R | RW | R | — |
| Drive-Off Record | RW/C/S | R | RW/C/S | RW/C/S | R |
| Forecourt Site Prefs | RW | R | RW | R | — |

---

## 17. Offline Resilience & Error Handling

**PTS-2 offline:** Records queued on SD card; replayed on reconnect. Deduplication on `pts_transaction_number` handles bulk replay. SD card logging must be enabled in PTS-2 Parameters.

**PTS offline buffer:** When ERPNext receives a PTS-2 push but the database write fails (race condition, lock, etc.), the raw JSON payload is saved to the `PTS Buffer` doctype (status = Pending). A background task (`fms.tasks.retry_pts_buffer`) runs every 30 minutes and replays all Pending records. After 5 failed retries the record is marked Failed and a Forecourt Alert is raised. The `/tmp/fms_pts_buffer.json` approach is NOT used — it is lost on reboot and inaccessible across RQ workers.

**Shift close without PTS:** Attendants read pump displays manually; enter closing totalizers; proceed normally.

**Duplicate prevention:** `pts_transaction_number` dedup key — duplicate inserts return `{"status": "ok"}` silently, not a 500 error.

---

## 18. Server Infrastructure & DevOps

| Sites | RAM | CPU | Disk |
|---|---|---|---|
| 1–5 | 4 GB | 2 vCPU | 50 GB SSD |
| 5–20 | 8 GB | 4 vCPU | 100 GB SSD |
| 20–50 | 16 GB | 8 vCPU | 200 GB SSD |

**Nginx WebSocket (add to bench site config):**
```nginx
location /api/method/fms.api.pts2.ws {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
}
```

**SSL:** `sudo certbot --nginx -d fms.shelldomain.co.ke`

**Monitoring:** Frappe worker queue depth (`bench doctor`); PTS-2 `last_seen` via watchdog job (alert if silent > 15 min); disk usage alert at 80%; MariaDB slow query log (> 2 sec).

---

## 19. Implementation Phases

### Phase 1 — ERPNext Foundation (Weeks 1–2)

- [ ] Install ERPNext v15; create Shell Kenya Limited + Shell Maanzoni sub-company
- [ ] Create Chart of Accounts with V-Power accounts separate from Unleaded
- [ ] Create Items: `FUEL-PMS-UNL`, `FUEL-PMS-VP`, `FUEL-AGO`
- [ ] Create tank Warehouses: Tank 1 (V-Power), Tank 2 (Unleaded), Tank 3 (Diesel)
- [ ] Create Roles; configure User Permissions
- [ ] Configure POS Profiles, Payment Methods, Kenya Fuel VAT 16%
- [ ] Create Employee records: Swedi Abuti, Peter Mbeve, Joseph Matale, Shadrack Kimulu, James Kitiapi, Joel Musembi, Abdirahman, etc.
- [ ] Create Supplier records for depots and transporters

### Phase 2 — FMS App & Manual Workflow (Weeks 3–4)

- [ ] `bench new-app fms`; `pip install pyserial pymodbus websocket-client --break-system-packages`
- [ ] Create all FMS doctypes including three-meter Meter Reading and Meter Validation Result
- [ ] Create Drive-Off Record, Forecourt Site Preferences, and all other doctypes
- [ ] Define custom fields via fixtures; `bench migrate`
- [ ] Configure Forecourt Site Preferences for Maanzoni
- [ ] Create Pump and Nozzle records matching actual hardware (UX/DX/VP pumps per island)
- [ ] Enter tank calibration charts for all three tanks
- [ ] Test full manual workflow: open shift → 3 meter readings per nozzle → dips → 5-cashier close → GL
- [ ] Verify per-cashier reconciliation matches paper sheet with 17-05-2026 data
- [ ] Configure eTIMS with KRA test environment

### Phase 3 — PTS Integration (Weeks 5–6)

- [ ] Order PTS-2 SDK from Technotrade; implement receiver against SDK simulator
- [ ] Create PTS-2 Device registry; create Pump Configuration mappings for all pumps
- [ ] Configure Nginx WebSocket proxy; configure PTS-2 at Maanzoni with server domain and secret key
- [ ] Test all data flows: pump transactions, tank measurements, alerts, price push, RFID sync
- [ ] Run 2-week parallel operation (paper + FMS) before cutting over

### Phase 4 — Multi-Site Rollout (Ongoing)

- [ ] Repeat Phases 1–3 for each additional site; HQ cross-site dashboard; train HQ Auditors
- [ ] Go-live site by site; 2-week parallel run per site

### Migration from Legacy System

1. Physical dip at cutover → `Stock Entry (Material Receipt)` for opening balances
2. Keep legacy read-only for 12 months; do not migrate history
3. Last shift on legacy, first shift on FMS — same calendar day
4. If FMS fails mid-shift: revert to paper dockets; reconcile retrospectively

---

## 20. Testing & Quality Assurance

### 20.1 Unit Tests — Meter Validation

```python
# fms/tests/test_meter_validation.py
import unittest, frappe

class TestMeterValidation(unittest.TestCase):

    def _run(self, elec_vol=100.0, elec_cash=None, mech_vol=None,
             rate=214.20, product="FUEL-PMS-UNL"):
        from fms.utils.meter import _validate_nozzle
        if elec_cash is None: elec_cash = elec_vol * rate
        if mech_vol  is None: mech_vol  = elec_vol
        nd = frappe._dict(pump="UX5", nozzle_number=2, fuel_product=product,
            tank="Tank 2 — Unleaded", elec_vol_sold=elec_vol,
            elec_cash_sold=elec_cash, mech_vol_sold=mech_vol)
        shift = frappe._dict(rate_pms_unl=rate, rate_pms_vp=229.0, rate_ago=242.9)
        return _validate_nozzle(nd, shift)

    def test_check_a_pass(self):
        r = self._run(elec_vol=100, elec_cash=100*214.20+3.0)
        self.assertEqual(r["check_a_status"], "Pass")

    def test_check_a_warning(self):
        r = self._run(elec_vol=100, elec_cash=100*214.20+10.0)
        self.assertEqual(r["check_a_status"], "Warning")

    def test_check_b_pass_typical_maanzoni(self):
        # U8 from live screen: 349.65 elec, 349.00 mech → 0.19% → Pass
        r = self._run(elec_vol=349.65, mech_vol=349.00)
        self.assertEqual(r["check_b_status"], "Pass")

    def test_check_b_fail_u7(self):
        # U7 from live screen: 80.53 elec, 80.00 mech → 0.65% → Fail
        r = self._run(elec_vol=80.53, mech_vol=80.00)
        self.assertEqual(r["check_b_status"], "Fail")

    def test_check_b_warning_l5(self):
        # L5 from live screen: 50.24 elec, 50.00 mech → 0.48% → Warning
        r = self._run(elec_vol=50.24, mech_vol=50.00, rate=242.90, product="FUEL-AGO")
        self.assertEqual(r["check_b_status"], "Warning")

    def test_check_b_critical_locks_pump(self):
        # 1.5% divergence → Critical → pump locked
        r = self._run(elec_vol=1000, mech_vol=985.0)
        self.assertEqual(r["check_b_status"], "Critical")

    def test_zero_sales_no_crash(self):
        r = self._run(elec_vol=0.0, elec_cash=0.0, mech_vol=0.0)
        self.assertEqual(r["check_b_divergence_pct"], 0.0)
        self.assertEqual(r["check_b_status"], "Pass")
```

### 20.2 Unit Tests — Wetstock Formula

```python
# fms/tests/test_wetstock.py
import unittest

class TestWetstockFormula(unittest.TestCase):

    def _compute(self, opening, deliveries, sales, actual):
        theoretical = opening + deliveries - sales
        variance_l  = theoretical - actual
        denom = opening + deliveries
        pct   = (variance_l / denom * 100) if denom else 0.0
        abs_pct = abs(pct)
        if variance_l < 0 and abs_pct > 0.50:   cl = "Critical"
        elif variance_l < 0 and abs_pct > 0.30: cl = "Elevated"
        elif variance_l > 0 and abs_pct > 0.30: cl = "Gain"
        else:                                   cl = "Normal"
        return {"theoretical": theoretical, "variance_l": variance_l,
                "variance_pct": round(pct, 4), "classification": cl}

    def test_balanced_shift(self):
        r = self._compute(5000, 0, 250, 4750)
        self.assertAlmostEqual(r["variance_l"], 0.0)
        self.assertEqual(r["classification"], "Normal")

    def test_critical_loss(self):
        r = self._compute(5000, 0, 250, 4710)
        self.assertGreater(abs(r["variance_pct"]), 0.5)
        self.assertEqual(r["classification"], "Critical")

    def test_delivery_included(self):
        r = self._compute(5000, 8000, 1750, 11240)
        self.assertAlmostEqual(r["theoretical"], 11250.0)

    def test_maanzoni_ux_reference(self):
        # Tank 2 Unleaded: 955.99 L sold this shift, typical opening ~7000 L
        r = self._compute(7000, 0, 955.99, 6040)
        # Theoretical: 6044.01; Actual: 6040 → loss 4.01 L = 0.057% → Normal
        self.assertEqual(r["classification"], "Normal")

    def test_maanzoni_dx_reference(self):
        # Tank 3 Diesel: 1702.44 L sold
        r = self._compute(12000, 0, 1702.44, 10290)
        # Theoretical: 10297.56; Actual: 10290 → loss 7.56 L = 0.063% → Normal
        self.assertEqual(r["classification"], "Normal")
```

### 20.3 Unit Tests — Calibration Chart

```python
# fms/tests/test_calibration.py
import unittest

class TestCalibration(unittest.TestCase):

    def _interp(self, dip_mm, chart=[(0,0),(1000,10000),(2000,25000)]):
        if dip_mm < chart[0][0] or dip_mm > chart[-1][0]:
            raise Exception("Out of range")
        for i in range(len(chart) - 1):
            lo, hi = chart[i], chart[i+1]
            if lo[0] <= dip_mm <= hi[0]:
                r = (dip_mm - lo[0]) / (hi[0] - lo[0])
                return lo[1] + r * (hi[1] - lo[1])

    def test_exact_boundary(self):
        self.assertEqual(self._interp(1000), 10000)

    def test_midpoint(self):
        self.assertAlmostEqual(self._interp(500), 5000, places=1)

    def test_above_range_raises(self):
        with self.assertRaises(Exception):
            self._interp(3000)
```

### 20.4 UAT Checklist (Per Site Go-Live)

```
Manual workflow:
□  Shift blocks sales until all three opening meter readings submitted per nozzle
□  Three types all required — cannot move to Readings Captured if any missing
□  Calibration chart interpolation: correct volume from dip height
□  5-cashier shift: each reconciles independently
□  Cash formula verified against 17-05-2026 paper sheet:
     □  Swedi Abuti:   expected 14,300.70 ✓
     □  Peter Mbeve:   expected 13,183.50 ✓
     □  Joseph Matale: expected 1,649.23 ✓
□  Check B: U7 at 0.65% → Fail; pump at 1.5% → Critical + locked
□  GL journal posts and balances (DR = CR within KES 0.05)
□  Drive-off: DR Drive-Off Losses / CR Fuel Sales — correct amounts
□  Delivery variance > 0.5% blocks GRN submission without approval

PTS-2 workflow:
□  Pump transaction appears within 30 seconds of dispense
□  Duplicate transaction (PTS retry) silently skipped
□  Tank measurement updates on ATG level change
□  Alert fires on probe disconnect
□  Price push reaches pump display within 5 seconds of save
□  RFID sync updates tag list on PTS-2
□  Reconnect after 8-hour offline: all records land, no duplicates

Kenya compliance:
□  VAT 16% calculated correctly on POS Invoice
□  eTIMS number returned and stored after submit
□  Price above EPRA cap blocked without approval
```

---

## 21. Known Limitations

**Sub-100ms pump authorisation.** Frappe's 50–200ms latency is fine for shift reconciliation but not for prepay flows. Use PTS-2's local OPT integration for prepay.

**Custom SQL reports.** User Permissions don't filter raw Query Reports. Every FMS SQL report must include an explicit company filter.

**WAC and delivery variance.** Purchase Invoice must match GRN received quantity, not docket quantity, to keep WAC consistent.

**N/A attendant.** The legacy system accepts blank/N/A attendants. ERPNext FMS blocks POS Invoice submission without a valid `fms_pump_attendant`. This is intentional — the legacy gap is eliminated.

**ERPNext upgrade risk.** Custom fields survive upgrades as Frappe Custom Field records. Always test `bench update` on staging before production.

**WebSocket stability.** Short-lived connections per command. Adequate for typical price update frequencies; persistent pool needed for 50+ simultaneous sites.

---

## 22. Appendix

### A. Daily Operating Checklist

**Shift Opening (Incoming Cashier + Supervisor):**
```
□  Previous shift = Closed (or Disputed with explanation)
□  Create Forecourt Shift: date, label, cashier(s), supervisor, EPRA rates locked
□  Create Cashier Session(s); issue floats → Cash Event: Float Issued (supervisor signs)
□  Opening dip — EVERY active tank:
     □  Tank 1 (V-Power)  □  Tank 2 (Unleaded)  □  Tank 3 (Diesel)
     □  Water levels — alert if > 20mm
□  Opening meter readings — EVERY active nozzle, ALL THREE TYPES:
     □  UX pumps: Elec Vol / Elec Cash / Man Mech
     □  DX pumps: Elec Vol / Elec Cash / Man Mech
     □  VP pumps: Elec Vol / Elec Cash / Man Mech
□  Transition → Readings Captured → Open
□  Brief attendants: do not dispense until system shows Open
```

**During the Shift:**
```
□  All POS: correct payment method + named attendant (never N/A or blank)
□  Fleet/credit → Sales Invoice (not POS) — this feeds Invoices column in cash rec
□  Till > KES 30,000: Cash Pickup + supervisor sign + envelope no. → Pymts column
□  Fuel delivery: Dip Before → wait 15 min → Dip After → GRN
□  Drive-off: Drive-Off Record with manager authorisation
```

**Shift Closing (Cashier + Supervisor):**
```
□  Each cashier physically counts till
□  Closing meter readings — EVERY active nozzle, ALL THREE TYPES
□  Closing dip — every active tank
□  Each cashier enters actual cash count in Cashier Session
□  Enter non-cash totals per cashier: Invoices / POS / VISA (matching paper sheet columns)
□  Status → Closing
□  Run Meter Validation → resolve any Check B Fail/Critical
□  Compute Reconciliation → review per-cashier summaries + wetstock
□  If balanced: Approve → Post GL → Status → Closed
□  If Critical: Status → Disputed → investigate
□  Brief incoming shift
```

### B. Variance Tolerance Quick Reference

| Metric | Normal | Elevated | Critical |
|---|---|---|---|
| Wetstock loss % | ≤ 0.3% | 0.3–0.5% | > 0.5% |
| Wetstock gain | — | Any > 0.3% | — |
| Delivery dip vs docket | ≤ 0.3% | 0.3–0.5% | > 0.5% |
| Cash variance (KES) | ≤ 50 | 50–200 | > 200 |
| Meter Check A (KES) | ≤ 5 | 5–20 | > 20 |
| Meter Check B (%) | ≤ 0.30% | 0.30–0.50% | > 0.50%; > 1.0% = lock pump |

### C. PTS-2 Field Mapping

| PTS-2 Field | ERPNext / FMS Field | Doctype |
|---|---|---|
| `DeviceId` | Lookup → `PTS2 Device.device_id` | PTS2 Device |
| `PumpNumber` | Resolved via Pump Configuration | Pump Configuration |
| `FuelGradeId` | Mapped → `fuel_grade` (Item) | Forecourt Transaction |
| `SaleEnd` | `posting_datetime` | Forecourt Transaction |
| `Volume` | `quantity_litres` | Forecourt Transaction |
| `TotalizerVolume` | `meter_before` | Forecourt Transaction |
| `TransactionNumber` | `pts_transaction_number` (dedup key) | Forecourt Transaction |
| `Tag` | Resolved → Employee via `fms_rfid_tag_id` | Cashier Session |
| `TankNumber` | Mapped → Warehouse via `fms_pts2_tank_number` | Tank Dip Reading |
| `ProductHeight` | `dip_height_mm` | Tank Dip Reading |
| `ProductVolume` | `volume_observed_l` | Tank Dip Reading |
| `AlertType` | `alert_type` | Forecourt Alert |

### D. Bench Commands Reference

```bash
# Installation
bench new-app fms
bench --site [site] install-app fms
bench --site [site] migrate
pip install pyserial pymodbus websocket-client --break-system-packages
bench restart

# Fixtures
bench --site [site] export-fixtures --app fms
bench --site [site] import-fixtures --app fms

# Testing
bench --site [site] run-tests --app fms --module fms.tests.test_meter_validation
bench --site [site] run-tests --app fms --module fms.tests.test_wetstock

# Manual job execution
bench --site [site] execute fms.tasks.watchdog_check_pts_devices
bench --site [site] execute fms.tasks.retry_pts_buffer

# Debugging
bench doctor
bench --site [site] show-pending-jobs
tail -f /home/frappe/frappe-bench/logs/web.error.log

# Maintenance
bench --site [site] clear-cache
bench --site [site] backup --with-files
bench update --pull --patch --build  # staging first
```

### E. Diagnostic SQL Queries

```sql
-- Open shifts (max 1 per station)
SELECT name, status, cashier, opened_at FROM `tabShift`
WHERE status IN ('Open', 'Closing') ORDER BY opened_at DESC;

-- Missing closing meter readings for a shift
SELECT fp.name AS pump, pn.nozzle_number, mr.meter_type
FROM `tabPump` fp
JOIN `tabPump Nozzle` pn ON pn.parent = fp.name
LEFT JOIN `tabMeter Reading` mr
    ON mr.pump = fp.name AND mr.nozzle_number = pn.nozzle_number
   AND mr.shift = 'SHIFT-2026-00001'
   AND mr.reading_position = 'Shift Close' AND mr.docstatus = 1
WHERE fp.is_active = 1 AND pn.is_active = 1 AND mr.name IS NULL;

-- Wetstock variance trend (last 30 days)
SELECT fs.shift_date, tws.tank,
    ROUND(tws.variance_l, 2) AS var_l,
    ROUND(tws.variance_pct, 4) AS var_pct,
    tws.classification
FROM `tabShift Reconciliation Tank Wetstock` tws
JOIN `tabShift Reconciliation` sr ON sr.name = tws.parent
JOIN `tabShift` fs ON fs.name = sr.shift
WHERE fs.shift_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
ORDER BY fs.shift_date DESC, tws.tank;

-- Per-cashier cash variance history
SELECT cashier, COUNT(*) AS shifts,
    ROUND(SUM(cash_over_under), 2) AS net_variance,
    SUM(CASE WHEN cash_over_under < 0 THEN 1 ELSE 0 END) AS short_count,
    MAX(ABS(cash_over_under)) AS max_single_variance
FROM `tabShift Reconciliation Cashier Summary`
GROUP BY cashier ORDER BY ABS(SUM(cash_over_under)) DESC;

-- POS Invoices missing shift link (data quality check)
SELECT name, posting_date, grand_total
FROM `tabPOS Invoice`
WHERE fms_shift IS NULL AND docstatus = 1
ORDER BY posting_date DESC LIMIT 20;
```

---

## 23. Architectural Corrections — Shift as Metadata

### 23.1 The Critical Principle

**A Shift does not record actual transactions.** It is a coordination and accountability framework. All actual financial, inventory, and purchasing events live exclusively in ERPNext's own modules:

| What actually happened | Where ERPNext records it | Shift role |
|---|---|---|
| Fuel sold to customer | POS Invoice → GL Entry | Linked via `fms_shift` custom field |
| Fleet/credit fuel sale | Sales Invoice → AR → GL | Linked via `fms_shift` |
| Fuel delivered to tank | Purchase Receipt → Stock Ledger → GL | Linked via `fms_linked_shift` |
| Wetstock loss written off | Stock Reconciliation or Material Issue → GL | Linked via `fms_shift` |
| Cash moved to safe | Journal Entry (DR Safe / CR Till) | Linked via `fms_shift` |
| RTT correction | Stock Entry (Material Transfer) → Stock Ledger | Linked via `fms_shift` |

The Shift's job is to:
1. Define the accountability period (who, when, at which station)
2. Capture the physical meter readings and dip readings that allow us to **verify** what ERPNext's modules recorded
3. Group all the related ERPNext documents so you can navigate from a single Shift record to every invoice, stock entry, and journal entry it generated
4. Identify discrepancies between physical reality (meters, dips) and what the system recorded (invoices, stock entries)

**The reconciliation does not create the GL — it verifies it.** When the manager approves a Shift Reconciliation and a Journal Entry is posted, that JE is for the **variance** (wetstock loss, cash short/over) — not for the sales revenue, which was already posted when each POS Invoice was submitted during the shift.

### 23.2 Implications for Doctype Design

The `Shift Reconciliation → Product Summaries` child table does not store revenue. It reads from submitted POS Invoices and Sales Invoices linked to the shift. The `gross_revenue` field is a computed display field — not a ledger field.

The `Shift Reconciliation → Tank Wetstock Summaries` child table does not deduct stock. The stock was already deducted when the POS Invoices were submitted (if `Update Stock = Yes` on the POS Profile) or via an automated Stock Entry. The wetstock summary **compares** what the stock ledger says against what the physical dip says.

```
Shift is a lens, not a ledger.
```

### 23.3 What "Shift Close" Actually Posts

The only new accounting event at shift close is:

1. **Wetstock variance JE** — if physical dip differs from stock ledger by a material amount
2. **Cash variance JE** — if cashier's actual cash count differs from expected
3. **Safe drop JE** — cash moving from Till to Safe account

Everything else (revenue, COGS, stock deductions) was already posted in real time as each POS Invoice was submitted.

---

## 24. Corrected Data Flow — Standard ERPNext Integration

### 24.1 Price Management via ERPNext Price List

Do not use a separate `Fuel Price History` doctype to store the current pump price. Use ERPNext's native `Price List` and `Item Price` doctypes, which already handle this correctly.

**Setup:**

```
Price List name:  "Pump Prices — Shell Maanzoni"
Currency:         KES
Selling:          Yes
Buying:           No
Country:          Kenya
```

Create one `Item Price` record per fuel grade per site:

| Item Code | Price List | Rate | Valid From |
|---|---|---|---|
| FUEL-PMS-UNL | Pump Prices — Shell Maanzoni | 214.20 | 2026-05-01 |
| FUEL-PMS-VP | Pump Prices — Shell Maanzoni | 229.00 | 2026-05-01 |
| FUEL-AGO | Pump Prices — Shell Maanzoni | 242.90 | 2026-05-01 |

When the shift opens, it reads the current `Item Price` for each grade and locks it into `rate_pms_unl`, `rate_pms_vp`, `rate_ago`. From that point on, the shift is immune to mid-shift price changes — the locked rate is the one used for all validations.

The POS Profile is configured to use the site-specific price list, so prices auto-fill on POS Invoices without manual entry.

**Custom fields to add on Item Price** (via FMS fixtures):

| Field | Type | Purpose |
|---|---|---|
| `fms_effective_shift` | Select | Current / Next Shift / Scheduled |
| `fms_scheduled_effective_at` | Datetime | When this price takes effect |
| `fms_pts_push_status` | Select | Pending / Pushed / Failed |
| `fms_approved_by` | Link → User | Required if rate > EPRA max |
| `fms_epra_max_price` | Currency | EPRA cap at time of this price |

### 24.2 Cashier as Employee with GL Account

Instead of a standalone Cashier doctype, use the ERPNext `Employee` record with custom fields. The key addition is linking the cashier to their physical till GL account.

**Custom fields on Employee** (via FMS fixtures):

| Field | Type | Purpose |
|---|---|---|
| `fms_rfid_tag_id` | Data | RFID card ID for PTS-2 pump authorisation |
| `fms_pts_pin` | Password | Optional PIN for PTS authorisation |
| `fms_till_gl_account` | Link → Account | The till account this cashier is responsible for |
| `fms_default_station` | Link → Branch | Default station for this employee |
| `fms_is_cashier` | Check | Flags employee as a cashier for POS and session setup |
| `fms_is_supervisor` | Check | Can authorise cash events |

When a `Cashier Session` is created, it copies `fms_till_gl_account` from the Employee record. This is the account that is debited in the GL Journal Entry at shift close for this cashier's actual cash count.

This eliminates the need for a separate Cashier doctype and keeps all payroll, leave, and HR data consolidated on the Employee record.

### 24.3 Territory for HQ Regional Grouping

Use ERPNext's native `Territory` hierarchy to group stations for HQ reporting. This is already used by ERPNext's sales reports and needs no customisation.

```
All Territories
└── Kenya
    ├── Nairobi Region
    │   ├── Shell Maanzoni      ← Territory on Customer/Company
    │   ├── Shell Westlands
    │   └── Shell Thika Road
    ├── Coast Region
    │   └── Shell Mombasa Road
    └── Rift Valley Region
        └── ...
```

Set the `Territory` field on each sub-company's Company record. HQ reports automatically filter by Territory to give regional views without any custom code.

### 24.4 Stock Levels from ERPNext Stock Module

HQ does not need a custom stock dashboard. ERPNext's built-in reports are the source of truth:

| Report | Location | What it shows |
|---|---|---|
| **Stock Balance** | Stock → Reports | Current litres per tank warehouse |
| **Stock Ledger** | Stock → Reports | Every movement: GRN in, sales out, adjustments |
| **Warehouse-wise Stock Balance** | Stock → Reports | Filter by warehouse group = all Maanzoni tanks |
| **Stock Summary** | Stock → Reports | By item group, filter `Fuel` |

For the HQ Dashboard, these are queried via Frappe's `frappe.db.sql()` or `frappe.get_report_doc()` — not recalculated from FMS doctypes.

---

## 25. Shift Auto-Open and Carry-Forward Logic

### 25.1 Shift Scheduling at the Station Level

The Shift Master (Forecourt Site Preferences) defines the shift schedule for each station:

**Add these fields to `Forecourt Site Preferences`:**

| Field | Type | Default | Notes |
|---|---|---|---|
| `shift_schedule_type` | Select | 24h / Multi-Shift | |
| `shift_start_time` | Time | 06:00 | For 24h stations: daily start time |
| `shift_duration_hours` | Int | 24 | For 24h stations |
| `shift_1_start` | Time | 06:00 | For multi-shift: Shift 1 start |
| `shift_1_label` | Data | Day | |
| `shift_2_start` | Time | 14:00 | Shift 2 start |
| `shift_2_label` | Data | Evening | |
| `shift_3_start` | Time | 22:00 | Shift 3 start |
| `shift_3_label` | Data | Night | |
| `auto_open_next_shift` | Check | ✅ | Auto-create next shift on close |
| `carry_forward_readings_on_skip` | Check | ✅ | Carry forward if close skipped |

### 25.2 Auto-Open Logic

When a shift is closed, if `auto_open_next_shift = True`, the system immediately creates the next shift and populates its opening meter readings from the closed shift's closing readings.

```python
# fms/api/shift_auto.py

import frappe
from frappe.utils import now_datetime, add_days, get_datetime

def auto_open_next_shift(closed_shift_name: str) -> str:
    """
    Called from Shift.on_submit (status → Closed).
    Creates the next shift and populates opening readings.
    """
    closed = frappe.get_doc("Shift", closed_shift_name)
    prefs  = frappe.get_doc("Forecourt Site Preferences", closed.company)

    if not prefs.auto_open_next_shift:
        return None

    # Determine next shift date and label
    next_date, next_label = _next_shift_datetime(closed, prefs)

    # Create the new shift
    new_shift = frappe.new_doc("Shift")
    new_shift.company     = closed.company
    new_shift.station     = closed.station
    new_shift.shift_date  = next_date
    new_shift.shift_label = next_label
    new_shift.status      = "Open"
    new_shift.opened_at   = now_datetime()

    # Lock current EPRA rates from Item Price
    new_shift.rate_pms_unl = _get_current_price("FUEL-PMS-UNL", closed.company)
    new_shift.rate_pms_vp  = _get_current_price("FUEL-PMS-VP",  closed.company)
    new_shift.rate_ago     = _get_current_price("FUEL-AGO",     closed.company)
    new_shift.rate_dpk     = _get_current_price("FUEL-DPK",     closed.company)

    new_shift.insert(ignore_permissions=True)

    # Populate opening meter readings from previous shift's closing readings
    _carry_forward_meter_readings(closed_shift_name, new_shift.name)

    # Populate opening dip readings from previous shift's closing dips
    _carry_forward_dip_readings(closed_shift_name, new_shift.name)

    frappe.logger().info(
        f"Auto-opened shift {new_shift.name} for {closed.company} "
        f"following close of {closed_shift_name}"
    )
    return new_shift.name


def _carry_forward_meter_readings(from_shift: str, to_shift: str):
    """
    Copy closing meter readings from the previous shift as carry-forward readings
    for the new shift. These are read-only once submitted.

    IMPORTANT:
    - reading_position = "Carry Forward" (NOT "Shift Open") — distinguishable in audit.
    - read_by = closing supervisor of the previous shift (NOT Administrator).
    Supervisors may supersede a Carry Forward by submitting a fresh Shift Open
    reading after re-taping; the Carry Forward is then ignored by the validation engine.
    """
    closed = frappe.get_doc("Shift", from_shift)
    closing_readings = frappe.get_all("Meter Reading", filters={
        "shift": from_shift,
        "reading_position": "Shift Close",
        "docstatus": 1
    }, fields=["pump", "nozzle_number", "meter_type", "totalizer_value", "unit", "company"])

    for cr in closing_readings:
        mr = frappe.new_doc("Meter Reading")
        mr.shift            = to_shift
        mr.pump             = cr.pump
        mr.nozzle_number    = cr.nozzle_number
        mr.meter_type       = cr.meter_type
        mr.reading_position = "Carry Forward"          # ← NOT "Shift Open"
        mr.totalizer_value  = cr.totalizer_value
        mr.unit             = cr.unit
        mr.observed_at      = now_datetime()
        mr.read_by          = closed.supervisor        # ← NOT "Administrator"
        mr.company          = cr.company
        mr.notes            = f"Carried forward from shift {from_shift}"
        mr.insert(ignore_permissions=True)
        mr.submit()


def _carry_forward_dip_readings(from_shift: str, to_shift: str):
    """
    Copy closing dip readings from the previous shift as opening dip
    readings for the new shift.
    """
    closing_dips = frappe.get_all("Tank Dip Reading", filters={
        "shift": from_shift,
        "reading_type": "Shift Close",
        "docstatus": 1
    }, fields=["tank", "volume_observed_l", "dip_height_mm", "water_level_mm",
               "reading_source", "calibration_chart"])

    closed = frappe.get_doc("Shift", from_shift)
    for cd in closing_dips:
        dip = frappe.new_doc("Tank Dip Reading")
        dip.shift             = to_shift
        dip.company           = frappe.get_cached_value("Shift", to_shift, "company")
        dip.tank              = cd.tank
        dip.reading_type      = "Shift Open"
        dip.reading_source    = "Carry Forward"        # ← Distinct source; no re-interpolation
        dip.volume_observed_l = cd.volume_observed_l   # ← Copied as-is; no interpolation needed
        dip.dip_height_mm     = cd.dip_height_mm
        dip.water_level_mm    = cd.water_level_mm
        dip.calibration_chart = cd.calibration_chart
        dip.reading_datetime  = now_datetime()
        dip.recorded_by       = closed.supervisor      # ← NOT Administrator
        dip.notes             = f"Carried forward from shift {from_shift}"
        dip.insert(ignore_permissions=True)
        dip.submit()


def handle_skipped_close(shift_name: str) -> str:
    """
    Called when a supervisor opens a new shift without closing the previous one.
    The previous shift's opening readings are carried forward as its own closing
    readings (system assumes nothing changed — conservative, flags for review).
    """
    old_shift = frappe.get_doc("Shift", shift_name)
    if old_shift.status not in ("Open", "Readings Captured"):
        return None

    opening_meters = frappe.get_all("Meter Reading", filters={
        "shift": shift_name,
        "reading_position": "Shift Open",
        "docstatus": 1
    }, fields=["pump", "nozzle_number", "meter_type", "totalizer_value", "unit"])

    for om in opening_meters:
        # Check if a closing reading already exists
        exists = frappe.db.exists("Meter Reading", {
            "shift": shift_name, "pump": om.pump,
            "nozzle_number": om.nozzle_number, "meter_type": om.meter_type,
            "reading_position": "Shift Close"
        })
        if not exists:
            mr = frappe.new_doc("Meter Reading")
            mr.shift            = shift_name
            mr.pump             = om.pump
            mr.nozzle_number    = om.nozzle_number
            mr.meter_type       = om.meter_type
            mr.reading_position = "Shift Close"
            mr.totalizer_value  = om.totalizer_value  # Same as opening
            mr.unit             = om.unit
            mr.observed_at      = now_datetime()
            mr.notes            = "AUTO: Closing assumed same as opening — shift close was skipped"
            mr.insert(ignore_permissions=True)
            mr.submit()

    frappe.msgprint(
        f"Shift {shift_name} was not formally closed. "
        "Closing readings have been set equal to opening readings (zero sales assumed). "
        "Review this shift's reconciliation before approving.",
        indicator="orange", title="Skipped Shift Close"
    )
    return shift_name


def _get_current_price(item_code: str, company: str) -> float:
    """
    Read the current pump price from ERPNext Item Price for the site's price list.
    Applies scheduled prices if their effective datetime has passed.
    """
    price_list = frappe.db.get_value(
        "POS Profile", {"company": company}, "selling_price_list"
    )
    if not price_list:
        return 0.0

    # Check for a scheduled price that becomes effective now
    scheduled = frappe.db.sql("""
        SELECT ip.price_list_rate
        FROM `tabItem Price` ip
        WHERE ip.item_code = %(item)s
          AND ip.price_list = %(pl)s
          AND ip.fms_effective_shift = 'Next Shift'
          AND ip.fms_scheduled_effective_at <= NOW()
        ORDER BY ip.fms_scheduled_effective_at DESC
        LIMIT 1
    """, {"item": item_code, "pl": price_list}, as_dict=True)

    if scheduled:
        # Promote it: change to Current
        frappe.db.sql("""
            UPDATE `tabItem Price`
            SET fms_effective_shift = 'Current'
            WHERE item_code = %(item)s AND price_list = %(pl)s
              AND fms_effective_shift = 'Next Shift'
              AND fms_scheduled_effective_at <= NOW()
        """, {"item": item_code, "pl": price_list})
        return frappe.utils.flt(scheduled[0].price_list_rate)

    current = frappe.db.get_value("Item Price", {
        "item_code": item_code,
        "price_list": price_list,
        "fms_effective_shift": ["in", ["Current", None]],
    }, "price_list_rate", order_by="valid_from desc")
    return frappe.utils.flt(current)


def _next_shift_datetime(closed_shift, prefs):
    """Determine the next shift's date and label based on site schedule."""
    from frappe.utils import getdate, add_days
    if prefs.shift_schedule_type == "24h":
        return add_days(closed_shift.shift_date, 1), "Day"
    # Multi-shift: find the next label after closed_shift.shift_label
    labels = [prefs.shift_1_label, prefs.shift_2_label, prefs.shift_3_label]
    labels = [l for l in labels if l]
    try:
        idx = labels.index(closed_shift.shift_label)
        if idx + 1 < len(labels):
            return closed_shift.shift_date, labels[idx + 1]
        else:
            return add_days(closed_shift.shift_date, 1), labels[0]
    except ValueError:
        return add_days(closed_shift.shift_date, 1), labels[0] if labels else "Day"
```

### 25.3 Meter Reading Organisation on the Shift Form

Opening meter readings are displayed in a structured grid on the Shift form — grouped by pump and nozzle, with all three types side by side. Once submitted (carried forward or manually entered), they are **read-only**.

```
┌──────────────────────────────────────────────────────────────────┐
│  OPENING METER READINGS (Read-Only after submission)              │
├──────────┬──────────┬──────────────────────────────────────────┤
│  Pump    │  Nozzle  │  Elec Vol (L)   Elec Cash (KES)  Man Mech│
├──────────┼──────────┼──────────────────────────────────────────┤
│  UX5     │  2 (UX)  │  171,275,183  │  29,387,277  │  171,275,182│
│  UX6     │  2 (UX)  │  462,357.45   │  99,034,978  │  462,357.4 │
│  DX5     │  1 (DX)  │  55,065,556   │  15,918,476  │  55,065,556│
│  VP7     │  1 (VP)  │  9,884,632    │   2,263,540  │   9,884,632│
│  ...     │  ...     │  ...          │  ...         │  ...       │
└──────────┴──────────┴──────────────────────────────────────────┘

  CLOSING METER READINGS (Editable until shift closes)
  [Enter values here — system validates against opening]
```

The closing readings section is an editable mirror of the same structure. The system computes and displays the delta (Sold Ltrs, Sold KES, Var Ltrs) in real time as the supervisor types — exactly like the legacy screen's `VIEW THROUGHPUT AND SALES FOR FUEL PUMPS` section.

---

## 26. HQ Configuration Powers

### 26.1 What HQ Can Configure (Not Just Read)

HQ Manager has read access to all financial data across sub-companies. In addition, HQ Manager has **configuration rights** over sub-company settings — not to edit transactions, but to manage master data that drives how the sub-companies operate.

| Action | Where | Who |
|---|---|---|
| Set EPRA pump prices for any site | Item Price (with `fms_effective_shift`) | HQ Manager |
| Schedule bulk price change across all sites | Bulk Price Update Wizard | HQ Manager |
| Configure Forecourt Site Preferences for any site | Forecourt Site Preferences | HQ Manager |
| Create/edit Pump and Nozzle master data | Pump, Pump Nozzle | HQ Manager |
| Create/edit Tank Calibration Charts for any site | Tank Calibration Chart | HQ Manager |
| Add/deactivate employees for any site | Employee | HQ Manager |
| Set User Permissions for site staff | User Permissions | HQ Manager |
| View but NOT edit submitted transactions | All ERPNext doctypes | HQ Manager (read-only) |

This is enforced via ERPNext's Role Permission Manager:

```
HQ Manager role on Shift:         Read = 1,  Write = 0,  Submit = 0
HQ Manager role on Item Price:     Read = 1,  Write = 1,  Create = 1
HQ Manager role on Forecourt Site Preferences: Read = 1, Write = 1
HQ Manager role on POS Invoice:    Read = 1,  Write = 0
HQ Manager role on Journal Entry:  Read = 1,  Write = 0
```

### 26.2 Bulk Price Change with Scheduled Effective Shift

HQ Manager opens the Bulk Price Update Wizard (a custom Page in the FMS app):

1. Select fuel grades to update (checkboxes: UX, VP, DX, DPK)
2. Enter new prices for each grade
3. Select sites to apply to (checkboxes, Select All available)
4. Set effectiveness: `Immediately` or `Next Shift` (default) or `Scheduled: [datetime]`
5. Enter EPRA gazette reference
6. Click Apply

```python
# fms/api/bulk_price_update.py

import frappe

@frappe.whitelist()
def apply_bulk_price_update(grades: list, new_prices: dict,
                             companies: list, effective: str,
                             scheduled_at: str = None,
                             epra_ref: str = None) -> dict:
    """
    HQ Manager bulk price update. Creates Item Price records for each
    (item, company price list) combination.

    effective: 'immediate' | 'next_shift' | 'scheduled'
    """
    if not frappe.has_permission("Item Price", "write"):
        frappe.throw("Insufficient permissions for price update.")

    created = []
    for company in companies:
        price_list = frappe.db.get_value("POS Profile", {"company": company}, "selling_price_list")
        if not price_list:
            frappe.log_error(f"No POS Profile/price list found for {company}")
            continue

        for item_code in grades:
            new_rate = frappe.utils.flt(new_prices.get(item_code, 0))
            if not new_rate:
                continue

            epra_max = frappe.db.get_value("Item Price", {
                "item_code": item_code, "price_list": price_list,
                "fms_effective_shift": "Current"
            }, "fms_epra_max_price") or 0

            if epra_max and new_rate > frappe.utils.flt(epra_max):
                frappe.throw(
                    f"{item_code} at {company}: new price {new_rate} exceeds "
                    f"EPRA cap {epra_max}. Add EPRA gazette reference and approval."
                )

            ip = frappe.new_doc("Item Price")
            ip.item_code             = item_code
            ip.price_list            = price_list
            ip.price_list_rate       = new_rate
            ip.valid_from            = frappe.utils.today()
            ip.fms_effective_shift   = {
                "immediate":  "Current",
                "next_shift": "Next Shift",
                "scheduled":  "Scheduled"
            }.get(effective, "Next Shift")
            ip.fms_scheduled_effective_at = scheduled_at
            ip.fms_epra_max_price    = epra_max
            ip.fms_approved_by       = frappe.session.user
            ip.insert(ignore_permissions=True)
            ip.submit()

            # Push to PTS-2 controllers if immediate
            if effective == "immediate":
                from fms.api.pts2_commands import push_price_update
                push_price_update(company, item_code, new_rate)

            created.append({"company": company, "item": item_code, "rate": new_rate})

    return {"created": created, "count": len(created)}
```

---

## 27. Reporting Suite

### 27.1 Core ERPNext Reports Used Directly (No Customisation Needed)

These native ERPNext reports work out of the box and are the primary financial data sources for both HQ and station managers:

**Stock / Inventory:**

| Report | Path | FMS Use |
|---|---|---|
| Stock Balance | Stock → Reports | Current litres per tank; filter by warehouse group |
| Stock Ledger | Stock → Reports | Every stock movement with before/after qty |
| Warehouse-wise Stock Balance | Stock → Reports | All tanks at a glance |
| Stock Summary | Stock → Reports | Filter by Item Group = Fuel |
| Batch-wise Balance History | Stock → Reports | Per-delivery batch tracking |

**Sales / Revenue:**

| Report | Path | FMS Use |
|---|---|---|
| Sales Register | Accounts → Reports | All invoices by date, customer, item |
| Item-wise Sales Register | Accounts → Reports | Volume and revenue per fuel grade |
| POS Report | POS → Reports | Per-cashier, per-payment-method breakdown |
| Sales Analytics | Selling → Reports | Revenue trend over time |
| Customer-wise Sales | Selling → Reports | Fleet account spend |

**Purchasing:**

| Report | Path | FMS Use |
|---|---|---|
| Purchase Register | Accounts → Reports | All GRNs by date and supplier |
| Item-wise Purchase Register | Accounts → Reports | Litres received per grade |
| Purchase Analytics | Buying → Reports | Delivery cost trends |

**Finance / GL:**

| Report | Path | FMS Use |
|---|---|---|
| General Ledger | Accounts → Reports | All entries — filter by account or cost centre |
| Trial Balance | Accounts → Reports | Station-level P&L snapshot |
| Profit and Loss Statement | Accounts → Reports | Revenue vs COGS per station |
| Cash Flow Statement | Accounts → Reports | Cash position |
| Accounts Receivable | Accounts → Reports | Outstanding fleet invoices |

### 27.2 Custom FMS Script Reports

These are built in ERPNext as **Script Reports** (Python + JS) under `FMS → Reports`.

#### 27.2.1 Daily Shift Summary Report

Mirrors the current legacy system's output. One row per shift.

```python
# fms/report/daily_shift_summary/daily_shift_summary.py

import frappe
from frappe.utils import flt

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"fieldname": "shift_date",    "label": "Date",        "fieldtype": "Date",     "width": 100},
        {"fieldname": "station",       "label": "Station",     "fieldtype": "Data",     "width": 150},
        {"fieldname": "shift_label",   "label": "Shift",       "fieldtype": "Data",     "width": 80},
        {"fieldname": "cashier",       "label": "Cashier",     "fieldtype": "Data",     "width": 130},
        {"fieldname": "ux_vol",        "label": "UX Litres",   "fieldtype": "Float",    "width": 100},
        {"fieldname": "ux_revenue",    "label": "UX Revenue",  "fieldtype": "Currency", "width": 120},
        {"fieldname": "vp_vol",        "label": "VP Litres",   "fieldtype": "Float",    "width": 100},
        {"fieldname": "dx_vol",        "label": "DX Litres",   "fieldtype": "Float",    "width": 100},
        {"fieldname": "dx_revenue",    "label": "DX Revenue",  "fieldtype": "Currency", "width": 120},
        {"fieldname": "total_revenue", "label": "Total Revenue","fieldtype": "Currency","width": 130},
        {"fieldname": "cash_variance", "label": "Cash Var",    "fieldtype": "Currency", "width": 110},
        {"fieldname": "wetstock_var",  "label": "Wetstock Var L","fieldtype":"Float",   "width": 120},
        {"fieldname": "status",        "label": "Status",      "fieldtype": "Data",     "width": 90},
    ]

    conditions = []
    params = {}
    if filters.get("from_date"):
        conditions.append("s.shift_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]
    if filters.get("to_date"):
        conditions.append("s.shift_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]
    if filters.get("company"):
        conditions.append("s.company = %(company)s")
        params["company"] = filters["company"]
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Pull from POS Invoices (actual sales) grouped by shift
    data = frappe.db.sql(f"""
        SELECT
            s.shift_date, s.company AS station,
            s.shift_label, s.cashier,
            COALESCE(SUM(CASE WHEN pii.item_code = 'FUEL-PMS-UNL' THEN pii.qty  END), 0) AS ux_vol,
            COALESCE(SUM(CASE WHEN pii.item_code = 'FUEL-PMS-UNL' THEN pii.net_amount END), 0) AS ux_revenue,
            COALESCE(SUM(CASE WHEN pii.item_code = 'FUEL-PMS-VP'  THEN pii.qty  END), 0) AS vp_vol,
            COALESCE(SUM(CASE WHEN pii.item_code = 'FUEL-AGO'     THEN pii.qty  END), 0) AS dx_vol,
            COALESCE(SUM(CASE WHEN pii.item_code = 'FUEL-AGO'     THEN pii.net_amount END), 0) AS dx_revenue,
            COALESCE(SUM(pii.net_amount), 0) AS total_revenue,
            sr.cash_variance,
            sr.wetstock_variance_l AS wetstock_var,
            s.status
        FROM `tabShift` s
        LEFT JOIN `tabPOS Invoice` pi ON pi.fms_shift = s.name AND pi.docstatus = 1
        LEFT JOIN `tabPOS Invoice Item` pii ON pii.parent = pi.name
        LEFT JOIN `tabShift Reconciliation` sr ON sr.shift = s.name
        {where}
        GROUP BY s.name
        ORDER BY s.shift_date DESC, s.company, s.shift_label
    """, params, as_dict=True)

    return columns, data
```

#### 27.2.2 Per-Cashier Cash Reconciliation Report

Replicates the current paper Cash Reconciliation Sheet in ERPNext.

```python
# fms/report/cashier_cash_reconciliation/cashier_cash_reconciliation.py
import frappe

def execute(filters=None):
    filters = filters or {}
    columns = [
        {"fieldname": "cashier",       "label": "Cashier",        "fieldtype": "Data",     "width": 160},
        {"fieldname": "sales",         "label": "Sales",          "fieldtype": "Currency", "width": 130},
        {"fieldname": "invoices",      "label": "Invoices",       "fieldtype": "Currency", "width": 130},
        {"fieldname": "pos_payments",  "label": "POS",            "fieldtype": "Currency", "width": 110},
        {"fieldname": "visa_card",     "label": "VISA",           "fieldtype": "Currency", "width": 110},
        {"fieldname": "total_credits", "label": "Total Credits",  "fieldtype": "Currency", "width": 130},
        {"fieldname": "receipts",      "label": "Recpts",         "fieldtype": "Currency", "width": 110},
        {"fieldname": "payments_out",  "label": "Pymts",          "fieldtype": "Currency", "width": 110},
        {"fieldname": "expected_cash", "label": "Expected Cash",  "fieldtype": "Currency", "width": 130},
        {"fieldname": "actual_cash",   "label": "Actual Cash",    "fieldtype": "Currency", "width": 130},
        {"fieldname": "cash_over_under","label":"Over/(Under)",   "fieldtype": "Currency", "width": 120},
    ]

    data = frappe.db.sql("""
        SELECT
            srcs.cashier, srcs.sales, srcs.invoices, srcs.pos_payments,
            srcs.visa_card, srcs.total_credits, srcs.receipts, srcs.payments_out,
            srcs.expected_cash, srcs.actual_cash, srcs.cash_over_under
        FROM `tabShift Reconciliation Cashier Summary` srcs
        JOIN `tabShift Reconciliation` sr ON sr.name = srcs.parent
        JOIN `tabShift` s ON s.name = sr.shift
        WHERE s.name = %(shift)s
        ORDER BY srcs.cashier
    """, {"shift": filters.get("shift")}, as_dict=True)

    # Append totals row
    if data:
        totals = {f: sum(frappe.utils.flt(r.get(f, 0)) for r in data)
                  for f in ["sales","invoices","pos_payments","visa_card",
                             "total_credits","receipts","payments_out",
                             "expected_cash","actual_cash","cash_over_under"]}
        totals["cashier"] = "TOTAL"
        data.append(totals)

    return columns, data
```

#### 27.2.3 Wetstock Variance Trend Report

```python
# SQL for fms/report/wetstock_variance_trend
QUERY = """
SELECT
    s.shift_date, s.company AS station,
    tws.tank, tws.fuel_product,
    ROUND(tws.opening_stock_l, 1)       AS opening_l,
    ROUND(tws.deliveries_l, 1)          AS deliveries_l,
    ROUND(tws.elec_vol_sales_l, 3)      AS sales_l,
    ROUND(tws.theoretical_closing_l, 1) AS theoretical_l,
    ROUND(tws.actual_closing_l, 1)      AS actual_l,
    ROUND(tws.variance_l, 2)            AS variance_l,
    ROUND(tws.variance_pct, 4)          AS variance_pct,
    tws.classification,
    ROUND(tws.variance_kes, 2)          AS variance_kes
FROM `tabShift Reconciliation Tank Wetstock` tws
JOIN `tabShift Reconciliation` sr ON sr.name = tws.parent
JOIN `tabShift` s ON s.name = sr.shift
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company)s IS NULL OR s.company = %(company)s)
ORDER BY s.shift_date DESC, s.company, tws.tank
"""
```

#### 27.2.4 Meter Reading Discrepancy Log

Surfaces every Check B warning or failure across all shifts for a date range.

```python
QUERY = """
SELECT
    s.shift_date, s.company AS station,
    mvr.pump, mvr.nozzle_number,
    ROUND(mvr.elec_vol_sold, 3) AS elec_vol_l,
    ROUND(mvr.mech_vol_sold, 1) AS mech_vol_l,
    ROUND(mvr.check_b_divergence_pct, 4) AS divergence_pct,
    mvr.check_b_status,
    mvr.check_a_status,
    mvr.overall_status
FROM `tabMeter Validation Result` mvr
JOIN `tabShift` s ON s.name = mvr.shift
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND mvr.check_b_status != 'Pass'
ORDER BY s.shift_date DESC, mvr.check_b_divergence_pct DESC
"""
```

#### 27.2.5 Delivery Reconciliation Register

```python
QUERY = """
SELECT
    fdd.delivery_end AS date,
    s.company AS station,
    fdd.truck_reg, fdd.docket_number, fdd.fuel_product,
    ROUND(fdd.docket_volume_l, 1) AS docket_l,
    ROUND(fdd.dip_measured_l, 1)  AS received_l,
    ROUND(fdd.delivery_variance_l, 2) AS variance_l,
    ROUND(fdd.delivery_variance_pct, 3) AS variance_pct,
    fdd.status, fdd.purchase_receipt
FROM `tabFuel Delivery Dip` fdd
JOIN `tabShift` s ON s.name = fdd.shift
WHERE fdd.delivery_end BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company)s IS NULL OR s.company = %(company)s)
ORDER BY fdd.delivery_end DESC
"""
```

#### 27.2.6 Cashier Performance Summary

```python
QUERY = """
SELECT
    srcs.cashier,
    COUNT(DISTINCT sr.shift)        AS shift_count,
    ROUND(SUM(srcs.sales), 2)       AS total_sales,
    ROUND(SUM(srcs.actual_cash), 2) AS total_cash_handled,
    ROUND(SUM(srcs.cash_over_under),2) AS net_variance,
    ROUND(AVG(srcs.cash_over_under),2) AS avg_per_shift,
    SUM(CASE WHEN srcs.cash_over_under < 0 THEN 1 ELSE 0 END) AS short_count,
    SUM(CASE WHEN srcs.cash_over_under > 0 THEN 1 ELSE 0 END) AS over_count,
    ROUND(MAX(ABS(srcs.cash_over_under)),2) AS largest_variance
FROM `tabShift Reconciliation Cashier Summary` srcs
JOIN `tabShift Reconciliation` sr ON sr.name = srcs.parent
JOIN `tabShift` s ON s.name = sr.shift
WHERE s.shift_date BETWEEN %(from_date)s AND %(to_date)s
  AND (%(company)s IS NULL OR s.company = %(company)s)
GROUP BY srcs.cashier
ORDER BY ABS(SUM(srcs.cash_over_under)) DESC
"""
```

---

## 28. HQ Dashboard

### 28.1 HQ Dashboard Design

The HQ Dashboard uses ERPNext's native **Dashboard** framework (Frappe Dashboard Doctype), populated by `Dashboard Chart` records linked to custom Script Reports or SQL queries.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SHELL KENYA HQ — FORECOURT DASHBOARD                  Today: 25 May 2026│
├───────────────────────────────┬─────────────────────────────────────────┤
│  FUEL STOCK — ALL SITES        │  TODAY'S REVENUE — BY SITE              │
│                                │                                         │
│  [Stacked Bar: litres per      │  [Bar Chart: KES revenue per company,   │
│   tank per company]            │   colour by product grade]              │
│                                │                                         │
│  Tank 2 UX — Maanzoni: 5,268 L │  Maanzoni:    KES 619,312              │
│  Tank 3 DX — Maanzoni: 10,240 L│  Mombasa Rd:  KES 412,500              │
│  Tank 2 UX — Westlands: 3,100 L│  Westlands:   KES 390,200              │
├───────────────────────────────┼─────────────────────────────────────────┤
│  OPEN SHIFTS                   │  CASH VARIANCE — LAST 7 DAYS            │
│                                │                                         │
│  ● Maanzoni — Day — OPEN       │  [Line chart per cashier, KES]          │
│  ● Mombasa — Day — OPEN        │  Swedi:   ▼ (1,100) yesterday          │
│  ● Westlands — CLOSED          │  Peter:   △ 116.50 yesterday           │
│  ● Thika — Disputed ⚠️          │  Joseph:  △ 0.77 yesterday            │
├───────────────────────────────┼─────────────────────────────────────────┤
│  WETSTOCK ALERTS               │  METER CHECK B — RECENT FAILS           │
│                                │                                         │
│  ⚠️ Mombasa Tank 2: 0.6% loss  │  ⚠️ U7 — Maanzoni: 0.65% (Fail)       │
│  ✅ Maanzoni: all normal       │  ⚠️ L5 — Maanzoni: 0.48% (Warning)    │
│  ⚠️ Thika: delivery disputed   │  ✅ All others: Pass                    │
└───────────────────────────────┴─────────────────────────────────────────┘
```

### 28.2 Stock Level Dashboard Chart (Python)

```python
# fms/dashboard_chart/fuel_stock_by_site.py

import frappe
from frappe.utils import flt

@frappe.whitelist()
def get_fuel_stock_by_site():
    """
    Returns current stock levels per tank per company.
    Reads from ERPNext Stock Ledger (bin table) — the source of truth.
    """
    rows = frappe.db.sql("""
        SELECT
            w.company,
            w.name AS warehouse,
            w.fms_fuel_grade AS item_code,
            COALESCE(b.actual_qty, 0) AS qty_litres
        FROM `tabWarehouse` w
        LEFT JOIN `tabBin` b ON b.warehouse = w.name AND b.item_code = w.fms_fuel_grade
        WHERE w.fms_is_fuel_tank = 1
        ORDER BY w.company, w.name
    """, as_dict=True)

    # Enrich with reorder alert
    for row in rows:
        reorder = frappe.db.get_value("Warehouse", row.warehouse, "fms_reorder_level_ltrs") or 0
        row["reorder_level"] = frappe.utils.flt(reorder)
        row["status"] = "Critical" if row.qty_litres < reorder else (
                         "Low" if row.qty_litres < reorder * 1.2 else "Normal")

    return rows


@frappe.whitelist()
def get_open_shifts_status():
    """Returns all currently open shifts for the HQ status panel."""
    return frappe.db.sql("""
        SELECT s.name, s.company, s.shift_date, s.shift_label,
               s.status, s.opened_at, s.cashier,
               TIMESTAMPDIFF(HOUR, s.opened_at, NOW()) AS hours_open
        FROM `tabShift` s
        WHERE s.status IN ('Open', 'Closing', 'Disputed')
        ORDER BY s.opened_at DESC
    """, as_dict=True)


@frappe.whitelist()
def get_today_revenue_by_site():
    """Reads from POS Invoice — the actual source of truth for revenue."""
    from frappe.utils import today
    return frappe.db.sql("""
        SELECT
            pi.company,
            pii.item_code,
            ROUND(SUM(pii.qty), 3)       AS qty_litres,
            ROUND(SUM(pii.net_amount), 2) AS revenue
        FROM `tabPOS Invoice` pi
        JOIN `tabPOS Invoice Item` pii ON pii.parent = pi.name
        WHERE pi.posting_date = %(today)s
          AND pi.docstatus = 1
          AND pii.item_code IN ('FUEL-PMS-UNL', 'FUEL-PMS-VP', 'FUEL-AGO', 'FUEL-DPK')
        GROUP BY pi.company, pii.item_code
        ORDER BY pi.company, pii.item_code
    """, {"today": today()}, as_dict=True)


@frappe.whitelist()
def get_wetstock_alerts():
    """Returns shifts with elevated or critical wetstock variance from the last 48h."""
    return frappe.db.sql("""
        SELECT
            s.company, s.shift_date, tws.tank, tws.fuel_product,
            ROUND(tws.variance_l, 2) AS variance_l,
            ROUND(tws.variance_pct, 4) AS variance_pct,
            tws.classification
        FROM `tabShift Reconciliation Tank Wetstock` tws
        JOIN `tabShift Reconciliation` sr ON sr.name = tws.parent
        JOIN `tabShift` s ON s.name = sr.shift
        WHERE tws.classification IN ('Elevated', 'Critical', 'Gain')
          AND s.shift_date >= DATE_SUB(CURDATE(), INTERVAL 2 DAY)
        ORDER BY s.shift_date DESC, tws.classification DESC
    """, as_dict=True)
```

### 28.3 Dashboard Definition (Frappe Dashboard Doctype)

Create this via `Setup → Dashboard → New Dashboard`:

```json
{
  "dashboard_name": "HQ Forecourt Dashboard",
  "charts": [
    {
      "chart": "Fuel Stock by Site",
      "width": "Half"
    },
    {
      "chart": "Today Revenue by Site",
      "width": "Half"
    },
    {
      "chart": "Cash Variance Trend",
      "width": "Half"
    },
    {
      "chart": "Wetstock Variance Trend",
      "width": "Half"
    }
  ]
}
```

Each chart is a `Dashboard Chart` with `chart_type: Custom` pointing to the Python methods above.

### 28.4 Per-Territory Stock View

Territory is an ERPNext native concept. To group stock by region:

```python
@frappe.whitelist()
def get_stock_by_territory():
    """Group fuel stock by Territory for regional HQ view."""
    return frappe.db.sql("""
        SELECT
            c.territory,
            w.company,
            w.fms_fuel_grade AS item_code,
            COALESCE(b.actual_qty, 0) AS qty_litres,
            w.fms_reorder_level_ltrs AS reorder_level
        FROM `tabWarehouse` w
        JOIN `tabCompany` c ON c.name = w.company
        LEFT JOIN `tabBin` b ON b.warehouse = w.name AND b.item_code = w.fms_fuel_grade
        WHERE w.fms_is_fuel_tank = 1
        ORDER BY c.territory, w.company, w.fms_fuel_grade
    """, as_dict=True)
```

---

## 29. Workspaces

### 29.1 Station Workspace

Create via `Setup → Workspace → New Workspace`. One workspace per station role, showing only the features that role needs daily.

**Station Workspace — Site Cashier / Supervisor:**

```
┌─────────────────────────────────────────────────────────────────┐
│  SHELL MAANZONI — FORECOURT STATION                             │
├──────────────────────────────────────────────────────────────────┤
│  QUICK LINKS (large icon buttons)                                │
│                                                                  │
│  [Open Shift]   [Meter Reading]   [Dip Reading]   [POS Invoice] │
│  [Cash Event]   [Fuel Delivery]   [Drive-Off]     [View Shift]  │
├──────────────────────────────────────────────────────────────────┤
│  TODAY'S SHIFT STATUS                                            │
│                                                                  │
│  Shift: SHIFT-2026-00142  Status: OPEN  Since: 06:00            │
│  Cashiers on duty: Swedi Abuti, Peter Mbeve, Joseph Matale       │
│  Meter readings: ✅ Opening done   Closing: pending              │
│  Dip readings:   ✅ Opening done   Closing: pending              │
├──────────────────────────────────────────────────────────────────┤
│  ALERTS                                                          │
│  ⚠️ U7 Pump: Meter Check B Warning (0.65%) — schedule calibration│
│  💧 No water contamination detected                             │
├──────────────────────────────────────────────────────────────────┤
│  REPORTS (station-scoped)                                        │
│  Daily Shift Summary | Cashier Cash Reconciliation              │
│  Wetstock Variance Trend | Delivery Reconciliation Register     │
└──────────────────────────────────────────────────────────────────┘
```

**Workspace definition (fms/fixtures/workspace.json):**

```json
{
  "doctype": "Workspace",
  "name": "FMS Station",
  "label": "Forecourt Station",
  "module": "FMS",
  "icon": "fa fa-gas-pump",
  "shortcuts": [
    {"type": "DocType", "link_to": "Shift",             "label": "Shifts"},
    {"type": "DocType", "link_to": "Meter Reading",      "label": "Meter Readings"},
    {"type": "DocType", "link_to": "Tank Dip Reading",   "label": "Dip Readings"},
    {"type": "DocType", "link_to": "Cash Event",         "label": "Cash Events"},
    {"type": "DocType", "link_to": "Fuel Delivery Dip",  "label": "Fuel Deliveries"},
    {"type": "DocType", "link_to": "Drive-Off Record",   "label": "Drive-Offs"},
    {"type": "Report",  "link_to": "Daily Shift Summary","label": "Shift Summary"},
    {"type": "Report",  "link_to": "Cashier Cash Reconciliation", "label": "Cash Rec Sheet"},
    {"type": "Page",    "link_to": "fms-shift-close",   "label": "Close Shift"}
  ],
  "cards": [
    {
      "label": "Shift Operations",
      "links": [
        {"type": "DocType", "name": "Shift"},
        {"type": "DocType", "name": "Meter Reading"},
        {"type": "DocType", "name": "Tank Dip Reading"},
        {"type": "DocType", "name": "Cashier Session"},
        {"type": "DocType", "name": "Cash Event"}
      ]
    },
    {
      "label": "Deliveries & Exceptions",
      "links": [
        {"type": "DocType", "name": "Fuel Delivery Dip"},
        {"type": "DocType", "name": "Drive-Off Record"},
        {"type": "DocType", "name": "Forecourt Alert"},
        {"type": "DocType", "name": "Shift Reconciliation"}
      ]
    },
    {
      "label": "Station Reports",
      "links": [
        {"type": "Report", "name": "Daily Shift Summary"},
        {"type": "Report", "name": "Cashier Cash Reconciliation"},
        {"type": "Report", "name": "Wetstock Variance Trend"},
        {"type": "Report", "name": "Delivery Reconciliation Register"}
      ]
    }
  ]
}
```

### 29.2 HQ Workspace

```
┌─────────────────────────────────────────────────────────────────┐
│  SHELL KENYA HQ — FORECOURT MANAGEMENT                          │
├──────────────────────────────────────────────────────────────────┤
│  QUICK ACTIONS                                                    │
│                                                                  │
│  [Bulk Price Update]  [Site Configuration]  [View All Shifts]   │
│  [HQ Dashboard]       [EPRA Reports]        [Fleet Accounts]    │
├──────────────────────────────────────────────────────────────────┤
│  NETWORK SNAPSHOT                                                 │
│                                                                  │
│  Sites Active: 4/4   Open Shifts: 3   Disputed: 1 ⚠️            │
│  Total Fuel in Network: 47,230 L  (UX: 18,400 | DX: 26,800)    │
│  Today Revenue: KES 2,470,000 (target: KES 2,800,000)           │
├──────────────────────────────────────────────────────────────────┤
│  PENDING APPROVALS                                               │
│  □ Thika shift SHIFT-2026-00138 — Disputed (wetstock 0.7%)      │
│  □ Mombasa delivery FDD-2026-042 — Variance 0.6% needs approval │
│  □ Westlands price change IP-2026-019 — Review before next shift│
├──────────────────────────────────────────────────────────────────┤
│  CARDS: Configuration | Network Reports | Finance | Compliance   │
└──────────────────────────────────────────────────────────────────┘
```

**HQ Workspace definition:**

```json
{
  "doctype": "Workspace",
  "name": "FMS HQ",
  "label": "Forecourt HQ",
  "module": "FMS",
  "icon": "fa fa-building",
  "shortcuts": [
    {"type": "Page",    "link_to": "fms-bulk-price",     "label": "Bulk Price Update"},
    {"type": "Page",    "link_to": "fms-hq-dashboard",   "label": "HQ Dashboard"},
    {"type": "DocType", "link_to": "Forecourt Site Preferences", "label": "Site Config"},
    {"type": "Report",  "link_to": "Daily Shift Summary", "label": "All Sites Shifts"},
    {"type": "Report",  "link_to": "Wetstock Variance Trend", "label": "Wetstock Trend"},
    {"type": "Report",  "link_to": "Cashier Performance Summary", "label": "Cashier Performance"}
  ],
  "cards": [
    {
      "label": "Configuration",
      "links": [
        {"type": "DocType", "name": "Forecourt Site Preferences"},
        {"type": "DocType", "name": "Pump"},
        {"type": "DocType", "name": "Tank Calibration Chart"},
        {"type": "DocType", "name": "PTS2 Device"},
        {"type": "DocType", "name": "Item Price", "label": "Pump Prices"},
        {"type": "DocType", "name": "Employee",   "label": "Station Staff"}
      ]
    },
    {
      "label": "Network Reports",
      "links": [
        {"type": "Report", "name": "Daily Shift Summary"},
        {"type": "Report", "name": "Wetstock Variance Trend"},
        {"type": "Report", "name": "Meter Reading Discrepancy Log"},
        {"type": "Report", "name": "Delivery Reconciliation Register"},
        {"type": "Report", "name": "Cashier Performance Summary"},
        {"type": "Report", "name": "Stock Balance",    "is_query_report": 1},
        {"type": "Report", "name": "Item-wise Sales Register", "is_query_report": 1}
      ]
    },
    {
      "label": "Finance",
      "links": [
        {"type": "Report", "name": "Profit and Loss Statement", "is_query_report": 1},
        {"type": "Report", "name": "General Ledger",           "is_query_report": 1},
        {"type": "Report", "name": "Accounts Receivable",      "is_query_report": 1},
        {"type": "Report", "name": "Sales Analytics",          "is_query_report": 1}
      ]
    },
    {
      "label": "Pending Approvals",
      "links": [
        {"type": "DocType", "name": "Shift",            "label": "Disputed Shifts",
          "count_filter": {"status": "Disputed"}},
        {"type": "DocType", "name": "Fuel Delivery Dip","label": "Pending Deliveries",
          "count_filter": {"status": "Pending"}},
        {"type": "DocType", "name": "Item Price",       "label": "Scheduled Prices",
          "count_filter": {"fms_effective_shift": "Next Shift"}}
      ]
    }
  ]
}
```

### 29.3 Workspace Notification Badges

```python
# fms/tasks.py — runs on scheduler "all" (every minute-ish)

def update_workspace_notifications():
    """Push real-time notification counts to workspaces."""
    disputed_shifts = frappe.db.count("Shift", {"status": "Disputed"})
    pending_deliveries = frappe.db.count("Fuel Delivery Dip", {"status": "Pending", "docstatus": 0})
    pending_prices = frappe.db.count("Item Price", {"fms_effective_shift": "Next Shift", "docstatus": 1})

    frappe.publish_realtime("fms_hq_counts", {
        "disputed_shifts": disputed_shifts,
        "pending_deliveries": pending_deliveries,
        "pending_prices": pending_prices,
    }, room="hq_managers")

    # Per-station: alert if shift has been open > configured max hours
    open_shifts = frappe.db.sql("""
        SELECT name, company, opened_at,
               TIMESTAMPDIFF(HOUR, opened_at, NOW()) AS hours_open
        FROM `tabShift`
        WHERE status = 'Open' AND opened_at IS NOT NULL
        HAVING hours_open > 26
    """, as_dict=True)

    for s in open_shifts:
        frappe.publish_realtime("fms_stale_shift_alert", {
            "shift": s.name, "company": s.company, "hours": s.hours_open
        }, room=f"station_{s.company}")
```

---

## 30. Corrections to Earlier Sections

The following architectural corrections apply to sections already documented. Any implementation team member should treat these as overrides.

### 30.1 Section 7.10 — Shift Reconciliation: Revenue Fields Are Read-Only Computed

The `gross_revenue` and `total_volume_l` fields in Shift Reconciliation's Product Summaries child table are **computed from POS Invoices and Sales Invoices**, not stored values. They are populated when "Compute Reconciliation" is clicked by querying:

```python
# Revenue comes from submitted invoices — not from meter readings
pos_totals = frappe.db.sql("""
    SELECT pii.item_code,
           SUM(pii.qty) AS qty_litres,
           SUM(pii.net_amount) AS revenue
    FROM `tabPOS Invoice` pi
    JOIN `tabPOS Invoice Item` pii ON pii.parent = pi.name
    WHERE pi.fms_shift = %(shift)s AND pi.docstatus = 1
    GROUP BY pii.item_code
""", {"shift": shift_name}, as_dict=True)
```

The meter readings provide the **physical verification** of these invoice totals. If Elec Cash (physical pump meter) diverges from POS Invoice totals (Check E), that is the signal that sales were dispensed but not invoiced.

### 30.2 Section 7.3 — Shift: No `total_net_volume` Fields

Remove the fields `total_net_volume_pms`, `total_net_volume_ago`, `total_net_volume_dpk`, and `total_gross_amount` from the Shift doctype. These are computed outputs of the Shift Reconciliation — they do not belong on the Shift master as stored fields.

The Shift doctype stores only **coordination data**: who, when, what station, what EPRA rates, and the status of the accountability period. The numbers live in ERPNext's modules.

### 30.3 Section 11.3 — Shift Close: GL Journal Only for Variances

The GL Journal posted at shift close covers only:
- Wetstock variance (DR Wetstock Variance / CR Fuel Inventory)
- Cash variance per cashier (DR or CR Cash Short/Over)
- Safe drop (DR Safe — Main / CR Till — Active)

Revenue, COGS, and stock deductions were already posted when each POS Invoice was submitted during the shift. Do not re-post them.

If the POS Profile has `Update Stock = Yes`, stock is depleted in real time per POS Invoice — no additional Stock Entry is needed at shift close. If `Update Stock = No`, a batch Stock Entry is created at shift close by the reconciliation engine.

### 30.4 Section 3 — Item Price Replaces Rate Fields on Shift

The fields `rate_pms_unl`, `rate_pms_vp`, `rate_ago`, `rate_dpk` on the Shift doctype are still valid — they serve as the locked snapshot of prices at shift open, preventing price-change contamination mid-shift. But they are **populated from ERPNext Item Price** (via `_get_current_price()` in Section 25.2) rather than from a custom FMS price doctype.

---

*End of Document*

**Document Version:** 3.0.0 (with Sections 23–30 addendum)  
**Prepared by:** Awo ERP Technical Team  
**Status:** Draft — Pending Review and Approval  
**Reference Data:** Shell Maanzoni Legacy Screen 18-05-2026; Cash Reconciliation Sheet 17-05-2026  
**Next Review:** Q3 2026
