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

    # ── Gate 5: Dip variance meniscus (absolute litres) ──────────────────────
    default_dip_variance_meniscus = fields.Float(
        'Dip Variance Meniscus (L)', default=1000.0, digits=(10, 2),
        help="Maximum absolute tank dip variance in litres before Gate 5 blocks shift close. "
             "Default: ±1000 L. Supervisor must investigate or post a stock adjustment if exceeded.",
    )
    meniscus_pct = fields.Float(
        'Variance Meniscus (%) [deprecated]', default=0.5, digits=(5, 2),
        help="Kept for Gate 6 (meter vs invoice) backward compatibility only. "
             "Dip gate now uses Dip Variance Meniscus (L) above.",
    )

    # ── Attendant assignment mode ─────────────────────────────────────────────
    attendant_assignment_mode = fields.Selection([
        ('per_nozzle',    'Per Nozzle — attendant set on each meter entry row'),
        ('pre_assigned',  'Pre-Assigned — default attendant from nozzle definition'),
    ], string='Attendant Assignment Mode', default='per_nozzle',
        help="Controls how attendants are assigned to nozzles during a shift.\n"
             "Per Nozzle: supervisor fills attendant on each meter entry before closing.\n"
             "Pre-Assigned: nozzle's default attendant is auto-populated when shift opens.",
    )

    # ── Disputed shift control ────────────────────────────────────────────────
    allow_multiple_disputed = fields.Boolean(
        'Allow Multiple Disputed Shifts', default=False,
        help="When enabled, more than one shift can be in 'Disputed' state at the same time. "
             "Default: disabled (only one disputed shift per company).",
    )

    # ── Three-meter gate: Electronic vs Cash threshold ────────────────────────
    elec_vs_cash_threshold_l = fields.Float(
        'Elec vs Cash Threshold (L)', default=5.0, digits=(10, 2),
        help="Maximum allowed variance between Electronic volume and Cash meter volume "
             "per nozzle (in litres). Default: 5L. Set to 0 to disable this gate.",
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

    # ── Shift schedule ────────────────────────────────────────────────────────
    shift_duration_hrs = fields.Selection([
        ('8',  '8 hours  (3 shifts/day: Day / Evening / Night)'),
        ('12', '12 hours (2 shifts/day: Day / Night)'),
        ('24', '24 hours (1 shift/day)'),
    ], string='Shift Duration', default='8',
       help="Controls planned close time and which label the auto-created next shift gets.")

    # Start-of-day hour for each slot (24h clock, integer).
    # Only used when shift_duration_hrs = '8' or '12'.
    shift_1_start_hour = fields.Integer('Shift 1 Start Hour', default=6,
                                        help="e.g. 6 = 06:00")
    shift_2_start_hour = fields.Integer('Shift 2 Start Hour', default=14,
                                        help="e.g. 14 = 14:00 (ignored for 24hr)")
    shift_3_start_hour = fields.Integer('Shift 3 Start Hour', default=22,
                                        help="e.g. 22 = 22:00 (8hr only)")

    # ── Operational ───────────────────────────────────────────────────────────
    auto_sync_attendants = fields.Boolean(
        'Auto-sync Attendant Cash Lines', default=True,
        help="Automatically create attendant cash lines when Start Closing is clicked.",
    )
    auto_open_next_shift = fields.Boolean(
        'Auto-open Next Shift on Close', default=True,
        help="When a shift closes, immediately create and open the next one.",
    )

    # ── POS integration ───────────────────────────────────────────────────────
    require_pos_reconciliation = fields.Boolean(
        'Require POS Reconciliation', default=True,
        help="When enabled, volume and cash gates compare meter readings against "
             "linked POS sessions. Disable only for stations not using Odoo POS "
             "(e.g., using an external PTS system or manual entry only).",
    )

    # ── Variance Resolution ─────────────────────────────────────────────────
    staff_advance_account_id = fields.Many2one(
        'account.account', 'Staff Advances Account',
        company_dependent=True,
        help="Account debited when posting attendant FC Cash variance as a staff advance "
             "(e.g. 115130 Staff Advances). Required when Variance Resolution is in use.",
    )
    allow_variance_writeoff = fields.Boolean(
        'Allow Variance Write-Off', default=False,
        help="When enabled, supervisors may write off small FC Cash variances "
             "to a dedicated account instead of posting to employee advance.",
    )
    variance_writeoff_account_id = fields.Many2one(
        'account.account', 'Variance Write-Off Account',
        company_dependent=True,
        help="Account debited (or credited for negative variance) when writing off "
             "attendant FC Cash discrepancies. Visible only when Allow Write-Off is on.",
    )
    max_writeoff_amount = fields.Float(
        'Write-Off Threshold (±)', default=200.0,
        help="Maximum absolute variance that may be written off per attendant per shift. "
             "Variances above this threshold must be posted to employee advance.",
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
            with self.env.cr.savepoint():
                try:
                    prefs = self.sudo().create({'company_id': company.id})
                except Exception:
                    # Another transaction raced us — savepoint auto-rolls back the failed INSERT.
                    prefs = self.search([('company_id', '=', company.id)], limit=1)
        return prefs

    @api.model
    def _fms_configure_defaults(self, clearing_account_id, cogs_account_id, journal_id):
        """Called from data XML to wire GL accounts onto the existing prefs record.

        Uses write() so it's safe whether the record was just created or already
        existed (avoids the UNIQUE constraint error from a duplicate INSERT).
        """
        Account = self.env['account.account']
        Journal = self.env['account.journal']
        revenue_acc = Account.search([('code', '=', '400000')], limit=1)

        prefs = self.get_for_company(self.env.company)
        vals = {
            'clearing_account_id': clearing_account_id,
            'default_cogs_account_id': cogs_account_id,
            'sales_journal_id': journal_id,
        }
        if revenue_acc:
            vals['default_revenue_account_id'] = revenue_acc.id
        prefs.write(vals)
