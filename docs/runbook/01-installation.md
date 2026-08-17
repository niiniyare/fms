# 01 — Installation

Audience: System Administrator

---

## Prerequisites

| Requirement | Version |
|---|---|
| Odoo | 18.0 Community or Enterprise |
| Python | 3.10 – 3.12 (match Odoo venv) |
| PostgreSQL | 14 – 16 |
| RAM | 2 GB min, 4 GB recommended |
| wkhtmltopdf | 0.12.6 (for PDF reports) |

Required Odoo modules (declared in manifest; auto-installed as dependencies):
`base`, `mail`, `account`, `stock`, `point_of_sale`, `hr`

---

## 1. Copy Modules

```bash
# Place both modules in your addons path
cp -r /path/to/fms         /opt/odoo/custom-addons/fms
cp -r /path/to/fms_accounting  /opt/odoo/custom-addons/fms_accounting
```

Directory names must stay `fms` and `fms_accounting` — they are technical module names.

---

## 2. Add to Addons Path

In `odoo.conf`:
```ini
[options]
addons_path = /opt/odoo/odoo/addons,/opt/odoo/custom-addons
```

---

## 3. Create Database

```bash
createdb -U odoo fms_prod
python odoo-bin -d fms_prod -i fms,fms_accounting \
    --db_host=localhost --db_user=odoo --db_password=secret \
    --stop-after-init
```

This installs both modules and runs the `post_init_hook` which creates the default FMS journal.

---

## 4. Kenya Locale (KES)

After install, in Odoo UI:
1. Settings → Companies → select company.
2. Set **Country** to Kenya.
3. Set **Currency** to KES (Kenyan Shilling).
4. Settings → Technical → Languages → install Swahili if needed.

Or via seed script (development environments):
```bash
make odoo-e2e-create   # create DB + install modules
make odoo-e2e-seed     # seed company, CoA, products
```

---

## 5. Verify Install

```
Forecourt menu must appear in top nav.
Settings → Technical → Sequences → search "FMS" → two sequences must exist:
  fms.shift (FMS/YYYY/NNNN)
  fms.incident
```

---

## Upgrade (existing install)

```bash
python odoo-bin -d fms_prod -u fms,fms_accounting --stop-after-init
```

Always back up the database before upgrading:
```bash
pg_dump fms_prod > fms_prod_backup_$(date +%Y%m%d).sql
```
