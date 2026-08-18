"""
test_common.py — Shared test helpers for FMS test suite.

FMSGLMixin.setup_fms_gl() wires journal + clearing + revenue + COGS accounts
into fms.site.preferences so shift close doesn't fail the GL config gate.
"""


class FMSGLMixin:
    """Mixin — call self.setup_fms_gl() in setUp to avoid missing-journal errors."""

    def setup_fms_gl(self, company=None):
        company = company or self.env.company

        journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not journal:
            journal = self.env['account.journal'].create({
                'name': 'FMS Test Sales Journal',
                'code': 'FMSTJ',
                'type': 'sale',
                'company_id': company.id,
            })

        clearing = self.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
            ('company_ids', 'in', company.id),
        ], limit=1)
        if not clearing:
            clearing = self.env['account.account'].create({
                'name': 'FMS Test Clearing',
                'code': 'FMS9099',
                'account_type': 'asset_current',
                'company_ids': [(4, company.id)],
            })

        self.fms_revenue_account = self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_ids', 'in', company.id),
        ], limit=1)
        if not self.fms_revenue_account:
            self.fms_revenue_account = self.env['account.account'].create({
                'name': 'FMS Test Revenue',
                'code': 'FMS9098',
                'account_type': 'income',
                'company_ids': [(4, company.id)],
            })

        self.fms_cogs_account = self.env['account.account'].search([
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
            ('company_ids', 'in', company.id),
        ], limit=1)
        if not self.fms_cogs_account:
            self.fms_cogs_account = self.env['account.account'].create({
                'name': 'FMS Test COGS',
                'code': 'FMS9097',
                'account_type': 'expense',
                'company_ids': [(4, company.id)],
            })

        prefs = self.env['fms.site.preferences'].get_for_company(company)
        prefs.write({
            'sales_journal_id': journal.id,
            'clearing_account_id': clearing.id,
        })

        # Wire revenue + COGS on any existing fuel products missing them
        fuel_products = self.env['product.product'].search([('fms_is_fuel', '=', True)])
        for p in fuel_products:
            vals = {}
            if not p.fms_revenue_account_id:
                vals['fms_revenue_account_id'] = self.fms_revenue_account.id
            if not p.fms_cogs_account_id:
                vals['fms_cogs_account_id'] = self.fms_cogs_account.id
            if vals:
                p.write(vals)

        return journal, clearing, prefs

    def wire_product_accounts(self, *products):
        """Set revenue + COGS accounts on fuel products (required for GL config gate)."""
        for product in products:
            if product.fms_is_fuel:
                product.write({
                    'fms_revenue_account_id': self.fms_revenue_account.id,
                    'fms_cogs_account_id': self.fms_cogs_account.id,
                })
