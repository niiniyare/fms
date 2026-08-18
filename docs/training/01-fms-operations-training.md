# FMS Operations Training Guide
**Audience:** New shift supervisors and forecourt attendants  
**Trainer:** Use this document section-by-section. Each section has trainer notes and trainee exercises.  
**Duration:** Full day (6–7 hours with exercises)  
**System:** Forecourt Management System (FMS) on Odoo 18

---

## How to Use This Guide

This is a trainer-led document. Work through each section in order:
1. Read the **Concept** to the trainee — explain it in plain language.
2. Walk through the **Demonstration** on screen while they watch.
3. Let the trainee repeat the **Exercise** themselves with you watching.
4. Answer questions before moving to the next section.

Do not skip sections. Each builds on the previous.

---

## Part 1 — What Is FMS and Why Does It Exist?

### Concept

Every litre of fuel that leaves a nozzle must be accounted for — twice.

**First account:** The pump meter. The pump records exactly how many litres passed through the nozzle and how much money the customer was charged on the electronic display. This is the "meter record."

**Second account:** The tank dip. Before and after each shift, a supervisor physically measures the fuel level in the underground tank using a calibrated dipstick. The difference (opening dip minus closing dip) is how many litres were sold from that tank. This is the "dip record."

If these two numbers match, everything is fine. If they don't match — say the meter says 1,000 litres sold but the tank is missing 1,050 litres — there is a 50-litre loss that needs to be explained. That could be a calibration error, a leaking pipe, or even theft.

On top of this, the money collected at the pump must also be reconciled. Each attendant sells fuel and collects cash, MPesa, or card payments. At the end of a shift they must account for every shilling: how much they collected versus how much the pump meter says they should have collected.

**FMS does all of this reconciliation automatically** — it pulls meter readings, compares them against dips, checks the money, and blocks the shift from closing until every number balances. It then posts the GL journal entries automatically.

Without FMS, supervisors did this on paper. A 200-litre station processes 5–10 shifts per day across 3–5 pumps. Manual reconciliation took 30–60 minutes per shift and was error-prone.

**With FMS, a well-run shift closes in under 15 minutes.**

### The Residual Problem — Why Attendants "Lump" Sales

Attendants often record non-fuel sales (carwash, LPG, oils) under a fuel product because it is faster. Example:

> Attendant Ali services a customer who buys 50L Diesel (KES 11,140) and a KES 500 carwash. Ali records the whole transaction under "Diesel MPesa: KES 11,640."

The pump meter only recorded 50L Diesel = KES 11,140. But Ali reported KES 11,640. The KES 500 gap is a "residual" — it belongs to Carwash, not Diesel.

If left uncorrected:
- Diesel inventory appears 2.2L short (500 ÷ 222.80 per litre = 2.2L phantom shortage)
- Carwash revenue is understated
- COGS is wrong

FMS detects this automatically during shift close and reallocates the residual. The supervisor does not need to do anything — but they need to understand why the system does it.

---

## Part 2 — The System Layout

### Concept

FMS lives inside Odoo 18. Odoo is the main business system — it handles accounting, stock, employees, and reporting. FMS is a layer on top that adds fuel station operations.

When you log in, you see the top menu. For FMS, you use:

```
Forecourt
  ├── Operations
  │     └── Shifts              ← Where you open and close shifts
  ├── Configuration
  │     ├── Site Preferences    ← Station-wide settings (set by manager)
  │     ├── Station Setup       ← Pumps and nozzles (set by manager)
  │     └── Products            ← Fuel products and GL accounts
  └── Reporting
        └── [All FMS reports]
```

### Demonstration

**Trainer:** Log in as supervisor. Navigate to Forecourt → Operations → Shifts. Show the list of past shifts — point out the status column (Draft, Open, Closing, Closed). Open a closed shift and walk through the tabs:
- Header (date, label, supervisor, timestamps)
- Meter Readings tab
- Tank Dips tab
- Cash Drops tab

Point out the status bar at the top: **Draft → Open → Closing → Closed**. Explain that once a shift moves to Closed, nothing can be edited.

### Exercise

> **Trainee task:** Navigate to Forecourt → Operations → Shifts. Open any closed shift. Find: (1) the shift date, (2) the supervisor name, (3) the total cash meter sales figure, (4) one nozzle's closing volume reading. Write them down.

