# 06 — Administration

Audience: Accountant / System Administrator

---

## Price Changes

When pump price changes:

1. **Forecourt → Configuration → Shift Definitions & Prices → New**
2. Set **Product**, **Start Date**, **Price per Litre (KES)**.
3. Save.

Simultaneously update the product price in POS:
**Point of Sale → Products → [Fuel Product] → Sales Price**

Both must match or Gate 2 will fail on the next shift close.

---

## Adding a New Pump / Nozzle

1. **Forecourt → Configuration → Station Setup → New**
2. Fill in pump details, add nozzle rows with current meter totalizer values (read from the physical pump display).
3. Save.

The new nozzle appears in Meter Readings tab on the next shift that is opened after saving.

---

## Adding a New Fuel Tank

1. **Inventory → Configuration → Locations → New**
2. Set **Location Type** to Internal.
3. Enable **Is Fuel Tank**.
4. Set **Fuel Product**.
5. Save.

Appears in Tank Dips tab on the next opened shift.

---

## User Management

**Settings → Users & Companies → Users → New**

Assign one FMS group:

| Group | Odoo path |
|---|---|
| `fms.group_fms_attendant` | Forecourt / Attendant |
| `fms.group_fms_supervisor` | Forecourt / Supervisor |
| `fms.group_fms_accountant` | Forecourt / Accountant |

Groups are hierarchical: Accountant includes Supervisor permissions; Supervisor includes Attendant permissions.

---

## Correcting a Closed Shift (Accountant)

Closed shifts cannot be edited. Meter and dip logs are immutable.

For GL corrections: post a manual journal entry in **Accounting → Journal Entries → New** referencing the shift number in the narration. Link to the relevant accounts (revenue, COGS, clearing).

For stock corrections: **Inventory → Operations → Physical Inventory** — adjust the affected product/location.

---

## Backup

```bash
# Database backup
pg_dump fms_prod > /backups/fms_prod_$(date +%Y%m%d_%H%M).sql

# Filestore backup (attachments, report templates)
tar czf /backups/fms_filestore_$(date +%Y%m%d).tar.gz ~/.local/share/Odoo/filestore/fms_prod/
```

Automate with cron, run before any upgrade.

---

## Module Upgrade

```bash
# Backup first
pg_dump fms_prod > /backups/pre_upgrade_$(date +%Y%m%d).sql

# Upgrade
python odoo-bin -d fms_prod -u fms,fms_accounting --stop-after-init
```

---

## Development Database (E2E)

```bash
make odoo-e2e-create   # create fms_e2e with modules installed
make odoo-e2e-seed     # seed Kenya CoA + all Anika products
make odoo-e2e-update   # update fms + fms_accounting in fms_e2e after code changes
make odoo-e2e          # start Odoo on port 8070 pointing at fms_e2e
make odoo-e2e-drop     # drop fms_e2e
```

After any code change, run `make odoo-e2e-update` before `make odoo-e2e` — the server does not hot-reload module XML/Python changes without an upgrade.

Seed script: `scripts/seed_e2e.py` — creates Anika Global Limited company, 143 accounts, 145 products (fuel, LPG, lubricants, filters, spare parts) with opening stock.
