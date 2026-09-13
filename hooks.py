"""
hooks.py — Odoo module lifecycle hooks for FMS.

post_init_hook runs after install/update and fixes any existing data:
  - Wires GL accounts onto fuel products missing them
  - Idempotent: safe to run multiple times
"""

import logging
_logger = logging.getLogger(__name__)


def post_init_hook(env):
    from odoo.addons.fms.models.fms_setup_check import fms_fix_product_accounts
    fixed = fms_fix_product_accounts(env)
    if fixed:
        _logger.info("FMS post_init: set GL accounts on products: %s", ', '.join(fixed))
    else:
        _logger.info("FMS post_init: all fuel products already have GL accounts.")

    # Backfill company_id on fms.pump records that predate the multi-company field.
    # Assigns existing pumps to the first company in the database. For multi-company
    # installations the operator should reassign pumps to the correct company afterwards.
    env.cr.execute("""
        UPDATE fms_pump
        SET company_id = (SELECT id FROM res_company ORDER BY id LIMIT 1)
        WHERE company_id IS NULL
    """)
    backfilled = env.cr.rowcount
    if backfilled:
        _logger.info("FMS post_init: backfilled company_id on %d pump(s).", backfilled)