---

## Part 3 — User Roles

### Concept

FMS has three roles. Each role controls what a user can see and do.

| Role | Who | What they can do |
|---|---|---|
| **Attendant** | Forecourt attendant | View their own shifts, enter their cash readings if given access |
| **Supervisor** | Shift supervisor | Open shifts, enter readings, close shifts, print reports |
| **Accountant** | Finance team | View GL entries, run financial reports, manage credit customers |

The role is set by the system administrator under Settings → Users. A supervisor can also have Accountant role if needed.

> **Key rule:** Only a Supervisor can open and close a shift. An attendant cannot close a shift even if they know the password.

### Exercise

> **Trainee task:** In Odoo, go to Settings → Users (trainer assists). Look at your own user record. Identify which FMS groups you belong to. Confirm you have the Supervisor role before proceeding.

---

## Part 4 — Before the First Shift: Configuration Checklist

### Concept

Before FMS can run, a manager must configure it once. Supervisors do not normally do this, but they need to understand it so they can report problems correctly.

The configuration lives in Forecourt → Configuration → Site Preferences.

**Critical settings:**

| Setting | What it does | What goes wrong if missing |
|---|---|---|
| FMS Sales Journal | Which accounting journal to post shift sales entries into | Shift close fails: "GL Config gate failed" |
| Cash Clearing Account | Which GL account is debited for total cash sales | Same as above |
| Fuel Revenue Account (per product) | Which income account is credited for each fuel product | Same as above |
| Fuel COGS Account (per product) | Which cost account is used for residual allocation | Same as above |
| Meniscus % | Maximum allowed tank dip variance | If too tight: every shift fails Gate 5. If too loose: losses go undetected |
| Require POS Reconciliation | Whether shifts must be linked to POS sessions to close | If True and no POS: shift cannot close |

**Pump/Nozzle configuration:**

Each physical pump is configured in Forecourt → Configuration → Station Setup.

Each nozzle has:
- **Product** — which fuel it dispenses
- **Current Elec Cash (KES)** — current meter totalizer (carried forward automatically after first shift)
- **Current Elec Volume (L)** — current volume totalizer
- **Current Manual Meter (L)** — mechanical counter

The "current" values become the opening readings of the next shift. After the first shift closes, the system updates these automatically from the closing readings.

### Exercise

> **Trainee task:** Go to Forecourt → Configuration → Station Setup. Count the number of active pumps. For each pump, note how many nozzles it has and which fuel each nozzle dispenses. Draw a simple diagram of the station layout (pump name → nozzle labels → fuel products).

---

## Part 5 — Opening a Shift

### Concept

A shift starts when the supervisor clicks **Open Shift**. Before clicking, the supervisor must set:
- **Shift Date** — today's date
- **Shift Label** — which period (1_day, 2_evening, 3_night — configured in Site Preferences)
- **Supervisor** — their own name

When the supervisor clicks Open Shift, the system:
1. Checks that no other shift is currently Open or Closing for the same date and label (one active shift per period).
2. Fetches opening meter readings from the previous shift's closing logs (`fms.meter_log`). If this is the first shift ever, it reads from the nozzle's "Current" values.
3. Fetches opening dip readings from the previous shift's closing dip logs (`fms.dip_log`).
4. Creates one row in the Meter Readings tab per active nozzle.
5. Creates one row in the Tank Dips tab per active fuel tank.
6. Runs `_sync_attendant_cash_lines()` — creates one row in the Attendant Cash section per attendant assigned to a nozzle in this shift.

**The supervisor does not enter opening values** — they are auto-filled. If they look wrong, the supervisor must NOT change them to fix the current shift — they must report to the manager, who will investigate the previous shift's closing logs.

### Common Opening Problems

| Problem | What you see | Fix |
|---|---|---|
| "Another shift already open" | Error dialog on Open Shift | Find and close/cancel the blocking shift |
| Opening readings are zero | All opening values = 0 | This is the very first shift — verify physical readings match the nozzle "Current" values in Station Setup |
| Wrong opening readings | Opening values don't match pump display | Do NOT change in this shift — report to manager. Previous shift's closing logs need investigation |
| Missing nozzle row | A pump nozzle has no row in Meter Readings | The nozzle is not marked "Active" — manager must enable it in Station Setup |

