# 03 — Daily Shift Workflow

Audience: Shift Supervisor
Role required: `fms.group_fms_supervisor`

Target time: 15 minutes from last pump transaction to closed shift.

---

## Quick Reference

| Step | Where | Time |
|---|---|---|
| 1. Create & open shift | Forecourt → Shifts → New | 2 min |
| 2. Enter closing meter readings | Shift → Meter Readings tab | 5 min |
| 3. Enter tank dips | Shift → Tank Dips tab | 3 min |
| 4. Start Closing | Header button | < 1 min |
| 5. Complete attendant cash | Shift → Attendant Cash tab | 3 min |
| 6. Close Shift | Header button | < 1 min |
| 7. Print report | Header button | 30 sec |

---

## Step 1 — Create and Open the Shift

1. **Forecourt → Shifts → New**
2. Set **Shift Date** and **Shift Period** (Day / Evening / Night).
3. Set **Supervisor** to yourself.
4. Click **Open Shift**.

System auto-fills:
- Meter reading rows for every active nozzle, pre-filled with the previous shift's closing totalizers.
- Tank dip rows for every fuel tank, pre-filled with the previous shift's closing dip.

> **First shift ever:** Opening readings come from the "Current Meter" values on each nozzle in Pumps configuration. Verify against physical pump display before proceeding.

---

## Step 2 — Enter Closing Meter Readings

Go to **Meter Readings** tab. For each nozzle row:

| Column | What to enter |
|---|---|
| Attendant | Who operated this nozzle |
| Elec Cash (KES) | Pump electronic cash totalizer — read from pump display |
| Elec Meter (L) | Pump electronic volume totalizer — read from pump display |
| Manual Meter (L) | Mechanical odometer reading — read from pump display |
| RTT (L) | Litres returned-to-tank this shift (leave 0 if none) |

**Cash Sold (KES)** and **Vol Sold (L)** compute automatically — do not enter them.

---

## Step 3 — Enter Tank Dip Readings

Go to **Tank Dips** tab. For each tank row:

- Enter **Closing Dip (L)** from the physical dipstick measurement.

**Variance %** updates automatically.
Values above ±0.5% turn red and will block close (Gate 5).
Investigate before proceeding — see [04-gate-failures.md](04-gate-failures.md#gate-5--dip-variance).

---

## Step 4 — Click "Start Closing"

Click **Start Closing** in the header.

This:
1. Locks meter and dip editing.
2. Auto-creates attendant cash rows (if Auto-sync is on in Site Preferences).
3. Runs the residual allocation algorithm.

---

## Step 5 — Complete Attendant Cash

Go to **Attendant Cash** tab. For each attendant row:

| Column | Source | Action |
|---|---|---|
| Meter Sales (KES) | Auto — sum of nozzle cash meters for this attendant | Read-only |
| MPesa (KES) | Auto — from linked POS sessions | Read-only |
| Card (KES) | Auto — from linked POS sessions | Read-only |
| AR / Credit (KES) | Auto — from linked POS sessions | Read-only |
| Expenses (KES) | Auto — from expense bills linked to shift | Read-only |
| Cash Dropped (KES) | **Manual** | Enter the cash the attendant physically dropped |

**Balance = Meter Sales − (Cash Dropped + MPesa + Card + AR + Expenses)**

Every attendant's Balance must equal 0 before the shift can close.
If any balance is non-zero, see [04-gate-failures.md](04-gate-failures.md#gate-3--attendant-balance-not-zero).

### Linking POS Sessions

In the **Linked POS Sessions** field (Attendant Cash tab header), select the POS session(s) that ran during this shift. Sessions are filtered to the shift date. This auto-populates MPesa, Card, and AR amounts.

---

## Step 6 — Click "Close Shift"

When all balances are 0 and all gate indicators are green, click **Close Shift**.

The system runs 5 hard gate checks:

| Gate | Check | Tolerance |
|---|---|---|
| 1 | Meter volume ≈ POS volume (litres) | max(0.5 L, meniscus% × total sold) |
| 2 | Elec cash meter ≈ POS revenue (KES) | 100 KES |
| 3 | Every attendant Balance = 0 | Exactly 0 |
| 4 | FC Cash balance = 0 | Exactly 0 |
| 5 | Tank dip variance within meniscus | 0.5% default |

All gates must pass. There is no "close anyway" override.

On success:
- Meter logs and dip logs written (immutable).
- Sales GL journal entry posted (DR Cash Clearing | CR Revenue per product).
- Residual allocation journal entries posted.
- Shift state moves to **Closed**.
- Nozzle totalizers advance to closing readings (become opening for next shift).

---

## Step 7 — Print Reports

From the closed shift:

- **Print Shift Report** — full reconciliation (readings, cash, GL, residuals, dip variances).
- **Print Meter Movement** — opening/closing totalizers per nozzle + attendant summary.

Both are available as PDF buttons on the closed shift form.

---

## Residual Allocation — What Is It?

Attendants sometimes lump non-fuel sales (carwash, LPG) into a fuel category for speed.
Example: Attendant reports KES 250,000 Diesel MPesa but the Diesel meter shows only KES 180,000.

The residual algorithm:
1. Detects the KES 70,000 gap as a residual on Diesel.
2. Allocates it to other products (carwash, LPG) based on configured allocation rules.
3. Posts a journal entry: DR Diesel COGS | CR Carwash COGS (or relevant product).

Result: inventory and GL are accurate without manual intervention.
Allocations appear in the **Residual Allocation** tab of the closed shift.
