# Shift Posting Guide — 29 August 2026
**Station:** Shell Maanzoni Service Station  
**Shift No:** 0 | **Date:** 29/08/2026  
**Supervisor / Operator:** Abdirahman Ahmed  
**Source docs:** Meter Movement By Product, Meter Movement By Cashier, Reconciliation Sheet, Sales Report, Invoice Register, Debtor Summary, Stock Calculations

---

## Overview of the Shift

| Metric | Value |
|---|---|
| Total Sales | KES 654,015.04 |
| Cash Collected | KES 73,400.00 |
| MPesa (AR) | KES 477,317.00 |
| VISA / Card | KES 30,040.00 |
| AR Invoices (Credit) | KES 524,457.00 |
| Total Fuel Sold | 3,001.37 L |
| Shift Variance | KES 0.00 (balanced) |

---

## Step 1 — Open the Shift

**Forecourt → Shifts → New**

| Field | Value |
|---|---|
| Date | 2026-08-29 |
| Shift No | 0 |
| Supervisor | Abdirahman Ahmed |
| Label / Notes | Day Shift — Shift 0 |

Click **Open Shift**. Opening meter readings auto-populate from nozzle init values (already seeded).

---

## Step 2 — Assign Attendants to Nozzles

Each meter entry row needs an attendant. Assignment per the METER BY CASHIER report:

**SHEDRACK KIMULU → Pumps 1–4** (all nozzles on P1, P2, P3, P4)

| Nozzle | Pump |
|---|---|
| DX1, UX1, VP1 | Pump 1 |
| DX2, UX2, VP2 | Pump 2 |
| DX3, UX3, VP3 | Pump 3 |
| DX4, UX4, VP4 | Pump 4 |

**PETER MBEVE → Pumps 5–8** (all nozzles on P5, P6, P7, P8)

| Nozzle | Pump |
|---|---|
| DX5, UX5, VP5 | Pump 5 |
| DX6, UX6, VP6 | Pump 6 |
| DX7, UX7, VP7 | Pump 7 |
| DX8, UX8, VP8 | Pump 8 |

**JOEL MUSEMBI** — handles car wash and lubricant sales only (no pump nozzles).

---

## Step 3 — Enter Closing Meter Readings

Go to **Meter Entries** tab. Enter closing electronic and mechanical readings from the METER MOVEMENT BY PRODUCT report (first non-Open row = closing reading).

### V-POWER (VP) Nozzles — Price KES 229.00/L

| Nozzle | Closing Elec (L) | Closing Mech (L) | Closing Cash Meter (KES) | Sold (L) |
|---|---|---|---|---|
| VP1 | 48,923.579 | 48,905.00 | 7,559,369.84 | 0.00 |
| VP2 | 82,275.651 | 82,285.00 | 12,687,594.21 | 81.83 |
| VP3 | 10,284.149 | 10,324.00 | 1,534,204.52 | 0.00 |
| VP4 | 21,751.243 | 21,761.00 | 3,420,813.10 | 0.00 |
| VP5 | 34,732.257 | 34,742.00 | 5,207,834.47 | 81.23 |
| VP6 | 52,594.642 | 52,604.00 | 7,994,041.20 | 21.83 |
| VP7 | 64,889.779 | 64,899.00 | 10,126,562.28 | 0.00 |
| VP8 | 65,354.663 | 65,364.00 | 9,766,609.43 | 9.82 |
| **TOTAL VP** | | | | **194.71 L** |

### UNLEADED EXTRA (UX) Nozzles — Price KES 210.00/L

| Nozzle | Closing Elec (L) | Closing Mech (L) | Closing Cash Meter (KES) | Sold (L) |
|---|---|---|---|---|
| UX1 | 476,525.501 | 476,386.00 | 66,924,930.31 | 288.55 |
| UX2 | 1,516,311.114 | 1,516,317.00 | 220,872,246.69 | 607.15 |
| UX3 | 174,112.838 | 174,055.00 | 24,089,350.93 | 0.00 |
| UX4 | 530,807.580 | 530,816.00 | 79,839,326.47 | 0.00 |
| UX5 | 459,205.125 | 304,542.00 | 65,583,073.39 | 72.85 |
| UX6 | 903,696.230 | 903,704.00 | 135,693,037.28 | 114.27 |
| UX7 | 709,715.180 | 709,724.00 | 100,595,136.87 | 101.85 |
| UX8 | 1,224,702.152 | 1,224,710.00 | 175,398,814.87 | 139.85 |
| **TOTAL UX** | | | | **1,324.52 L** |

> **Note UX5:** Elec meter shows 459,205.125 but mechanical shows 304,542.00 — large discrepancy exists in source data (likely meter was replaced or rolled over). Enter as per PDF exactly; system will compute variance.

