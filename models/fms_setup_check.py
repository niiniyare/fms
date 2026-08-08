"""
fms_setup_check.py — GL account configuration validator.

Accessible via Forecourt → Configuration → GL Account Setup Check.
Also called automatically before shift close to surface issues early.
"""

from odoo import api, fields, models


class FMSSetupCheck(models.TransientModel):
    _name = 'fms.setup.check'
    _description = 'FMS GL Account Setup Check'

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, readonly=True,
    )
    issue_ids = fields.One2many('fms.setup.check.issue', 'check_id', 'Issues')
    issue_count = fields.Integer(compute='_compute_counts')
    error_count = fields.Integer(compute='_compute_counts')
    warning_count = fields.Integer(compute='_compute_counts')
    ok = fields.Boolean(compute='_compute_counts')

    @api.depends('issue_ids')
    def _compute_counts(self):
        for rec in self:
            errors   = rec.issue_ids.filtered(lambda i: i.level == 'error')
            warnings = rec.issue_ids.filtered(lambda i: i.level == 'warning')
            rec.error_count   = len(errors)
            rec.warning_count = len(warnings)
            rec.issue_count   = len(rec.issue_ids)
            rec.ok            = not errors

    # ------------------------------------------------------------------
    # Public API — called from shift close and from the menu wizard
    # ------------------------------------------------------------------

    @api.model
    def run_check(self, company=None):
        """Run all checks and return a new fms.setup.check record."""
        company = company or self.env.company
        rec = self.create({'company_id': company.id})
        issues = []
        issues += rec._check_site_preferences()
        issues += rec._check_fuel_products()
        issues += rec._check_journals()
        for issue in issues:
            issue['check_id'] = rec.id
        self.env['fms.setup.check.issue'].create(issues)
        return rec

    def action_open_site_prefs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Site Preferences',
            'res_model': 'fms.site.preferences',
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_products(self):
        fuel_ids = self.env['product.product'].search(
            [('fms_is_fuel', '=', True)]
        ).ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fuel Products',
            'res_model': 'product.product',
            'domain': [('id', 'in', fuel_ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_site_preferences(self):
        issues = []
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if not prefs:
            issues.append(self._issue(
                'error',
                'No Site Preferences found for this company.',
                'Go to Forecourt → Configuration → Site Preferences and create one.',
            ))
            return issues

        if not prefs.clearing_account_id:
            issues.append(self._issue(
                'error',
                'Site Preferences: Cash Clearing Account is not set.',
                'Set a current asset account (e.g. 101600 — FMS Cash Clearing). '
                'Without this, the shift close will post to an AR account, '
                'causing revenue accounts to appear on both sides of the P&L.',
            ))

        if not prefs.sales_journal_id:
            issues.append(self._issue(
                'warning',
                'Site Preferences: Forecourt Sales Journal is not set.',
                'Set the sales journal to use for shift GL entries. '
                'FMS will auto-detect a journal named "forecourt" if left blank.',
            ))

        if not prefs.default_revenue_account_id:
            issues.append(self._issue(
                'warning',
                'Site Preferences: Default Fuel Revenue Account is not set.',
                'New fuel products will have no revenue account pre-filled.',
            ))

        if not prefs.default_cogs_account_id:
            issues.append(self._issue(
                'warning',
                'Site Preferences: Default Fuel COGS Account is not set.',
                'New fuel products will have no COGS account pre-filled.',
            ))

        return issues

    def _check_fuel_products(self):
        issues = []
        products = self.env['product.product'].search([
            ('fms_is_fuel', '=', True),
            ('active', '=', True),
        ])
        if not products:
            issues.append(self._issue(
                'warning',
                'No active fuel products found (fms_is_fuel = True).',
                'Mark at least one product as fuel in its FMS settings tab.',
            ))
            return issues

        no_revenue = products.filtered(lambda p: not p.fms_revenue_account_id)
        no_cogs    = products.filtered(lambda p: not p.fms_cogs_account_id)

        for p in no_revenue:
            issues.append(self._issue(
                'error',
                f'Fuel product "{p.name}" has no Revenue Account (fms_revenue_account_id).',
                'Open the product → FMS tab → set Fuel Revenue Account. '
                'Without this, shift close skips this product in the GL entry.',
            ))

        for p in no_cogs:
            issues.append(self._issue(
                'warning',
                f'Fuel product "{p.name}" has no COGS Account (fms_cogs_account_id).',
                'Open the product → FMS tab → set Fuel COGS Account. '
                'Residual allocation journals cannot post without this.',
            ))

        # Detect revenue account = clearing account (the bug from the reports)
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs and prefs.clearing_account_id:
            wrong = products.filtered(
                lambda p: p.fms_revenue_account_id == prefs.clearing_account_id
            )
            for p in wrong:
                issues.append(self._issue(
                    'error',
                    f'Fuel product "{p.name}": Revenue Account is the same as the '
                    f'Cash Clearing Account ({prefs.clearing_account_id.code}).',
                    'This causes both DR and CR to hit the same account, making '
                    'the P&L show sales as both income and expense. '
                    'Set the Revenue Account to an income account (e.g. 400000).',
                ))

        return issues

    def _check_journals(self):
        issues = []
        # Warn if no sale-type journal exists at all
        sale_journals = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ])
        if not sale_journals:
            issues.append(self._issue(
                'error',
                'No sale-type journal found for this company.',
                'Create a Sales journal in Accounting → Configuration → Journals.',
            ))
        return issues

    @staticmethod
    def _issue(level, title, detail):
        return {'level': level, 'title': title, 'detail': detail}


class FMSSetupCheckIssue(models.TransientModel):
    _name = 'fms.setup.check.issue'
    _description = 'FMS Setup Check Issue'
    _order = 'level, title'

    check_id = fields.Many2one('fms.setup.check', required=True, ondelete='cascade')
    level = fields.Selection([('error', 'Error'), ('warning', 'Warning')], required=True)
    title = fields.Char(required=True)
    detail = fields.Text()