### Demonstration

**Trainer:** Create a new shift. Set date, label, supervisor. Click Open Shift. Show how the meter reading rows appear with opening values pre-filled. Point out that opening columns are greyed out (read-only).

### Exercise

> **Trainee task:** Create a new shift for today (use a test label if a real shift is already open). Click Open Shift. Verify: (1) opening meter values appeared automatically, (2) opening dip values appeared automatically, (3) you cannot edit the opening values. Take a screenshot.

---

## Part 6 — Entering Closing Meter Readings

### Concept

At the end of the shift, the supervisor reads three values from each pump nozzle's physical display and enters them into FMS.

**The three meter types:**

| Column name | Meter type | Read from |
|---|---|---|
| Closing Elec Cash (KES) | Electronic cash totalizer | Digital display on pump, cumulative KES total |
| Closing Elec Vol (L) | Electronic volume totalizer | Digital display, cumulative litres total |
| Closing Manual (L) | Mechanical odometer | Physical spinning counter on pump body |

All three are **cumulative lifetime totals** — they never reset to zero. The system calculates "sold this shift" by subtracting the opening reading from the closing reading.

**RTT (Return to Tank):**

If any fuel was pumped back into the tank during this shift (e.g. from a nozzle that was mis-calibrated or during tank cleaning), enter the litres in the RTT column. This is rare but important — unrecorded RTT creates phantom shortages.

**Computed automatically (do not enter these):**

| Column | Formula | What it means |
|---|---|---|
| Cash Sold (KES) | Closing Cash − Opening Cash | Money recorded by the pump this shift |
| Vol Sold Elec (L) | Closing Vol − Opening Vol − RTT | Fuel dispensed by this nozzle this shift |
| Vol Sold Manual (L) | Closing Manual − Opening Manual | Same, via mechanical counter |

The system cross-checks Elec Volume vs Manual Volume. If they differ by more than 1 litre per nozzle (Gate G1), the shift blocks on close. This catches misreads.

The system also cross-checks Elec Cash vs (Elec Volume × price). If they differ by more than the configured threshold (default 5L equivalent), the shift blocks on close (Gate G2). This catches price entry errors.

### Reading the Physical Pump Display

**Trainer note:** Do a physical walk-out to the pump forecourt with the trainee. Show them where to find each meter on the specific pump model at this station. Take photos and paste them into this section for your station.

> **[Insert station-specific pump display photos here]**

### Common Entry Errors

| Error | What happens | Fix |
|---|---|---|
| Copied opening value into closing | Vol Sold = 0 | Correct the closing value |
| Transposed digits (e.g. 124,850 entered as 124,580) | Implausible sold volume | Verify against pump display, correct |
| Forgot RTT | Volume variance at dip check | Enter litres in RTT column |
| Entered litres in KES column | Gate G2 fails | Clear the wrong value, re-enter in correct column |

### Exercise

> **Trainee task:** On the open test shift, enter fictional closing readings. Use these values:
> - Closing Elec Cash: opening value + 45,000
> - Closing Elec Vol: opening value + 200
> - Closing Manual: opening value + 199
> - RTT: 0
>
> Verify the computed "Cash Sold" = 45,000 and "Vol Sold Elec" = 200. Note: Cash ÷ Vol = 225 per litre — this is the price FMS will use for the cross-check. Does this match the configured price in Site Preferences?

---

## Part 7 — Entering Tank Dip Readings

### Concept

A tank dip is a physical measurement of how much fuel is in the underground tank right now.

The supervisor uses a calibrated dipstick (or electronic gauge) and measures the depth of fuel in the tank. Using the tank's calibration chart, this depth converts to litres.

FMS only needs **one number per tank per shift close: the closing dip volume in litres.** The opening volume is auto-filled from the previous shift.

### What FMS Does With the Dip

```
Variance (L) = Opening Dip − Closing Dip − Meter Litres Sold from this tank's product

Variance % = |Variance| / Closing Dip × 100
```

If variance % is within the configured Meniscus % (default 0.5%), the dip column goes green. If it is above 0.5% but below 2%, it goes yellow. Above 2%, it goes red and the shift cannot close (Gate 5).

**Example:**