### DIESEL EXTRA (DX) Nozzles — Price KES 213.80/L

| Nozzle | Closing Elec (L) | Closing Mech (L) | Closing Cash Meter (KES) | Sold (L) |
|---|---|---|---|---|
| DX1 | 1,596,085.878 | 1,596,045.00 | 230,779,778.90 | 193.36 |
| DX2 | 1,196,235.337 | 1,196,244.00 | 162,647,155.76 | 351.07 |
| DX3 | 2,015,390.085 | 2,015,380.00 | 284,237,019.84 | 0.00 |
| DX4 | 702,490.304 | 702,499.00 | 101,266,683.48 | 0.00 |
| DX5 | 764,559.485 | 764,567.00 | 101,739,068.45 | 187.52 |
| DX6 | 2,180,557.592 | 2,180,565.00 | 300,687,835.06 | 358.77 |
| DX7 | 885,226.392 | 885,027.00 | 113,698,468.49 | 110.15 |
| DX8 | 1,743,181.521 | 1,743,190.00 | 242,494,761.82 | 280.51 |
| **TOTAL DX** | | | | **1,481.38 L** |

---

## Step 4 — Enter Tank Dip Readings (Closing)

**Dip Entries tab** — physical stick readings at end of shift:

| Tank | Product | Opening Stock (L) | Meter Sales (L) | Closing Dip (L) | Shift Variance (L) |
|---|---|---|---|---|---|
| T1 | V-Power | 1,691.41 | 195.48 | **1,437.00** | +47.48 (gain) |
| T2 | Unleaded Extra | 11,519.52 | 1,324.52 | **9,920.00** | -75.48 (loss) |
| T3 | Diesel Extra | 25,869.62 | 1,481.37 | **24,178.00** | +26.37 (gain) |

Enter the **Closing Dip** column values (bold). No deliveries received this shift.

> VP variance +47.48 L and DX variance +26.37 L are within tolerance.  
> UX variance -75.48 L exceeds typical meniscus — supervisor should note but shift can close if within site preference threshold.

---

## Step 5 — Cash Reconciliation (Per Attendant)

**Cash Reconciliation tab** — one row per attendant:

### JOEL MUSEMBI
| Field | Value |
|---|---|
| Sales (reported) | KES 1,300.00 |
| Cash Collected | KES 1,300.00 |
| MPesa | 0.00 |
| Card / VISA | 0.00 |
| AR / Credit | 0.00 |
| Balance | **0.00** ✓ |

### SHEDRACK KIMULU
| Field | Value |
|---|---|
| Sales (meter, from pumps 1–4) | KES 332,797.05 |
| AR Invoices (MPesa credited) | KES 280,381.00 |
| VISA / Card | KES 15,540.00 |
| Total Credits | KES 295,921.00 |
| Receipts | KES 23.95 |
| Cash Collected (drop) | KES 36,900.00 |
| Balance | **0.00** ✓ |

### PETER MBEVE
| Field | Value |
|---|---|
| Sales (meter, from pumps 5–8) | KES 319,917.99 |
| AR Invoices (MPesa + credit) | KES 244,076.00 |
| VISA / Card | KES 14,500.00 |
| Total Credits | KES 258,576.00 |
| Receipts | KES (31.99) — negative, overpaid |
| Payments (expenses) | KES 26,110.00 |
| Cash Collected (drop) | KES 35,200.00 |
| Balance | **0.00** ✓ |

### ABDIRAHMAN AHMED (Supervisor)
| Field | Value |
|---|---|
| Receipts (cash safe collection) | KES 1,201,539.00 |
| Cheques / Transfers | KES 1,201,539.00 |
| Cash Collected | KES 0.00 |
| Balance | **0.00** ✓ |

**TOTAL Cash Dropped to Safe: KES 73,400.00**

---

## Step 6 — Post AR / Credit Invoices

**Forecourt → Credit Sales** or via shift AR tab. These are invoices raised during the shift:

### Cashier: SHEDRACK KIMULU

| Inv No | Customer | Product | Qty (L) | Amount (KES) | LPO |
|---|---|---|---|---|---|
| 059202 | Lipa Na MPesa | Diesel Extra | 1,311.42 | 280,381.00 | — |

### Cashier: PETER MBEVE

