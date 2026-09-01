# FMS UAT Checklist

**Version:** 1.0  
**Module:** FMS (Forecourt Management System) for Odoo 18  
**Sign-off required from:** Station Supervisor + Accountant  

---

## Pre-UAT Setup

- [ ] FMS module installed on test instance (`make odoo-upgrade` or via Apps menu)
- [ ] fms_accounting module installed
- [ ] Site preferences configured (Forecourt > Configuration > Site Preferences)
  - [ ] Sales journal set
  - [ ] Clearing account set
  - [ ] Dip variance meniscus set (default 1000 L)
- [ ] Fuel products created with `Track Inventory = True`, revenue + COGS accounts set
- [ ] Pumps and nozzles created
- [ ] Tank locations created with `Is Fuel Tank = True`
- [ ] At least 2 attendants created with `Is Attendant = True`
- [ ] Supervisor user exists with `FMS Supervisor` group

---

## UAT-1: Normal Shift Close (No Residuals)

**Scenario:** Day shift, two pumps, diesel + super, clean close.

- [ ] Create new shift (Forecourt > Active Shift > New)
- [ ] Set date, label (1. Day), supervisor
- [ ] Click **Open Shift** — state changes to Open
- [ ] Enter closing meter readings for all nozzles
- [ ] Enter closing dip readings for all tanks
- [ ] No attendant cash (or all set to zero)
- [ ] Click **Start Closing** — state changes to Closing
- [ ] Click **Close Shift** — state changes to Closed
- [ ] Verify: meter logs created (Reporting > Meter Movement Log)
- [ ] Verify: dip logs created (Reporting > Tank Dip Log)
- [ ] Verify: sales journal entry posted (Sales GL Entry link visible on shift)
- [ ] Verify: GL entry is balanced (DR = CR)

**Expected result:** Shift closes cleanly, GL posted, no errors.

---

## UAT-2: Residual Allocation (Lumped Non-Fuel Sales)

**Scenario:** Attendant reports diesel sales that include carwash. System detects residual and auto-allocates.

- [ ] Open a new shift
- [ ] Enter meter readings: diesel meter shows lower volume than cash suggests (attendant lumped carwash into diesel)
- [ ] Add Non Fuel Sales line: carwash, service type, enter amount
- [ ] Click **Start Closing**
- [ ] Verify: residual allocation lines appear (visible on shift after closing trigger)
- [ ] Click **Close Shift**
- [ ] Verify: residual journal entry posted (separate from sales journal)
- [ ] Verify: diesel COGS debited, carwash COGS credited for the allocated amount

**Expected result:** Residual auto-allocated, two journal entries posted.

---

## UAT-3: Gate 4 — FC Cash Variance Blocks Close

**Scenario:** Attendant has unresolved cash variance.

- [ ] Open a new shift
- [ ] Add cash drop for attendant via Floats / Drops tab
- [ ] Do NOT post a corresponding receipt or invoice (create variance deliberately)
- [ ] Click **Start Closing** — FC Cash Variance wizard should appear
- [ ] Choose resolution (write-off or defer)
- [ ] Verify shift moves to Closing only after resolution
- [ ] Close shift
- [ ] Verify: FC Variance field = 0 on closed shift

**Expected result:** Gate 4 blocks close until FC Cash variance = 0.

---

## UAT-4: Gate 5 — Dip Variance Blocks Close

**Scenario:** Tank dip reading shows variance exceeding the meniscus.

- [ ] Open a new shift
- [ ] Enter a closing dip with a large variance (e.g., closing = opening × 0.98 on a 20,000 L tank = 400 L variance, exceeding 1000 L threshold only if tank > 100,000 L — or adjust meniscus to 50 L in Site Preferences for test)
- [ ] Click **Start Closing**, then **Close Shift**
- [ ] Verify: ValidationError raised with "GATE 5 FAILED" and tank name
- [ ] Investigate dip reading, correct it
- [ ] Close successfully

**Expected result:** Gate 5 blocks close, names the specific tank.

---

## UAT-5: Sequential Shifts — Opening Reads from Previous Closing

**Scenario:** Second shift auto-fetches closing readings from first shift.

- [ ] Close first shift (UAT-1 result)
- [ ] Create second shift for the same day or next day
- [ ] Click **Open Shift**
- [ ] Verify: meter entries for all nozzles are pre-populated with previous shift's closing readings as opening readings
- [ ] Verify: dip entries are pre-populated with previous shift's closing volumes

**Expected result:** No manual re-entry of previous readings required.

---

## UAT-6: Non-Fuel Sales Tab

**Scenario:** Goods and service lines behave differently.

- [ ] Open a shift, go to Non Fuel Sales tab
- [ ] Add a **Goods** line (e.g., motor oil): opening/closing/qty fields visible, amount field hidden
- [ ] Add a **Service** line (e.g., carwash): amount field visible, qty/price fields hidden
- [ ] Verify totals update in header KPI bar
- [ ] Verify Non Fuel Sales total is included in Total Sales

**Expected result:** Correct fields shown per line type, totals correct.

---

## UAT-7: Reports Print Correctly

- [ ] Open any closed shift
- [ ] Click **Print Shift Report** — PDF opens with meter readings, dip section, KPI tiles
- [ ] Click **FC Cash Recon Report** — PDF shows per-attendant reconciliation
- [ ] Click **Sales Register** — PDF shows transaction list
- [ ] Click **Attendant Statements** — PDF with one page per attendant
- [ ] Click **Print Meter Movement** — PDF shows nozzle-level data
- [ ] Verify no `&nbsp;` or XML errors in browser console

**Expected result:** All 5 reports render without errors.

---

## UAT-8: Security — Non-Supervisor Cannot Close

- [ ] Log in as a user with only `FMS Attendant` group (not Supervisor)
- [ ] Verify: **Close Shift** button not visible on shift form
- [ ] Verify: Cannot edit closed shift fields
- [ ] Log back in as Supervisor to confirm buttons visible

**Expected result:** Attendant cannot close a shift.

---

## UAT-9: Dashboard / Overview

- [ ] Navigate to Forecourt > Overview
- [ ] Verify: KPI stat buttons show (Current Shift, Yesterday Sales, etc.)
- [ ] Verify: Alert banner shows when there are overdue shifts or open incidents
- [ ] Verify: All Clear banner shows when no action items

**Expected result:** Overview loads cleanly with accurate data.

---

## Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Station Supervisor | | | |
| Accountant | | | |
| IT / System Admin | | | |

---

*All UAT scenarios must pass before production go-live.*
