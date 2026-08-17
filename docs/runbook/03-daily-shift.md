# 03 — Daily Shift Workflow

Audience: Shift Supervisor
Role required: `fms.group_fms_supervisor`
Target: 15 minutes from last pump transaction to closed shift.

---

## Shift State Machine

```
Draft ──[Open Shift]──► Open ──[Start Closing]──► Closing ──[Close Shift]──► Closed
  ▲                                                    │
  │                                                    │ (sysadmin reset only)
  └────────────────────────────────────────────────────┘
```

| State | Who can act | Editable |
|---|---|---|
| Draft | Supervisor | Shift header fields |
| Open | Supervisor, Attendant | Meter readings, dip readings |
| Closing | Supervisor | Attendant cash only (meter/dip locked) |
| Closed | — | Nothing (immutable audit trail written) |

---

## Quick Reference

| Step | Location | Time |
|---|---|---|
| 1. Create shift | Forecourt → Shifts → New | 1 min |
| 2. Open shift | Header button | < 1 min |
| 3. Enter closing meter readings | Meter Readings tab | 5 min |
| 4. Enter tank dips | Tank Dips tab | 3 min |
| 5. Start Closing | Header button | < 1 min |
| 6. Link POS sessions | Attendant Cash tab | 1 min |
| 7. Enter cash dropped | Attendant Cash tab | 2 min |
| 8. Close Shift | Header button | < 1 min |
| 9. Print report | Header buttons | 30 sec |

---

## Step 1 — Create the Shift

**Forecourt → Shifts → New**

| Field | What to set |
|---|---|
| Shift Date | Today's date |
| Shift Period | Day / Evening / Night |
| Supervisor | Yourself (required before close) |
| Notes | Optional — deliveries received, incidents, nozzle faults |

One active shift per period is enforced. If another shift is already open or closing for the same period, the system will block creation.

---

## Step 2 — Open Shift

Click **Open Shift**.

System auto-generates:

**Meter reading rows** — one per active nozzle. Opening values auto-filled:
- From the previous shift's **closing totalizers** (stored in `fms.meter_log`).
- If no previous shift: from the **Current Meter** values on each nozzle (set in Pumps configuration).

**Dip entry rows** — one per fuel tank (locations where `Is Fuel Tank = True`). Opening dip auto-filled from the previous shift's `fms.dip_log.closing_volume`.

> **First shift ever:** Verify opening readings match the physical pump display before any sales begin. If they don't match, correct them in Forecourt → Configuration → Pumps before proceeding.

---

## Step 3 — Enter Closing Meter Readings

**Tab: Meter Readings**

Enter these at the end of the shift, from the physical pump display.

| Column | What to read | Notes |
|---|---|---|
| Attendant | Who operated this nozzle | Drives attendant cash allocation |
| Closing Elec Cash (KES) | Electronic cash totalizer (KES) | Read from pump display |
| Closing Elec Vol (L) | Electronic volume totalizer (litres) | Read from pump display |
| Closing Manual (L) | Mechanical odometer (litres) | Read from pump display |
| RTT Volume (L) | Litres returned to tank this shift | Only if fuel was pumped back into tank |

**Computed automatically (do not enter):**

| Column | Formula |
|---|---|
| Cash Sold (KES) | Closing Elec Cash − Opening Elec Cash |
| Qty Sold Elec (L) | Closing Elec Vol − Opening Elec Vol − RTT |
| Qty Sold Manual (L) | Closing Manual − Opening Manual |
| Amount (KES) | Qty Sold Elec × current price period price |

### RTT (Return to Tank)

RTT = fuel returned to tank during the shift without being sold (nozzle priming, calibration, test pumping).

Enter RTT in litres. It is deducted from Qty Sold Elec so it does not inflate sales figures.

---

## Step 4 — Enter Tank Dip Readings

**Tab: Tank Dips**

For each tank, enter the physical dipstick reading at shift end.

| Column | What to enter |
|---|---|
| Closing Dip (L) | Dipstick reading in litres |