```
Opening dip:        18,500 L
Closing dip:        17,648 L
Meter sold:            850 L

Expected closing:   18,500 − 850 = 17,650 L
Actual closing:     17,648 L
Variance:           17,648 − 17,650 = −2 L (within 18,500 L tank, this is 0.01% — well within 0.5%)
```

### Why the Dip Might Not Match

| Cause | Typical variance | Action |
|---|---|---|
| Normal temperature/meniscus reading error | < 0.2% | Acceptable — close the shift |
| Misread dipstick | Can be large | Re-measure, correct |
| Fuel delivery received during shift not recorded | Large positive | Record the delivery, then re-measure |
| Evaporation or calibration drift | 0.2–0.5% | Monitor over weeks — report if persistent |
| Meter calibration fault | Consistent across shifts | Escalate to engineering |
| Leak | Growing over time | Immediate EPRA reporting obligation |

### Demonstration

**Trainer:** On the test shift, show the Tank Dips tab. Explain opening volume (read-only, auto-filled). Enter a closing dip and show the Variance column update in real-time.

### Exercise

> **Trainee task:** Enter closing dip readings on the test shift. Use: Opening value − (volume that should match the meter you entered in Part 6). See if the variance turns green. Then enter a deliberately wrong dip that would cause a red variance. Describe what you see.

---

## Part 8 — Cash Drops

### Concept

During a shift, attendants drop cash into the station safe. This is called a **cash drop**. FMS records each drop individually.

**Why individual drops matter:**
- The safe balance at any point in the shift is known
- If an attendant drops multiple times (morning and afternoon), each is timestamped
- The total drops per attendant become their "Cash Collected" figure in the reconciliation

Cash drops live on the **Cash Drops tab** of the shift. Each row has:

| Field | What to enter |
|---|---|
| Attendant | Which attendant made this drop |
| Amount (KES) | How much cash they dropped |
| Time | When they dropped it (default: now) |
| Note | Optional note (e.g. "morning drop", "shift end collection") |

The total of all drops per attendant automatically flows into the Attendant Cash reconciliation — the supervisor does not need to enter it separately.

### Who Enters Cash Drops

Normally the supervisor enters cash drops as they happen — when an attendant brings cash to the booth. Some stations enter them all at the end of the shift. Both work, but real-time entry is better practice because it keeps the safe balance traceable.

### Exercise

> **Trainee task:** On the test shift, navigate to the Cash Drops tab. Enter two drops for one attendant (e.g. 5,000 and 8,000). Enter one drop for a second attendant (e.g. 12,000). Save. Then navigate to confirm: does the system show these amounts in the right place in the attendant reconciliation?

---

## Part 9 — Starting the Close Process

### Concept

When the last pump transaction is done for the shift, the supervisor clicks **Start Closing**.

This is a one-way action. Once clicked:
- Meter readings and dip readings are **locked** — they cannot be edited.
- The timestamp and user who started closing are recorded permanently.
- The residual allocation algorithm runs.
- Attendant cash rows are created (if Auto-sync is enabled).

**If you click Start Closing and then find an error in the meter readings**, a system administrator must reset the shift back to Open state. This is not a routine operation — it requires a reason to be documented. So: **verify all meter and dip readings before clicking Start Closing.**

### Pre-Closing Checklist (do this before clicking)

- [ ] All nozzle closing readings entered (Elec Cash, Elec Vol, Manual)
- [ ] RTT entered where applicable
- [ ] All tank dip closing volumes entered
- [ ] Dip variance columns are green (or yellow — investigate if yellow)
- [ ] No nozzle row is showing zero for "Cash Sold" unless that nozzle truly had no sales
- [ ] You have the authority (Supervisor role) to proceed

### Exercise

> **Trainee task:** On the test shift, run through the pre-closing checklist above. Confirm each item. Then click Start Closing. Observe: what locks, what stays editable, what new information appears?

---

## Part 10 — The Attendant Cash Reconciliation

### Concept

This is the most important part of the shift close. It answers: **does the money match the fuel sold?**

After clicking Start Closing, you will see an Attendant Cash section. Each attendant who operated a nozzle this shift has one row. The row shows:

