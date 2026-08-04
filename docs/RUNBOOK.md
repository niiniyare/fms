# FMS Operations Runbook

Daily procedures for operating FMS (Forecourt Management System).

## Table of Contents
1. Opening Shift
2. During Shift
3. Closing Shift
4. Troubleshooting
5. Contact & Support

## Opening Shift

### Prerequisites
- Odoo instance running
- FMS module installed
- User logged in (supervisor or attendant role)

### Steps

1. Navigate to: **Forecourt → Shifts**
2. Click **Create** (new shift)
3. Fill in:
   - **Shift Date:** Today's date
   - **Shift Label:** Select (1_day, 2_evening, 3_night)
   - **Supervisor:** Select supervisor
4. Click **Save**
5. Click **Open Shift** (button)
   - System auto-populates opening meter/dip readings
6. Verify opening values are correct
7. Click **Save**

### What Happens
- Status changes: Draft → Open
- System fetches previous shift's closing readings
- Entry forms become editable
- Attendants can enter sales data

---

## During Shift

### Attendant Tasks

1. Enter meter readings (after each nozzle close or at shift end):
   - Navigate to opened shift
   - Scroll to "Pump Meters" section
   - For each pump:
     - Select pump (auto-filled)
     - Enter **Closing Elec Volume** (from pump display)
     - Enter **Closing Man Mech** (manual reading, if applicable)
   - System auto-calculates: Qty Sold, Amount

2. Enter dip readings (at shift end, usually):
   - Scroll to "Tank Dips" section
   - For each tank:
     - Select tank (auto-filled)
     - Enter **Closing Volume** (from dip stick)
     - System shows variance vs. opening
   
3. Track cash:
   - Note cash dropped to safe
   - Note AR (receivables) created
   - Note card/MPesa transfers
   - Note expenses paid from till

### Supervisor Tasks

- Monitor shift progress (optional)
- Review reconciliation (before close)
- Address discrepancies (if any)

---

## Closing Shift

### Prerequisites
- All meter/dip readings entered
- All cash/AR recorded
- No outstanding issues

### Steps

1. Click **Reconciliation** (read-only section)
   - System shows:
     - FC Cash balance (must = 0)
     - Stock variances (must be < meniscus)
     - Attendant balances (all must = 0)
     - Residual allocations (if any)

2. Review results:
   - If all shows ✅: proceed to step 3
   - If any ❌: investigate & fix before closing

3. Click **Close Shift** (button)
   - System performs hard gate checks:
     - FC Cash = 0 (exactly)?
     - All attendants clear?
     - Variances < meniscus?
   
4. If gates pass:
   - Logs written (meter_log, dip_log)
   - Journals posted (GL)
   - Status changes: Closing → Closed
   - Success message shown

5. If gates fail:
   - Error message shows which gate failed
   - Example: "FC Cash is +50 KES. Cannot close."
   - Supervisor must post adjustment, retry

### What Happens After Close
- Meter/dip logs locked (immutable)
- GL journals posted (sales, residuals, variance)
- Stock adjustments recorded
- Shift marked "Closed"
- Cannot be re-opened

---

## Troubleshooting

### "FC Cash Not Zero"

**Symptom:** Close button shows error: "FC Cash is ±X KES. Cannot close."

**Cause:** Total money in doesn't equal total money out.

**Solution:**
1. Check attendant cash reconciliation:
   - Navigate: Shift → Attendant Cash section
   - For each attendant, verify:
     - Sales + Receipts = Cash + AR + Card + Expenses + Balance
2. If one attendant is short/over:
   - Supervisor investigates
   - Posts adjustment entry (DR AR/Expense | CR FC Cash)
3. Retry close

**Example:**
```
Attendant John:
  In:  Sales 5000 + Receipts 0 = 5000
  Out: Cash 4950 + AR 0 + Card 0 + Expenses 0 = 4950
  Balance: -50 KES (SHORT)

Fix:
  Supervisor posts: DR Employee AR 50 | CR FC Cash 50
  Now balance = 0 ✅
```

---

### "Stock Variance Exceeds Meniscus"

**Symptom:** Close button shows error: "Tank T1: variance 2.00% exceeds meniscus 0.50%"

**Cause:** Tank volume loss/gain exceeds acceptable threshold.