**Computed automatically:**

| Column | Formula |
|---|---|
| Variance (L) | Opening − Closing − Meter Sold for this tank's product |
| Variance % | `abs(Variance) / Closing × 100` |

Variance % above ±0.5% turns red. This will block Gate 5 on close. Investigate before proceeding.

---

## Step 5 — Click "Start Closing"

Moves shift from Open to Closing state.

What happens automatically:
1. Meter and dip rows are **locked** — no further edits.
2. `closing_meter_date` and `closing_meter_user_id` are recorded.
3. If **Auto-sync Attendant Cash Lines** is enabled in Site Preferences: attendant cash rows are created for every attendant assigned to a nozzle in this shift.
4. The **Residual Allocation Algorithm** runs in the background (see Residual Allocation section below).

> If you need to correct a meter or dip reading after clicking Start Closing, a sysadmin must reset the shift state. See [07-troubleshooting.md](07-troubleshooting.md#resetting-shift-state).

---

## Step 6 — Link POS Sessions

**Tab: Attendant Cash → Linked POS Sessions field (header)**

Select the POS session(s) that ran during this shift. Sessions are filtered to the shift date.

Linking causes the system to pull from each POS session:
- MPesa amount per attendant
- Card amount per attendant
- AR / Credit amount per attendant

> If operations were cash-only (no POS session), leave this blank. Gate 2 still runs — ensure the electronic cash meter total and the manually entered cash are reconciled.

Click **Refresh Sales Summary** after linking if the totals don't update immediately.

---

## Step 7 — Review and Complete Attendant Cash

**Tab: Attendant Cash**

Each row represents one attendant's shift-end reconciliation.

| Column | Source | Action |
|---|---|---|
| Reported Sales (KES) | Auto — sum of their nozzle cash meters | Read-only |
| MPesa (KES) | Auto — from linked POS sessions | Read-only |
| Card (KES) | Auto — from linked POS sessions | Read-only |
| AR / Credit (KES) | Auto — from linked POS sessions | Read-only |
| Expenses (KES) | Auto — from vendor bills linked to shift + attendant | Read-only |
| Cash Dropped (KES) | **Manual entry** | Physical cash dropped into the safe |

**Balance formula:**
```
Balance = Reported Sales − (Cash Dropped + MPesa + Card + AR + Expenses)
```

**Every attendant's Balance must equal 0** before the shift can close (Gate 3).

Balance meanings:
- **Positive** — attendant collected more than accounted for (owes money).
- **Negative** — more was declared than the meter recorded (system owes attendant).

### Resolving Non-Zero Balances

| Situation | Fix |
|---|---|
| Attendant forgot some cash | Increase Cash Dropped |
| MPesa amount wrong | Correct in POS, re-link session |
| Change given out wrongly | Reduce Cash Dropped |
| Petty cash expense during shift | Raise vendor bill in Accounting → Bills, link to shift and attendant |
| Unresolvable (theft / investigation) | Post correction journal entry in Accounting, adjust Cash Dropped to zero, document in Notes |

---

## Step 8 — Close Shift

Click **Close Shift**.

### Gate Sequence (all must pass)

| Gate | What is checked | Tolerance |
|---|---|---|
| GL Config | Every fuel product has `fms_revenue_account_id` set | Zero tolerance |
| Supervisor | `supervisor_id` is set on the shift | Required |
| Gate 1 | Meter volume ≈ POS accounted volume (litres) | max(0.5 L, meniscus% × total meter L) |
| Gate 2 | Elec cash meter total ≈ POS revenue total (KES) | 100 KES |
| Gate 3 | Every attendant `balance = 0` | Exactly 0 (< 0.01 KES tolerance) |
| Gate 4 | FC Cash (sum of all attendant balances) = 0 | Exactly 0 |
| Gate 5 | Every tank dip variance% ≤ meniscus% | 0.5% default |

If any gate fails, an error message names the failing gate, the exact amount of the gap, and the fix. See [04-gate-failures.md](04-gate-failures.md).

**No "close anyway" button exists.**

### On Success

Within a single database transaction:

1. **`fms.meter_log`** written — one immutable record per nozzle (opening, closing, RTT, net sold for all three meters).
2. **`fms.dip_log`** written — one immutable record per tank (opening volume, closing dip, variance).
3. **Sales GL journal entry** posted:
   ```
   DR  Cash Clearing account    (total meter cash sold, KES)
   CR  [Product] Revenue account (per product, one line each)
   ```
4. **Residual allocation GL entries** posted — one `account.move` per allocation line:
   ```
   DR  [Target product] COGS account
   CR  [Source product] COGS account
   ```
5. Shift state moves to **Closed**.
6. Each nozzle's `current_elec_cash`, `current_elec_volume`, `current_man_mech` advance to the closing values — becoming opening readings for the next shift.
7. If **Auto-open Next Shift** is enabled in Site Preferences, the next shift is created and opened automatically.

---

## Step 9 — Print Reports

Available on the closed shift form:

| Button | Content | Use |
|---|---|---|
| Print Shift Report | Full reconciliation — readings, cash, residuals, dip variances, GL ref | File with handover |
| Print Meter Movement | Opening/closing totalizers per nozzle, RTT, net sold, attendant summary | Verify nozzle figures |
| Attendant Shift Statement | Per-attendant breakdown — sales, collections, balance | Give to each attendant |

---

## Residual Allocation — Deep Explanation

### The Problem

Attendants lump non-fuel sales into fuel categories for speed. Example:

```
Attendant reports: KES 250,000 Diesel (MPesa)
Diesel meter shows: KES 180,000

Gap: KES 70,000
Why: Attendant included KES 50,000 carwash + KES 20,000 LPG under "Diesel"
```

Without correction: Diesel inventory is over-stated, Carwash/LPG are understated, COGS is wrong.

### How the Algorithm Works

Runs automatically on **Start Closing**. Can be re-run manually with **Recalculate Residuals** button (visible in Closing state, Supervisor role).

**Step 1:** Compute product sales from meter entries (volume and cash per product).

**Step 2:** Compare to POS-accounted volumes. Products where `meter_volume > pos_volume` are **over-reported** (likely lumped in other products' sales). Products where `meter_volume < pos_volume` are **under-reported**.

**Step 3:** Greedy allocation — match over-reported litres to under-reported products in proportion to their gap size. Converts litres to KES using the current price period price.

**Step 4:** Write `fms.shift.residual.allocation` lines (one per source→target pair).

**On Close Shift:** Post one GL entry per allocation line:
```
DR  [Target product] COGS    (the product that actually sold)
CR  [Source product] COGS    (the product incorrectly reported)
```

### Viewing Allocations

Closed shift → **Residual Allocation** tab — shows each reallocation with source product, target product, litres, and KES amount.
GL entries are also visible from **Accounting → Journal Entries** filtered to the FMS journal on the shift date.

---

## Shift Duration Modes

Configured in Forecourt → Configuration → Site Preferences → Shift Duration.

| Mode | Periods | Auto-next |
|---|---|---|
| 8hr | Day → Evening → Night → Day (next date) | Yes (if enabled) |
| 12hr | Day → Night → Day (next date) | Yes (if enabled) |
| 24hr | One period per day | Yes (if enabled) |

If Auto-open Next Shift is enabled, closing one shift immediately creates and opens the next one with pre-filled opening readings.

---

## Concurrent Use

Multiple users can open the same shift simultaneously. Odoo ORM handles concurrent saves via record locking. However:

- Only one supervisor should enter closing readings to avoid overwriting.
- The **last save wins** on individual fields — coordinate via the shift Notes tab if two supervisors are working on the same shift.

---

## Empty Shifts

A shift with zero sales and zero attendant balances is an **empty shift**. Empty shifts bypass all gate checks and close immediately without posting any GL entries. Use to close a shift that was opened accidentally or for a period with no sales.