| Inv No | Customer | Product | Qty (L) | Amount (KES) | LPO |
|---|---|---|---|---|---|
| 059198 | Lipa Na MPesa | Diesel Extra | 921.12 | 196,936.00 | — |
| 059199 | Maasai Gas | Diesel Extra | 150.47 | 32,170.00 | LPO 14149 / KCK099R |
| 059200 | Master Fabricators Ltd | Diesel Extra | 18.71 | 4,000.00 | LPO 14245 / 4123 |
| 059201 | Master Fabricators Ltd | Diesel Extra | 51.31 | 10,970.00 | LPO 1446 / KCM567J |

**Total AR Invoiced: KES 524,457.00**

> MPesa invoices appear as AR in the old system. In FMS, classify Lipa Na MPesa as **MPesa payment method** (not true AR). The two Master Fabricators and Maasai Gas invoices are genuine credit customers.

---

## Step 7 — VISA / Card Receipts

From Reconciliation Sheet — VISA column:

| Attendant | Amount (KES) |
|---|---|
| Shedrack Kimulu | 15,540.00 |
| Peter Mbeve | 14,500.00 |
| **TOTAL** | **30,040.00** |

Post as **Card payment receipts** linked to respective attendants. From Debtor Summary:
- Shell Card (POS): KES 27,900.50
- Equity VISA: KES 453.80
- KCB VISA: KES 167,946.00 *(cumulative balance, not this shift only)*

---

## Step 8 — Non-Fuel Sales (for reference)

From SALES report — enter via POS or as manual non-fuel lines:

| Product | Code | Qty | Amount (KES) | Type |
|---|---|---|---|---|
| Helix HX8 5W40 T1 | 100025 | 1 | 1,180.00 | Lubricant |
| Helix Ultra 5W40 T1 | 100027 | 1 | 1,370.00 | Lubricant |
| Helix Ultra 5W40 T4 | 100028 | 1 | 4,980.00 | Lubricant |
| Brake Fluid DOT 4 T1/2 | 102002 | 2 | 1,260.00 | Lubricant |
| Shell AF Coolant | 102040 | 1 | 760.00 | Fluid |
| Super Glue | 104011 | 1 | 50.00 | Misc |
| Gas Load 13KG | 200001 | 1 | 3,510.00 | LPG |
| Fuel Filter 23390-OL041 | 500200 | 1 | 550.00 | Filter |
| Body Wash Saloon Car | 710601 | 3.5 | 700.00 | Car Wash |
| **TOTAL** | | | **14,360.00** | |

Joel Musembi handled KES 1,300 of this (car wash + some lubes as cash).

---

## Step 9 — Validate Gates Before Closing

| Gate | Check | Status |
|---|---|---|
| FC Cash = 0 | Total Expected Cash 73,400 = Actual Cash 73,400 | ✓ PASS |
| All attendants balanced | Joel 0, Shedrack 0, Peter 0, Abdirahman 0 | ✓ PASS |
| Tank variance VP T1 | +47.48 L (gain) | ✓ within tolerance |
| Tank variance UX T2 | -75.48 L (loss) | ⚠ check site preference threshold |
| Tank variance DX T3 | +26.37 L (gain) | ✓ within tolerance |

If UX variance fails gate: supervisor posts a stock adjustment or increases the meniscus tolerance in **Forecourt → Configuration → Site Preferences**.

---

## Step 10 — Close the Shift

Click **Close Shift**. System will:
1. Lock all meter and dip entries (immutable)
2. Post fuel sales journal (DR AR/Cash | CR Revenue by product)
3. Adjust stock quantities on T1, T2, T3
4. Write `fms.meter_log` and `fms.dip_log` audit trail records
5. Set state = `closed`

**Verify after close:**
- Forecourt → Shifts → (this shift) → Journal Entries — should show 3 product lines
- Inventory → Reporting → Inventory Valuation — stock reduced by meter sales quantities
- Accounting → Reports → General Ledger — fuel revenue accounts 400010/011/012 credited

---

## Key Totals Summary

| | VP | UX | DX | Total |
|---|---|---|---|---|
| Opening Stock (L) | 1,691.41 | 11,519.52 | 25,869.62 | 39,080.55 |
| Meter Sales (L) | 195.48 | 1,324.52 | 1,481.37 | 3,001.37 |
| Closing Dip (L) | 1,437.00 | 9,920.00 | 24,178.00 | 35,535.00 |
| Shift Variance (L) | +47.48 | -75.48 | +26.37 | -1.63 |
| Sales Value (KES) | 44,768.00 | 278,169.40 | 316,717.64 | **639,655.04** |

| Payment Method | KES |
|---|---|
| Cash dropped to safe | 73,400.00 |
| MPesa (via AR) | 477,317.00 |
| VISA / Card | 30,040.00 |
| Credit (Maasai Gas + Master Fab) | 47,140.00 |
| Non-fuel sales | 14,360.00 |
| **Grand Total** | **654,015.04** |
