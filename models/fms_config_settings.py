from odoo import models, fields, api


class FMSConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Gate thresholds ───────────────────────────────────────────────────────
    fms_meniscus_pct = fields.Float(
        'Dip Variance Meniscus (%)',
        config_parameter='fms.meniscus_pct',
        default=0.5,
    )
    fms_elec_vs_cash_threshold_l = fields.Float(
        'Elec vs Cash Threshold (L)',
        config_parameter='fms.elec_vs_cash_threshold_l',
        default=5.0,
    )

    # ── Shift schedule ────────────────────────────────────────────────────────
    fms_shift_duration_hrs = fields.Selection([
        ('8',  '8 hours  — 3 shifts/day'),
        ('12', '12 hours — 2 shifts/day'),
        ('24', '24 hours — 1 shift/day'),
    ], string='Shift Duration', config_parameter='fms.shift_duration_hrs', default='8')

    # ── POS / gate behaviour ──────────────────────────────────────────────────
    fms_require_pos_reconciliation = fields.Boolean(
        'Require POS Reconciliation',
        config_parameter='fms.require_pos_reconciliation',
        default=True,
    )
    fms_auto_open_next_shift = fields.Boolean(
        'Auto-open Next Shift on Close',
        config_parameter='fms.auto_open_next_shift',
        default=True,
    )
    fms_auto_sync_attendants = fields.Boolean(
        'Auto-sync Attendant Lines on Closing',
        config_parameter='fms.auto_sync_attendants',
        default=True,
    )
    fms_allow_multiple_disputed = fields.Boolean(
        'Allow Multiple Disputed Shifts',
        config_parameter='fms.allow_multiple_disputed',
        default=False,
    )

    # ── Attendant mode ────────────────────────────────────────────────────────
    fms_attendant_assignment_mode = fields.Selection([
        ('per_nozzle',   'Per Nozzle'),
        ('pre_assigned', 'Pre-Assigned'),
    ], string='Attendant Assignment', config_parameter='fms.attendant_assignment_mode',
        default='per_nozzle')

    # ── GL / journals (stored on fms.site.preferences, not ir.config_parameter)
    # These proxy through to the site prefs record for the current company.
    fms_prefs_id = fields.Many2one(
        'fms.site.preferences', compute='_compute_fms_prefs', store=False)

    fms_sales_journal_id = fields.Many2one(
        'account.journal', 'Forecourt Sales Journal',
        domain=[('type', '=', 'sale')],
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)
    fms_clearing_account_id = fields.Many2one(
        'account.account', 'Cash Clearing Account',
        domain=[('account_type', '=', 'asset_receivable')],
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)
    fms_default_revenue_account_id = fields.Many2one(
        'account.account', 'Default Fuel Revenue Account',
        domain=[('account_type', 'in', ('income', 'income_other'))],
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)
    fms_default_cogs_account_id = fields.Many2one(
        'account.account', 'Default Fuel COGS Account',
        domain=[('account_type', 'in', ('expense', 'expense_direct_cost'))],
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)

    @api.depends('company_id')
    def _compute_fms_prefs(self):
        for rec in self:
            prefs = self.env['fms.site.preferences'].get_for_company(rec.company_id)
            rec.fms_prefs_id = prefs
            rec.fms_sales_journal_id = prefs.sales_journal_id
            rec.fms_clearing_account_id = prefs.clearing_account_id
            rec.fms_default_revenue_account_id = prefs.default_revenue_account_id
            rec.fms_default_cogs_account_id = prefs.default_cogs_account_id

    def _set_fms_prefs(self):
        for rec in self:
            prefs = self.env['fms.site.preferences'].get_for_company(rec.company_id)
            prefs.write({
                'sales_journal_id': rec.fms_sales_journal_id.id,
                'clearing_account_id': rec.fms_clearing_account_id.id,
                'default_revenue_account_id': rec.fms_default_revenue_account_id.id,
                'default_cogs_account_id': rec.fms_default_cogs_account_id.id,
            })
