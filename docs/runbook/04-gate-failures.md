# 04 — Gate Failures

Audience: Shift Supervisor
Gates block shift close until the supervisor resolves the issue. No override exists.

---

## Gate 1 — Volume Reconciliation Gap

**Error:** `Gate 1 failed: meter volume differs from POS volume by X L (tolerance Y L)`

Pump meters recorded more or fewer litres than POS captured.

**Common causes:**
- A POS session from this shift is not linked. Go to Attendant Cash tab → Linked POS Sessions, add it.
- Meter closing reading entered incorrectly. Correct in Meter Readings tab (only possible before Start Closing — if already in Closing state, contact sysadmin to reset).
- RTT volume not recorded. Enter litres in the RTT (L) column on Meter Readings tab.

**Fix:** Correct data → click **Refresh Sales Summary** → retry **Close Shift**.

---

## Gate 2 — Cash Reconciliation Gap

**Error:** `Gate 2 failed: cash meter differs from POS revenue by KES X (tolerance 100 KES)`

Electronic cash totalizer on pumps differs from POS recorded revenue by more than 100 KES.

**Common causes:**
- Missing POS session (same fix as Gate 1).
- Pump price differs from POS product price — e.g. a price change was applied on one but not the other.
- Transaction completed on pump but voided or not captured in POS.

**Fix:**
1. Link any missing POS sessions.
2. If gap is a genuine price mismatch: post a manual correction journal entry in Accounting → Journal Entries, confirm gap falls within tolerance, retry Close Shift.
3. If gap is unexplained: document in shift Notes tab, post a correction journal entry, investigate with attendant.

---

## Gate 3 — Attendant Balance Not Zero

**Error:** `Gate 3 failed: attendant [Name] balance is KES X`

**Positive balance** — attendant collected more than declared (system shows they owe money).
**Negative balance** — more was declared than the meter recorded.

**Resolution by situation:**

| Situation | Action |
|---|---|
| Attendant forgot to include some cash | Increase Cash Dropped in their row |
| Attendant made an error in MPesa recording | Correct in POS, re-link POS session |
| Proven petty cash expense during shift | Raise vendor bill in Accounting linked to this shift (auto-populates Expenses) |
| Overpayment to attendant for change | Reduce Cash Dropped accordingly |
| Unresolvable (theft investigation) | Post a correction journal entry in Accounting, adjust Cash Dropped to balance, document in Notes |

---

## Gate 4 — FC Cash Balance Not Zero

**Error:** `Gate 4 failed: FC Cash balance is KES X`

FC Cash is the aggregate of all attendant balances. If Gate 3 is resolved (all individual balances = 0), Gate 4 clears automatically. No separate action needed.

---

## Gate 5 — Dip Variance Too High

**Error:** `Gate 5 failed: tank [Name] variance X% exceeds meniscus Y%`

Formula: `variance% = |opening − closing − meter_sold| / closing × 100`

**Common causes:**
- Dip reading was misread or entered incorrectly. Re-measure the tank, correct in Tank Dips tab (only before Start Closing — see note below).
- Delivery received during this shift was not recorded. Post a stock receipt in Inventory → Receipts for the delivered volume, then re-measure and correct closing dip.
- Genuine wetstock loss (leakage, evaporation, meter calibration drift). Requires EPRA investigation.

**Fix options:**
1. Correct the dip if data entry error (requires sysadmin to reset to Draft state if already in Closing).
2. Post missing stock receipt, re-enter closing dip.
3. If variance is confirmed and investigated: post a stock adjustment in Inventory → Physical Inventory, document in shift Notes.

**Change the meniscus threshold permanently:**
Forecourt → Configuration → Site Preferences → Variance Meniscus (%).

---

## Resetting Shift State (Sysadmin Only)

If meter/dip data needs correction after Start Closing:

```bash
python odoo-bin shell -d fms_prod
```
```python
shift = env['fms.shift'].browse(SHIFT_ID)
shift.write({'state': 'open'})
env.cr.commit()
```

**Warning:** This re-opens editing. Meter and dip logs are NOT yet written at this point (they write on Close Shift), so no audit trail is broken. Document the reset and reason in the shift Notes before re-closing.
