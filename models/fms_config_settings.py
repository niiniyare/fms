from odoo import models, fields, api


class FMSConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── Gate thresholds — proxied through fms.site.preferences ───────────────
    # Previously stored via config_parameter='fms.xxx' (ir.config_parameter),
    # but gates read from prefs.elec_vs_cash_threshold_l / prefs.default_dip_variance_meniscus.
    # Storing in a separate table meant Settings UI changes had zero effect on gate behavior.
    fms_meniscus_l = fields.Float(
        'Dip Variance Meniscus (L)',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
        default=50.0,
    )
    fms_elec_vs_cash_threshold_l = fields.Float(
        'Elec vs Cash Threshold (L)',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
        default=5.0,
    )

    # ── Shift schedule ────────────────────────────────────────────────────────
    fms_shift_duration_hrs = fields.Selection([
        ('8',  '8 hours  — 3 shifts/day'),
        ('12', '12 hours — 2 shifts/day'),
        ('24', '24 hours — 1 shift/day'),
    ], string='Shift Duration',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)

    # ── POS / gate behaviour ──────────────────────────────────────────────────
    fms_require_pos_reconciliation = fields.Boolean(
        'Require POS Reconciliation',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
    )
    fms_auto_open_next_shift = fields.Boolean(
        'Auto-open Next Shift on Close',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
    )
    fms_auto_sync_attendants = fields.Boolean(
        'Auto-sync Attendant Lines on Closing',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
    )
    fms_allow_multiple_disputed = fields.Boolean(
        'Allow Multiple Disputed Shifts',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False,
    )

    # ── Attendant mode ────────────────────────────────────────────────────────
    fms_attendant_assignment_mode = fields.Selection([
        ('per_nozzle',   'Per Nozzle'),
        ('pre_assigned', 'Pre-Assigned'),
    ], string='Attendant Assignment',
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)

    # ── GL / journals (stored on fms.site.preferences) ───────────────────────
    fms_prefs_id = fields.Many2one(
        'fms.site.preferences', compute='_compute_fms_prefs', store=False)

    fms_sales_journal_id = fields.Many2one(
        'account.journal', 'Forecourt Sales Journal',
        domain=[('type', '=', 'sale')],
        compute='_compute_fms_prefs', inverse='_set_fms_prefs', store=False)
    fms_clearing_account_id = fields.Many2one(
        'account.account', 'Cash Clearing Account',
        domain=[('account_type', '=', 'asset_current')],
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
            rec.fms_meniscus_l = prefs.default_dip_variance_meniscus
            rec.fms_elec_vs_cash_threshold_l = prefs.elec_vs_cash_threshold_l
            rec.fms_shift_duration_hrs = prefs.shift_duration_hrs
            rec.fms_require_pos_reconciliation = prefs.require_pos_reconciliation
            rec.fms_auto_open_next_shift = prefs.auto_open_next_shift
            rec.fms_auto_sync_attendants = prefs.auto_sync_attendants
            rec.fms_allow_multiple_disputed = prefs.allow_multiple_disputed
            rec.fms_attendant_assignment_mode = prefs.attendant_assignment_mode

    def _set_fms_prefs(self):
        for rec in self:
            prefs = self.env['fms.site.preferences'].get_for_company(rec.company_id)
            prefs.write({
                'sales_journal_id': rec.fms_sales_journal_id.id,
                'clearing_account_id': rec.fms_clearing_account_id.id,
                'default_revenue_account_id': rec.fms_default_revenue_account_id.id,
                'default_cogs_account_id': rec.fms_default_cogs_account_id.id,
                'default_dip_variance_meniscus': rec.fms_meniscus_l,
                'elec_vs_cash_threshold_l': rec.fms_elec_vs_cash_threshold_l,
                'shift_duration_hrs': rec.fms_shift_duration_hrs,
                'require_pos_reconciliation': rec.fms_require_pos_reconciliation,
                'auto_open_next_shift': rec.fms_auto_open_next_shift,
                'auto_sync_attendants': rec.fms_auto_sync_attendants,
                'allow_multiple_disputed': rec.fms_allow_multiple_disputed,
                'attendant_assignment_mode': rec.fms_attendant_assignment_mode,
            })