| Column | Source | Editable? |
|---|---|---|
| Attendant | From Meter Readings assignment | No |
| Reported Sales (KES) | Sum of their nozzles' Elec Cash Sold | No (computed) |
| Cash Dropped (KES) | Sum of their Cash Drops from the Cash Drops tab | No (computed from drops) |
| MPesa (KES) | From linked POS session | No |
| Card (KES) | From linked POS session | No |
| AR / Credit (KES) | From linked POS session (credit customers) | No |
| Expenses (KES) | From vendor bills linked to this shift and attendant | No |
| Balance (KES) | Reported Sales − (Cash Dropped + MPesa + Card + AR + Expenses) | No (computed) |

**Every Balance must equal exactly zero** for the shift to close.

### The Balance Formula

```
Balance = Reported Sales − Cash Dropped − MPesa − Card − AR − Expenses

Must equal: 0.00
```

**Positive balance** means the pump says the attendant collected more money than has been accounted for. The attendant still owes money.

**Negative balance** means more has been accounted for than the pump recorded. Could be: attendant was given cash float at start of shift, received a payment for a prior credit sale, or there is a data entry error.

### What To Do When Balance Is Not Zero

**Most common scenario — positive balance (attendant owes):**

The attendant forgot to drop some cash, or dropped cash that wasn't recorded.
- Check the Cash Drops tab — is any drop missing?
- Ask the attendant to hand in outstanding cash.
- Add a cash drop record for the outstanding amount.

**Attendant collected a credit customer payment during the shift:**
- This cash is already in the safe.
- Record it as a payment against the customer's invoice in Accounting → Customer → Payments.
- Link the payment to this shift.
- The Expenses/receipts section will update.

**Attendant paid a vendor from shift cash (e.g. bought cleaning supplies):**
- Raise a vendor bill in Accounting → Vendors → Bills.
- On the bill, set Shift = this shift, Attendant = this attendant.
- The Expenses column updates automatically.

**Negative balance (system owes attendant) — most common cause: cash float given at shift start:**
- Record the float as an incoming payment linked to this shift in Accounting → Customers → Payments (using the float payment context).
- Balance adjusts.

**Unresolvable after 30 minutes of investigation:**
- Document in the shift Notes tab with full detail.
- Post a manual journal entry in Accounting → Journal Entries to force the balance to zero via the discrepancy account (700002).
- Do NOT leave a shift open overnight trying to resolve it — the next shift's opening readings will be wrong.

### Exercise

> **Trainee task:** On the test shift, look at the Attendant Cash section. If balances are zero, artificially create an imbalance by changing a cash drop amount. Observe the balance go non-zero. Understand which direction (positive/negative) the change causes. Then restore the original value so balance = 0. Explain to the trainer: what does it mean if an attendant's balance is KES +2,000?

---

## Part 11 — Closing the Shift

### Concept

When all balances are zero and the dip variances are acceptable, the supervisor clicks **Close Shift**.

The system runs a sequence of gate checks. All must pass. If any fails, a detailed error message describes exactly what is wrong and how to fix it.

### The Gate Sequence

| Gate | What is checked | What "failing" looks like |
|---|---|---|
| GL Config | All fuel products have revenue and COGS accounts wired | "GL Config gate failed: Diesel has no revenue account" |
| Supervisor | A supervisor is assigned to the shift | "Supervisor is required before closing" |
| G1 Meter Elec vs Manual | For each nozzle, |Elec Vol − Manual Vol| ≤ 1L | "Nozzle P1-A: Elec=850L, Manual=847L, Diff=3L" |
| G2 Meter Elec vs Cash | For each nozzle, Elec Cash ≈ Elec Vol × price | "P1-A: Elec=850L, Cash implied=1046L" |
| G3 Volume Reconciliation | Meter total volume ≈ POS total volume | Skipped if Require POS Reconciliation = False |
| G4 Cash Reconciliation | Meter cash total ≈ POS cash total | Skipped if Require POS Reconciliation = False |
| G5 Attendant Balances | Every attendant balance = 0 | "Ali Hassan: KES +3,850" |
| G6 FC Cash | Sum of all attendant balances = 0 | Clears automatically when G5 passes |
| G7 Stock Variance | Each tank dip variance ≤ meniscus % | "Diesel Tank 1: 0.8% exceeds 0.5% meniscus" |

**No "close anyway" button exists.** Every gate must pass. This is intentional — it prevents losses from being hidden.

### What Happens on Successful Close

