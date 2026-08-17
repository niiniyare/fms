# 07 — Troubleshooting

Audience: Supervisor / System Administrator

---

## Shift Issues

### "Meter readings were wrong on this shift — opening values are off"

Opening readings come from the nozzle's stored current meter positions (set when the previous shift closed).

Fix:
1. Do not close this shift yet.
2. **Forecourt → Configuration → Pumps** → open the affected nozzle.
3. Correct **Current Elec Cash**, **Current Elec Volume**, or **Current Manual Meter**.
4. Delete this shift's meter entry rows for that nozzle.
5. Click **Open Shift** again — system regenerates meter rows with corrected values.

---

### "A nozzle totalizer was reset to zero (nozzle replaced)"

1. **Forecourt → Configuration → Pumps** → open the nozzle.
2. Set all current meter fields to the new (reset) values from the physical display.
3. The next shift opened picks them up as opening readings.
4. Document the reset in that shift's Notes tab.

---

### "Can I edit readings after clicking Start Closing?"

No. Meter and dip entries are locked in Closing state. To unlock, a sysadmin must reset state via shell:

```bash
python odoo-bin shell -d fms_prod
shift = env['fms.shift'].browse(SHIFT_ID)
shift.write({'state': 'open'})
env.cr.commit()
```

---

### "Two supervisors edited the shift simultaneously and data was overwritten"

Odoo ORM handles concurrent saves via record locking. If both saved at the exact same time, the last write wins on individual fields. Recommendation: only one supervisor enters closing readings per shift. Use Notes tab to coordinate.

---

### "Recalculate Residuals button is not visible"

Button is visible only in **Closing** state to users with Supervisor role. If shift is still in Open state, first click **Start Closing**.

---

## Installation / Server Issues

### "FMS menu does not appear after install"

1. Check the module is installed: **Settings → Apps → search "FMS"** — status must be **Installed**.
2. Reload browser (Ctrl+F5).
3. Check user has at least `fms.group_fms_attendant` group.
4. Check Odoo logs for install errors:
   ```bash
   tail -200 /var/log/odoo/odoo.log | grep -E "ERROR|fms"
   ```

---

### "PDF reports error: IndexError: list index out of range"

wkhtmltopdf is missing or wrong version.

```bash
wkhtmltopdf --version   # must be 0.12.6
which wkhtmltopdf       # must be on PATH
```

Install: https://wkhtmltopdf.org/downloads.html

---

### "cannot change data type of view column ... from bigint to integer"

SQL view type conflict — occurs when upgrading after a view column type changed.

Fix: drop and recreate the view manually, then upgrade:
```bash
psql -d fms_prod -c "DROP VIEW IF EXISTS fms_report_attendant_perf CASCADE;"
python odoo-bin -d fms_prod -u fms --stop-after-init
```

---

### "External ID not found: fms.action_fms_overview_server"

XML load order issue. Occurs if an older version of the module is installed.

Fix:
```bash
python odoo-bin -d fms_prod -u fms --stop-after-init
```

If persists, check `__manifest__.py` load order: `fms_menu_structure.xml` must be first, `fms_overview_views.xml` and `fms_menus.xml` must be last in the `data` list.

---

### "Invalid field account.account.company_id"

Odoo 18 changed `account.account` to use `company_ids` (Many2many) instead of `company_id`. Any custom scripts that search by `company_id` on `account.account` need updating:

```python
# Old (Odoo 17 and earlier)
AccountAccount.search([('company_id', '=', company.id)])

# New (Odoo 18)
AccountAccount.search([('company_ids', 'in', [company.id])])
```

---

## GL / Accounting Issues

### "Shift closed but no journal entry was created"

Common causes:
1. No fuel products have `fms_revenue_account_id` set. Set it on each fuel product's FMS tab.
2. FMS Journal is not set in Site Preferences.
3. Python error during posting — check Odoo logs:
   ```bash
   grep -A 10 "Error posting sales journal" /var/log/odoo/odoo.log
   ```

---

### "Residual allocation posted but amounts look wrong"

1. Check price periods — if no price period covers the shift date, allocation uses 0 as the unit price.
2. Check that residual allocation rules are configured in **Forecourt → Configuration → Site Preferences → Residual Allocation**.

---

## Audit Trail

All closed shifts write to:
- `fms.meter_log` — immutable meter readings per nozzle
- `fms.dip_log` — immutable dip readings per tank

These records raise a `ValidationError` if any write or delete is attempted. Do not bypass via SQL — this breaks EPRA audit compliance.

View logs:
- **Forecourt → Compliance → Meter Logs**
- **Forecourt → Wetstock → Dip Logs**

GL entries: **Accounting → Journal Entries** → filter journal = FMS Shifts.
