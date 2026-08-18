"""
fms_setup_check.py — GL account configuration validator.

Accessible via Forecourt → Configuration → GL Account Setup Check.
Also called automatically before shift close to surface issues early.
"""

from odoo import api, fields, models


# ── Module-level helpers (also called from post_init_hook) ────────────────────

def fms_fix_product_accounts(env, company=None):
    """Set fms_revenue_account_id + fms_cogs_account_id on fuel products missing them.
    Returns list of product names that were updated."""
    company = company or env.company
    prefs = env['fms.site.preferences'].get_for_company(company)
    revenue_acc = prefs.default_revenue_account_id
    cogs_acc    = prefs.default_cogs_account_id
    if not revenue_acc and not cogs_acc:
        return []
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
    return fixed


def fms_create_opening_equity(env, company=None):
    """Create DR Bank / CR 301000-Capital opening balance entry if none exists yet."""
    company = company or env.company
    existing = env['account.move'].search([
        ('ref', 'ilike', 'Opening Balance'),
        ('move_type', '=', 'entry'),
        ('state', '=', 'posted'),
        ('company_id', '=', company.id),
    ], limit=1)
    if existing:
        return f"Opening balance entry already exists: {existing.ref} ({existing.name})"

    capital_acc = env['account.account'].search(
        [('code', '=', '301000'), ('company_ids', 'in', company.id)], limit=1
    )
    bank_acc = env['account.account'].search(
        [('code', '=', '101401'), ('company_ids', 'in', company.id)], limit=1
    )
    gen_journal = env['account.journal'].search([
        ('type', '=', 'general'),
        ('company_id', '=', company.id),
        ('name', 'not ilike', 'Exchange'),
        ('name', 'not ilike', 'Cash Basis'),
        ('name', 'not ilike', 'Inventory'),
        ('name', 'not ilike', 'Point of Sale'),
    ], limit=1)

    if not capital_acc or not bank_acc or not gen_journal:
        return "Could not find required accounts (301000, 101401) or a general journal."

    opening_amount = 500_000.0
    move = env['account.move'].create({
        'move_type': 'entry',
        'journal_id': gen_journal.id,
        'date': fields.Date.from_string('2026-01-01'),
        'ref': 'Opening Balance — Station Capital',
        'company_id': company.id,
        'line_ids': [
            (0, 0, {
                'account_id': bank_acc.id,
                'name': 'Opening — Cash at bank',
                'debit': opening_amount,
                'credit': 0.0,
            }),
            (0, 0, {
                'account_id': capital_acc.id,
                'name': 'Opening — Owner paid-in capital',
                'debit': 0.0,
                'credit': opening_amount,
            }),
        ],
    })
    move.action_post()
    return f"Created opening equity entry {move.name} — KES {opening_amount:,.2f} capital"


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

    def action_fix_product_accounts(self):
        """Auto-assign revenue + COGS accounts from site prefs to all fuel products missing them."""
        fixed = fms_fix_product_accounts(self.env, self.company_id)
        # Refresh the check
        new_check = self.env['fms.setup.check'].run_check(self.company_id)
        return {
            'type': 'ir.actions.act_window',
            'name': 'GL Account Setup Check',
            'res_model': 'fms.setup.check',
            'res_id': new_check.id,
            'view_mode': 'form',
            'view_id': self.env.ref('fms.view_fms_setup_check_form').id,
            'target': 'new',
            'context': {'fixed_count': len(fixed), 'fixed_names': ', '.join(fixed)},
        }

    def action_create_opening_equity(self):
        """Create DR Bank / CR 301000-Capital opening balance entry if none exists."""
        msg = fms_create_opening_equity(self.env, self.company_id)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Opening Balance',
                'message': msg,
                'type': 'success' if 'Created' in msg else 'warning',
                'sticky': False,
            },
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
                'error',
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
