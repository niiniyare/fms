"""
fms_pos_session.py — POS session close enforcement for FMS fuel revenue integrity.

FMS is the authoritative revenue owner for fuel products. When a POS session
closes, Odoo calls _create_account_move which credits the product's income account
for each sale. If fuel products use a revenue-type income account, POS will post
fuel revenue independently — duplicating the revenue that FMS will also post on
shift close.

Enforcement: block pos.session.action_pos_session_close if fuel products in this
session are configured with a revenue-type income account.

Error code: E610

Reference: FMS_Complete_Specification_Technical_Guide.md §7.1, §8.1
"""

import logging
from odoo import models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _get_fuel_revenue_conflicts(session):
    """
    Return a list of human-readable conflict strings for fuel products in this
    POS session that would post revenue through POS (duplicating FMS revenue).

    A conflict exists when:
      - product.fms_is_fuel = True
      - product._get_product_accounts()['income'].account_type in ('income', 'income_other')

    Returns empty list if no conflicts.
    """
    conflicts = []
    fuel_products = (
        session.order_ids
        .mapped('lines.product_id')
        .filtered(lambda p: p.fms_is_fuel)
    )
    if not fuel_products:
        return conflicts

    for product in fuel_products:
        try:
            income_account = product.with_company(session.company_id)._get_product_accounts().get('income')
        except Exception:
            income_account = None

        if not income_account:
            continue

        if income_account.account_type in ('income', 'income_other'):
            conflicts.append(
                f"  • {product.name}\n"
                f"    Income account: {income_account.name} (type={income_account.account_type})\n"
                f"    Action: Set this product's income account to the FMS Cash Clearing account."
            )

    return conflicts


class FMSPOSSession(models.Model):
    """
    Inherit pos.session to enforce FMS fuel revenue ownership at POS close.

    FMS owns fuel revenue. POS must not independently recognize fuel revenue
    by posting to a revenue-type account when a session closes.
    """

    _inherit = 'pos.session'

    def action_pos_session_close(self, balancing_account=False, amount_to_balance=0,
                                 bank_payment_method_diffs=None):
        for session in self:
            session._fms_validate_fuel_revenue_config()
        return super().action_pos_session_close(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )

    def _fms_validate_fuel_revenue_config(self):
        """
        [E610] Block POS session close when FMS fuel products would post revenue.

        FMS is the authoritative revenue owner for fuel. A POS session that contains
        FMS fuel sales must NOT credit a revenue-type account on close. The fuel
        product's income account must be a clearing/transit account.

        Raises UserError with structured error code [E610] if conflicts found.
        """
        self.ensure_one()
        conflicts = _get_fuel_revenue_conflicts(self)
        if not conflicts:
            return

        conflict_text = '\n'.join(conflicts)
        raise UserError(
            "[E610] POS Fuel Accounting Configuration Invalid\n\n"
            "This POS session contains FMS fuel products configured to post revenue\n"
            "independently. FMS owns fuel revenue and will post it at shift close.\n\n"
            "Affected products:\n"
            f"{conflict_text}\n\n"
            "Required fix:\n"
            "  For each fuel product above, go to:\n"
            "    Product → Accounting → Income Account\n"
            "  and set it to the FMS Cash Clearing account (an asset_current account).\n\n"
            "  POS will then post fuel payments to clearing, and FMS shift close will\n"
            "  post the authoritative fuel revenue exactly once.\n\n"
            "  Do NOT close this POS session until the configuration is corrected."
        )
