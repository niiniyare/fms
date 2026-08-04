# FMS Operations Runbook

Forecourt Management System — Daily Operating Procedures  
Audience: Shift Supervisors | Role required: FMS Shift Supervisor

---

## Quick Reference

| Task | Where | Time |
|---|---|---|
| Open a shift | Forecourt → Shifts → New | 2 min |
| Enter closing meter readings | Shift → Meter Readings tab | 5 min |
| Enter tank dips | Shift → Tank Dips tab | 3 min |
| Link POS sessions | Shift → Attendant Cash tab | 1 min |
| Review attendant balances | Shift → Attendant Cash tab | 3 min |
| Close shift | Header button "Close Shift" | 1 min |
| Print shift report | Header button "Print Shift Report" | 30 sec |

Target shift close time: **≤ 15 minutes** from last pump transaction.

---

## Daily Shift Workflow

### Step 1 — Create and Open the Shift

1. Go to **Forecourt → Shifts**.
2. Click **New**.
3. Set **Shift Date** and **Shift Period** (Day / Evening / Night).
4. Set **Supervisor** to yourself.
5. Click **Open Shift**.

The system automatically:
- Creates meter reading rows for every active nozzle, pre-filled with the previous shift's closing totalizers.
- Creates tank dip rows for every fuel tank, pre-filled with the previous shift's closing dip.

> If this is the **very first shift ever**, opening readings come from the meter totalizer values entered on each nozzle in Pumps configuration. Verify they match the physical meters before proceeding.

---

### Step 2 — Enter Closing Meter Readings (at shift end)

Go to the **Meter Readings** tab.

For each nozzle row, enter **three closing readings** from the pump display:

| Column | What to enter |
|---|---|
| Elec Cash (KES) | The pump's electronic cash totalizer (KES) |
| Elec Meter (L) | The pump's electronic volume totalizer (litres) |
| Manual Meter (L) | The mechanical odometer reading (litres) |

Also:
- **Attendant** — select the attendant who operated this nozzle this shift.
- **RTT (L)** — if any fuel was returned to tank during the shift, enter the volume here. This reduces the net volume sold without affecting the cash meter.

The **Cash Sold (KES)** and **Vol Sold (L)** columns compute automatically. You do not enter them.

---

### Step 3 — Enter Tank Dip Readings

Go to the **Tank Dips** tab.

For each tank, enter the **Closing Dip (L)** from the dipstick measurement.

The **Variance %** column updates automatically. Anything above **±0.5%** is highlighted in red and will block shift close (Gate 5). Investigate before proceeding.

---

### Step 4 — Link POS Sessions

Go to the **Attendant Cash** tab.

In the **Linked POS Sessions** field, select the POS session(s) that ran during this shift. Sessions are filtered to the shift date for easy picking.

Linking a session causes the system to automatically populate:
- MPesa amounts per attendant
- Card amounts per attendant
- AR/Credit amounts per attendant

> If no POS session ran (cash-only operation), leave this blank.

---

### Step 5 — Click "Start Closing"

Click the **Start Closing** button in the header.

This:
1. Moves the shift to **Closing** state (locks meter/dip editing).
2. Auto-creates attendant cash reconciliation rows for every attendant assigned to a nozzle (if **Auto-sync Attendant Cash Lines** is enabled in Site Preferences).
3. Runs the residual allocation algorithm in the background.

---

### Step 6 — Review and Complete Attendant Cash

Go to the **Attendant Cash** tab.

For each attendant row:

| Column | Source | Action |
|---|---|---|
| Meter Sales (KES) | Auto — sum of their nozzle cash meters | Read-only |
| MPesa (KES) | Auto — from linked POS sessions | Read-only |
| Card (KES) | Auto — from linked POS sessions | Read-only |
| AR/Credit (KES) | Auto — from linked POS sessions | Read-only |
| Expenses (KES) | Auto — from expense bills | Read-only |
| Cash Dropped (KES) | **Manual entry** | Enter the cash the attendant physically dropped into the safe |

**Balance** = Meter Sales − (Cash Dropped + MPesa + Card + AR + Expenses)

Every attendant's **Balance must be 0** before the shift can close (Gate 3).

If an attendant's balance is non-zero, see the [Gate Failures](#gate-failures) section.

---

### Step 7 — Click "Close Shift"

When all balances are 0 and all gates are green, click **Close Shift**.

The system runs five hard gate checks in sequence:

| Gate | Check | Tolerance |
|---|---|---|
| Gate 1 | Meter volume ≈ POS volume (liters) | max(0.5L, meniscus% × total) |
| Gate 2 | Cash meter ≈ POS revenue (KES) | 100 KES |
| Gate 3 | Every attendant balance = 0 | Exactly 0 |
| Gate 4 | FC Cash balance = 0 | Exactly 0 |
| Gate 5 | Tank dip variance within meniscus | 0.5% default |

If all gates pass:
- Meter and dip logs are written (immutable audit trail).
- Sales GL journal entry is posted (DR Cash Clearing | CR Revenue per product).
- Residual allocation journal entries are posted.
- Shift moves to **Closed** state.
- Nozzle totalizer positions advance to the closing readings (becoming opening readings for the next shift).

---

### Step 8 — Print Reports

From the closed shift, you can print:

- **Print Shift Report** — full reconciliation summary (GL entry, residuals, dip variances).
- **Print Meter Movement** — opening and closing readings per nozzle with attendant summary.

---

## Gate Failures

Gates block shift close until the supervisor resolves the underlying issue. This is by design — there is no "close anyway" override.

### Gate 1 Failed — Volume Reconciliation Gap