In a single operation (either all succeed or none):
1. **Meter logs written** — permanent, immutable record of opening, closing, RTT, net sold per nozzle.
2. **Dip logs written** — permanent, immutable record of opening and closing per tank.
3. **Sales GL entry posted** — DR clearing account, CR revenue per product.
4. **Residual allocation GL entries posted** — one per reallocation line.
5. Shift moves to **Closed** state.
6. Each nozzle's current meter values advance to the closing values — ready for next shift.
7. Next shift auto-created if configured.

### After Close — Print Reports

Always print the shift report before leaving:

- **Print Shift Report** — full reconciliation. File physically and scan to manager.
- **Print Meter Movement** — nozzle-by-nozzle summary. Give to incoming supervisor.
- **Print Attendant Shift Statement** — one per attendant. Give to each person as their receipt.

### Exercise

> **Trainee task:** Attempt to close the test shift. If any gates fail, read the error message carefully, identify which gate failed, and fix it using the guidance above. Try again. Once closed, print the Shift Report and identify: (1) the GL entry reference number, (2) total cash sold, (3) which attendant had the highest sales.

---

## Part 12 — Reading the Shift Report

### Concept

The printed shift report is the official record of the shift. It contains everything needed for a handover and for the accountant's review.

**Sections of the report:**

**Header:** Shift number, date, label, supervisor name, opening and closing timestamps.

**Meter Readings Summary:** For each nozzle — pump name, nozzle label, fuel product, opening readings (all three meters), closing readings, RTT, net sold litres, net sold KES.

**Tank Dip Summary:** For each tank — opening volume, closing volume, variance litres, variance %, status (within/outside meniscus).

**Attendant Cash Summary:** For each attendant — reported sales, cash dropped, MPesa, card, AR, expenses, balance. Confirms all zeros.

**Residual Allocations (if any):** Source product, target product, litres reallocated, KES value.

**GL Entry Reference:** The journal entry number (e.g. FCST/2026/00001) that was posted to the GL on close.

**How to read the variance column:**
- Green: within acceptable meniscus — no action needed.
- Yellow: between meniscus and 2× meniscus — monitor, no immediate action.
- Red: exceeds 2× meniscus — would have blocked close (if it appears on a printed closed-shift report, an override was used — investigate).

### Exercise

> **Trainee task:** Using a printed or on-screen shift report from a closed shift, answer:
> 1. What was the total fuel sold in litres across all products?
> 2. Which product had the highest KES sales?
> 3. Was any residual allocation made? If yes, between which products?
> 4. What was the GL entry number?
> 5. Were all tank variances within meniscus?

---

## Part 13 — Common Situations and How to Handle Them

### Situation 1: Pump Nozzle Broke Mid-Shift

If a nozzle stops working mid-shift, the closing reading is whatever it was when it stopped.

- Enter the last valid closing reading from the pump display.
- Add a note in the nozzle row: "Nozzle fault — stopped at 14:30."
- Enter the closing dip as normal for the tank.
- The sold volume will be less than a normal shift — this is correct.
- Report the fault to engineering immediately.
- Do NOT leave the nozzle row blank — the system will treat it as zero sales which may not be correct.

### Situation 2: Fuel Delivery During the Shift

A tanker delivers fuel during the shift. This affects the dip.

**Problem:** If you record the closing dip after the delivery, it will include the delivered fuel. The dip variance will show a positive figure (more fuel than the meter sold, because more came in).

**Fix:**
- Record the delivery in Accounting → Inventory → Receipts (stock receipt).
- The FMS dip variance calculation automatically accounts for confirmed stock receipts to each tank during the shift period.
- Alternatively: take the dip just before the delivery. Record that as the closing dip for this tank. The delivery then opens fresh for the next shift.
- Always note in the shift Notes: "Delivery received from Vivo Energy, 10,000L Diesel at 14:15."

### Situation 3: Attendant Goes Home Before Shift Closes

Sometimes an attendant finishes their work and leaves before the supervisor closes the shift.

- The attendant must drop their cash **before leaving**.
- The supervisor records the cash drop at the time it was made.
- The shift can still close — the attendant does not need to be present for close.
- If the attendant forgot to drop cash: call them. They must return or arrange for the cash to be brought. Do not close with an unresolved balance.

### Situation 4: Power Cut During Shift

