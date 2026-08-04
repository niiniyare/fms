"""
fms_site_preferences.py — Company-level configuration for FMS

One record per company.  Accessed via Forecourt → Configuration → Site Preferences.
"""

from odoo import models, fields, api


class FMSSitePreferences(models.Model):
    _name = 'fms.site.preferences'
    _description = 'FMS Site Preferences'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', 'Company', required=True, ondelete='cascade',
        default=lambda self: self.env.company,
    )

    # ── Gate 3: Dip variance meniscus ────────────────────────────────────────
    meniscus_pct = fields.Float(
        'Variance Meniscus (%)', default=0.5, digits=(5, 2),
        help="Maximum allowed tank dip variance as a percentage of closing volume. "
             "Default: 0.5%. Shifts cannot close if any tank exceeds this.",
    )

    # ── Shift labels ──────────────────────────────────────────────────────────
    shift_label_1 = fields.Char('Shift 1 Label', default='1_day')
    shift_label_2 = fields.Char('Shift 2 Label', default='2_evening')
    shift_label_3 = fields.Char('Shift 3 Label', default='3_night')

    # ── GL accounts (defaults for new products) ───────────────────────────────
    default_revenue_account_id = fields.Many2one(
        'account.account', 'Default Fuel Revenue Account',
        domain=[('account_type', 'in', ('income', 'income_other'))],
        help="Pre-filled on new fuel products created at this station.",
    )
    default_cogs_account_id = fields.Many2one(
        'account.account', 'Default Fuel COGS Account',
        domain=[('account_type', 'in', ('expense', 'expense_direct_cost'))],
        help="Pre-filled on new fuel products created at this station.",
    )
    clearing_account_id = fields.Many2one(
        'account.account', 'Cash Clearing Account',
        domain=[('account_type', '=', 'asset_receivable')],
        help="Debited on shift close for total cash sales (before banking). "
             "Must contain 'clearing' in its name if left blank (auto-detected).",
    )
    sales_journal_id = fields.Many2one(
        'account.journal', 'Forecourt Sales Journal',
        domain=[('type', '=', 'sale')],
        help="Journal used for shift sales entries. "
             "Auto-detected from journals named 'forecourt' if left blank.",
    )

    # ── Operational ───────────────────────────────────────────────────────────
    auto_sync_attendants = fields.Boolean(
        'Auto-sync Attendant Cash Lines', default=True,
        help="Automatically create attendant cash lines when Start Closing is clicked.",
    )

    _sql_constraints = [
        ('company_unique', 'UNIQUE(company_id)',
         'Only one set of site preferences is allowed per company.'),
    ]

    @api.model
    def get_for_company(self, company=None):
        """Return (or create) the preferences record for the given company."""
        company = company or self.env.company
        prefs = self.search([('company_id', '=', company.id)], limit=1)
        if not prefs:
            prefs = self.create({'company_id': company.id})
        return prefs
