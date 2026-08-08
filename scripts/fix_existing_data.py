"""
fix_existing_data.py — One-time DB fix script for FMS.

Run via:  make odoo-shell < scripts/fix_existing_data.py
      or: python scripts/fix_existing_data.py  (with ODOO env active)

What it does:
  1. Wires fms_revenue_account_id + fms_cogs_account_id on all fuel products
     that are currently missing those accounts.
  2. Creates an opening equity journal entry (DR Bank / CR 301000 Capital)
     if no opening balance entry exists yet.
"""

import sys
import odoo
from odoo import api, fields, SUPERUSER_ID

DB = 'test_fms'
OPENING_CAPITAL_KES = 500_000.00   # adjust to actual station capital
OPENING_DATE = '2026-01-01'

odoo.tools.config['db_name'] = DB
registry = odoo.registry(DB)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})

    prefs       = env['fms.site.preferences'].get_for_company(env.company)
    revenue_acc = prefs.default_revenue_account_id
    cogs_acc    = prefs.default_cogs_account_id

    # ── 1. Fix fuel product accounts ─────────────────────────────────────────
    products = env['product.product'].search([('fms_is_fuel', '=', True)])
    fixed = []
    for p in products:
        vals = {}
        if not p.fms_revenue_account_id and revenue_acc:
            vals['fms_revenue_account_id'] = revenue_acc.id
        if not p.fms_cogs_account_id and cogs_acc:
            vals['fms_cogs_account_id'] = cogs_acc.id
        if vals:
            p.write(vals)
            fixed.append(p.name)

    if fixed:
        print(f"[OK] Fixed product GL accounts: {', '.join(fixed)}")
    else:
        print("[OK] All fuel products already have GL accounts configured.")

    # ── 2. Opening equity entry ───────────────────────────────────────────────
    existing_opening = env['account.move'].search([
        ('ref', 'ilike', 'Opening Balance'),
        ('state', '=', 'posted'),
    ], limit=1)

    if existing_opening:
        print(f"[SKIP] Opening balance entry already exists: {existing_opening.ref}")
    else:
        capital_acc = env['account.account'].search([('code', '=', '301000')], limit=1)
        bank_acc    = env['account.account'].search([('code', '=', '101401')], limit=1)
        gen_journal = env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', env.company.id),
            ('name', 'not ilike', 'Exchange'),
            ('name', 'not ilike', 'Cash Basis'),
        ], limit=1)

        if not capital_acc or not bank_acc or not gen_journal:
            print("[WARN] Missing accounts/journal for opening entry — skipping.")
            print(f"       capital={capital_acc}, bank={bank_acc}, journal={gen_journal}")
        else:
            move = env['account.move'].create({
                'move_type': 'entry',
                'journal_id': gen_journal.id,
                'date': fields.Date.from_string(OPENING_DATE),
                'ref': 'Opening Balance — Station Capital',
                'line_ids': [
                    (0, 0, {
                        'account_id': bank_acc.id,
                        'name': 'Opening — Cash at bank',
                        'debit': OPENING_CAPITAL_KES,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': capital_acc.id,
                        'name': 'Opening — Owner paid-in capital',
                        'debit': 0.0,
                        'credit': OPENING_CAPITAL_KES,
                    }),
                ],
            })
            move.action_post()
            print(f"[OK] Created opening equity entry: {move.name} | KES {OPENING_CAPITAL_KES:,.2f}")

    cr.commit()
    print("\nDone.")