**Solution:**
1. Re-dip the tank (physical recount)
2. Update dip reading with new value
3. Verify new variance is < meniscus
4. Retry close

**Example:**
```
Tank T1 (10,000L capacity):
  Opening: 10,000L
  Closing (first dip): 9,800L
  Variance: 200L (2.0%) → EXCEEDS 0.5% meniscus ❌

  Re-dip: 9,950L
  New Variance: 50L (0.5%) → OK ✅
```

---

### "Attendant Not Cleared"

**Symptom:** Close button shows error: "Attendant Sarah: balance -100.00 KES not cleared."

**Cause:** One attendant's cash doesn't balance.

**Solution:**
1. Locate attendant in Attendant Cash section
2. Check: Sales + Receipts vs. Cash + AR + Card + Expenses
3. Possible causes:
   - Cash short-changed a customer (enters AR instead)
   - Forgot to record a cash drop
   - Forgot to record an expense
4. Attendant explains or Supervisor posts correction
5. Retry close

---

### "Residual Allocation Unexpected"

**Symptom:** Reconciliation shows allocation: "Diesel -100L → Carwash +100L"

**Cause:** Attendant reported non-fuel sales under wrong category.

**Solution (Informational):**
- System detected: Carwash was lumped into Diesel reporting
- Auto-allocated: Moved 100L (worth 22,280 KES) from Diesel to Carwash
- GL posted automatically
- No action needed (expected behavior)

---

## Pre-Go-Live Production Checklist

Run through these checks before going live at a new station.

### System Configuration
- [ ] Odoo 18 Community installed, FMS module installed and upgraded
- [ ] Company/currency set correctly (KES)
- [ ] At least one Sale journal exists (type=sale)
- [ ] At least one Receivable account with "clearing" in the name
- [ ] Fuel products created with `fms_is_fuel = True`
- [ ] Fuel products have `fms_revenue_account_id` and `fms_cogs_account_id` set
- [ ] Pumps created with nozzles linked to fuel products
- [ ] Tanks created (`fms_is_fuel_tank = True`) linked to fuel products
- [ ] Employees created; supervisors added to `Forecourt Management / Shift Supervisor` group
- [ ] Attendants created with `fms_is_attendant = True`

### UAT Acceptance Scenarios

Run these manually before going live:

**Scenario 1 – Normal shift close:**
1. Create shift, click Open Shift
2. Enter closing meter readings (e.g., diesel +500L)
3. Enter closing dip reading (variance < 0.5%)
4. Add attendant cash line with cash_collected = 0
5. Click Start Closing → Close Shift
6. Confirm: state = Closed, meter/dip logs created

**Scenario 2 – Gate 1 block and resolution:**
1. Open a shift, start closing
2. Add attendant cash line with cash_collected = 5,000 (no POS sales → balance = -5,000)
3. Attempt Close Shift → must see "GATE 1 FAILED" error
4. Set cash_collected = 0, retry Close Shift → must succeed

**Scenario 3 – Gate 3 block and resolution:**
1. Open a shift, add dip entry with 10,000L opening, 9,700L closing (3% variance)
2. Start closing, attempt Close Shift → must see "GATE 3 FAILED" error
3. Update dip to 9,950L (0.5% variance), retry → must succeed

**Scenario 4 – Print shift report:**
1. With a closing/closed shift, click Print Report
2. PDF must render with meter readings, dip readings, attendant cash, and gate summary

**Scenario 5 – Sequential shifts:**
1. Close shift 1 with diesel meter at 1000L
2. Open shift 2 the next day
3. Confirm shift 2 opens with diesel opening = 1000L (carried over)

### Go/No-Go Criteria
- All 5 UAT scenarios pass manually
- All automated tests pass: `make odoo-test`
- No JS errors in browser console (F12) during shift workflow
- Shift close time < 5 minutes (end-to-end)
- Report renders without errors (wkhtmltopdf installed)

---

## Contact & Support

- **Technical Issues:** Check logs (Odoo admin panel)
- **Spec Reference:** FMS_Complete_Specification_Technical_Guide.md
- **Development:** See dev-guide.py in scripts/

---

**Last Updated:** 2026-08-04  
**Version:** 1.0 (Phase 1 MVP)