If power is cut and the pump meters go dark, the meters retain their readings when power returns. Odoo itself requires power to the server.

- Do not enter closing readings until pumps are back and readable.
- If the power cut was very long and the physical meter display is uncertain, use the mechanical manual meter as backup.
- In extreme cases (complete pump failure), estimate based on dip readings only and note this clearly in the shift.

### Situation 5: Wrong Opening Readings at Shift Start

If you open a shift and the opening meter values are clearly wrong (e.g. zeros when the pump display shows 127,000L):

- Do NOT enter readings against wrong openings.
- Click the shift and look for the Notes field — enter a note: "Opening readings appear incorrect — see previous shift FMS/2026/0XXX."
- Contact the manager immediately.
- The manager will investigate the previous shift's meter_log and correct the nozzle "Current" values if needed.
- Do NOT try to work around this by entering the correct opening value manually — the opening value is computed and read-only by design.

---

## Part 14 — End-of-Day Handover

### Concept

At the end of the day (after the last shift closes), the incoming supervisor (or night supervisor) receives a formal handover.

**The physical handover:**
1. Outgoing supervisor hands the incoming supervisor the **Meter Movement Report** for the last shift.
2. Incoming supervisor visually confirms the pump display readings match the "closing" values on the report.
3. Both supervisors sign the printed report.
4. Outgoing supervisor hands over the safe. Both count the cash together and note the safe balance.

**Why both must verify:**
- If there is a discrepancy between the physical pump display and the printed closing readings, it means either a data entry error was made or the pump meter changed after the reading was taken. This needs immediate investigation — it could indicate a pump being operated off the books.

**After handover:**
- The incoming supervisor opens the next shift (if auto-open is not enabled).
- They verify the new opening readings match the previous closing readings exactly.
- If they don't match, they flag it before any fuel is sold.

### Exercise

> **Trainee task (role play with trainer):** Trainer plays outgoing supervisor, trainee plays incoming supervisor. Print the Meter Movement report. Walk to the (imaginary) pump. "Read" the pump display. Confirm the numbers match. Sign the report. Now the trainee opens the next shift in the system. Verify opening readings match.

---

## Assessment — Can the Trainee Close a Shift Independently?

Before signing off the trainee as competent, they must complete this assessment without assistance:

1. Create a new shift with correct date and label.
2. Open the shift.
3. Enter fictional but internally consistent closing meter readings for all nozzles.
4. Enter tank dip readings that produce variance < 0.5%.
5. Enter cash drops for all attendants such that the balances will be zero.
6. Click Start Closing.
7. Click Close Shift (all gates must pass on first try).
8. Print the Shift Report and identify: total fuel sold, total KES sales, GL entry reference.

**Pass criteria:** Shift closes on first attempt with all gates green. Trainee can explain what each gate is checking without looking at notes.

**If the trainee fails any gate:** Walk through the specific error with them. Allow one additional attempt. If they fail again, schedule a follow-up day.

---

## Quick Reference Card (Print and Post at Supervisor Station)

```
SHIFT CLOSE SEQUENCE
─────────────────────────────────────────────────────
1. Read all pump meters (Elec Cash, Elec Vol, Manual Vol)
2. Enter in FMS: Meter Readings tab
3. Dip all tanks, enter in FMS: Tank Dips tab
4. Record all cash drops: Cash Drops tab
5. Click START CLOSING (locks meter + dip readings)
6. Verify all attendant balances = 0
   └─ If not zero: check cash drops, add missing entries
7. Click CLOSE SHIFT (runs all gates)
   └─ If gate fails: read the error, fix, retry
8. Print Shift Report + Meter Movement Report
9. Hand over to incoming supervisor with signed report

GATE ERRORS — QUICK FIXES
─────────────────────────────────────────────────────
GL Config failed   → Manager must wire revenue/COGS accounts on products
Elec vs Manual     → Recheck both closing readings from pump display
Elec vs Cash       → Recheck Elec Cash from pump display; check product price
Attendant balance  → Check Cash Drops; add missing drop entry
Dip variance       → Re-measure tank; check for unrecorded delivery

CONTACTS
─────────────────────────────────────────────────────
System Admin  : ___________________________
Manager       : ___________________________
Accounting    : ___________________________
Engineering   : ___________________________
```