**What it means:** The total liters dispensed per pump meters differs from the total liters recorded in POS by more than the tolerance.

**Common causes:**
- A POS session from this shift is not linked. Go to Attendant Cash tab → Linked POS Sessions and add it.
- Meter reading was entered incorrectly. Go to Meter Readings tab and correct the closing value.
- RTT volume was not recorded. If fuel was returned to tank, enter the litres in the **RTT (L)** column.

**Resolution:** Fix the data, then click **Refresh Sales Summary** and try **Close Shift** again.

---

### Gate 2 Failed — Cash Reconciliation Gap

**What it means:** The sum of electronic cash meters (KES) differs from the total POS revenue recorded by more than 100 KES.

**Common causes:**
- A POS session is missing from the linked sessions list.
- The pump price setting differs from the POS product price (e.g. price was updated mid-shift without updating both).
- A transaction was completed on the pump but voided or not captured in POS.

**Resolution:**
1. Link any missing POS sessions (Attendant Cash tab).
2. If the gap is a genuine price mismatch, post a manual correction journal entry in Accounting, then confirm the gap is within tolerance before closing.

---

### Gate 3 Failed — Attendant Balance Not Zero

**What it means:** One or more attendants have `Balance ≠ 0`.

**Positive balance** (attendant owes money): Meter says they collected more than they accounted for.  
**Negative balance** (system owes attendant): More was accounted for than the meter recorded.

**Resolution options:**

| Situation | Action |
|---|---|
| Attendant forgot to declare some cash | Increase **Cash Dropped** |
| Attendant made an error in MPesa recording | Correct in POS, re-link session |
| Proven petty cash expense during shift | Raise a vendor bill in Accounting (auto-populates Expenses) |
| Unresolvable discrepancy (e.g. theft investigation) | Post a correction in Accounting and set Cash Dropped to balance |

---

### Gate 4 Failed — FC Cash Balance Not Zero

**What it means:** The sum of all attendant balances is non-zero. This is the aggregate of Gate 3 — resolve individual attendant balances first and this gate will clear automatically.

---

### Gate 5 Failed — Tank Dip Variance Too High

**What it means:** A tank's dip variance exceeds the meniscus percentage (default 0.5%).

Formula: `variance% = |opening − closing − meter_sold| / closing × 100`

**Common causes:**
- Dip reading was misread or entered incorrectly. Re-measure and correct.
- Delivery received during the shift was not recorded. Add a stock receipt in Inventory.
- Genuine wetstock loss (leakage, evaporation, meter calibration drift). Requires EPRA investigation.

**Resolution:**
1. Correct the dip reading if it was a data entry error.
2. If a delivery arrived during the shift, post a stock receipt in Inventory for the delivered volume, then re-enter the closing dip.
3. If the variance is genuine and investigated, post a stock adjustment in Inventory and document in the shift's **Notes** tab.

**To change the meniscus threshold permanently:** Forecourt → Configuration → Site Preferences → Variance Meniscus (%).

---

## Common Questions

**Can I edit meter readings after clicking "Start Closing"?**  
No. Meter and dip entries are locked in Closing state. Click **Open Shift** is not available — you must revert by having an Administrator reset the state via the Odoo shell. Contact your system administrator.

**Can I re-run the residual allocation after changing meter readings?**  
The allocation runs automatically on Start Closing. If you need to re-run it without closing, use the **Recalculate Residuals** button (visible in Closing state, supervisors only).

**What is the Meter Movement Report?**  
A per-nozzle report showing opening totalizer, closing totalizer, RTT, and net volume sold for all three meters (Elec Cash, Elec Volume, Manual), plus an attendant summary. Use it to verify individual nozzle figures before closing.

**Opening readings were wrong on this shift — what do I do?**  
Opening readings come directly from the nozzle's stored current meter positions (set when the previous shift closed). If they are wrong:
1. Do not close this shift yet.
2. Go to Forecourt → Configuration → Pumps → open the nozzle.
3. Correct the **Current Elec Cash**, **Current Elec Volume**, or **Current Manual Meter** value.
4. Delete this shift's meter entry rows and click **Open Shift** again to regenerate them with the corrected values.

**A nozzle was replaced and the totalizer reset to zero. How do I handle this?**  
Go to Pumps → open the nozzle → set all current meter fields to the new (reset) values. The next shift that opens will pick them up as opening readings. Document the reset in the shift's Notes tab.

**Can two supervisors work on the same shift simultaneously?**  
Yes — Odoo's standard ORM locking handles concurrent saves. However, only one person should enter closing readings to avoid overwriting each other's work.

---

## Audit Trail

All shifts write immutable records on close:

- **fms.meter_log** — one record per nozzle, capturing opening, closing, RTT, and net sold for all three meters.
- **fms.dip_log** — one record per tank, capturing opening volume, closing dip, and variance.

These records cannot be edited or deleted (the system raises an error if attempted). They form the EPRA-compliant audit trail.

GL entries are posted to Odoo's `account.move` and can be viewed from the closed shift form (Sales GL Entry field) or via Accounting → Journal Entries.

---

## Roles Summary

| Action | Attendant | Supervisor | Accountant |
|---|---|---|---|
| Enter meter/dip readings | ✓ | ✓ | ✓ |
| Open shift | — | ✓ | ✓ |
| Start closing | — | ✓ | ✓ |
| Close shift | — | ✓ | ✓ |
| Print reports | — | ✓ | ✓ |
| Edit site preferences | — | — | ✓ |
| View GL entries | — | — | ✓ |
| Delete shifts (draft only) | — | ✓ | ✓ |
