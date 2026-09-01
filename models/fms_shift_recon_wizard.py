"""
fms_shift_recon_wizard.py — FC Cash variance resolution wizard.

Opened when supervisor clicks "Start Closing" and FC Cash variance != 0,
or manually via the shift form. Lists each attendant with variance and lets
the supervisor choose per-attendant: post to staff advance or write off.

GL entries:
  advance:  DR Staff Advances (site_prefs.staff_advance_account_id)
            CR Shift Clearing  (site_prefs.clearing_account_id)
  writeoff: DR Variance Write-Off (site_prefs.variance_writeoff_account_id)
             CR Shift Clearing  (site_prefs.clearing_account_id)

For negative variance (fc_variance < 0) the DR/CR are reversed.
After all lines resolved the wizard moves the shift to 'closing'.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class FmsShiftReconWizard(models.TransientModel):
    _name = 'fms.shift.recon.wizard'
    _description = 'FC Cash Variance Resolution Wizard'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', related='shift_id.company_id', store=True, readonly=True,
    )
    line_ids = fields.One2many(
        'fms.shift.recon.wizard.line', 'wizard_id', 'Attendant Variances',
    )
    allow_variance_writeoff = fields.Boolean(compute='_compute_prefs', store=False)
    max_writeoff_amount = fields.Float(compute='_compute_prefs', store=False)

    @api.depends('shift_id')
    def _compute_prefs(self):
        for wiz in self:
            prefs = self.env['fms.site.preferences'].get_for_company(wiz.company_id)
            wiz.allow_variance_writeoff = prefs.allow_variance_writeoff if prefs else False
            wiz.max_writeoff_amount = prefs.max_writeoff_amount if prefs else 200.0

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        shift_id = self.env.context.get('default_shift_id') or self.env.context.get('active_id')
        if not shift_id:
            return res
        shift = self.env['fms.shift'].browse(shift_id)
        prefs = self.env['fms.site.preferences'].get_for_company(shift.company_id)
        shift.attendant_cash_ids.invalidate_recordset(['fc_variance', 'fc_captured', 'fc_collected'])
        lines = []
        for cash in shift.attendant_cash_ids:
            if abs(cash.fc_variance) > 0.01:
                lines.append((0, 0, {
                    'attendant_id': cash.attendant_id.id,
                    'fc_captured': cash.fc_captured,
                    'fc_collected': cash.fc_collected,
                    'fc_variance': cash.fc_variance,
                    'resolution': 'advance',
                    'writeoff_account_id': prefs.variance_writeoff_account_id.id if prefs else False,
                }))
        res['shift_id'] = shift_id
        res['line_ids'] = lines
        return res

    def action_post_resolution(self):
        self.ensure_one()
        shift = self.shift_id
        prefs = self.env['fms.site.preferences'].get_for_company(shift.company_id)

        if not prefs or not prefs.clearing_account_id:
            raise UserError("Cash Clearing Account not set in Site Preferences.")
        if not prefs.staff_advance_account_id:
            raise UserError("Staff Advances Account not set in Site Preferences.")

        clearing_account = prefs.clearing_account_id
        journal = prefs.sales_journal_id or self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', shift.company_id.id)], limit=1
        )
        if not journal:
            raise UserError("No general journal found. Configure Sales Journal in Site Preferences.")

        move_vals_list = []
        for line in self.line_ids:
            if abs(line.fc_variance) <= 0.01:
                continue

            if line.resolution == 'writeoff':
                if not line.writeoff_account_id:
                    raise ValidationError(
                        f"Write-off account not set for {line.attendant_id.name}."
                    )
                if prefs.allow_variance_writeoff and abs(line.fc_variance) > prefs.max_writeoff_amount:
                    raise ValidationError(
                        f"Variance for {line.attendant_id.name} "
                        f"({shift.company_id.currency_id.name} {abs(line.fc_variance):,.2f}) "
                        f"exceeds the write-off threshold of {prefs.max_writeoff_amount:,.2f}. "
                        "Post to staff advance or increase the threshold in Site Preferences."
                    )
                resolution_account = line.writeoff_account_id
                label = f"FC Variance write-off — {line.attendant_id.name} — {shift.display_name}"
            else:
                resolution_account = prefs.staff_advance_account_id
                label = f"FC Variance advance — {line.attendant_id.name} — {shift.display_name}"

            variance = line.fc_variance  # positive = attendant owes more than collected
            # DR resolution_account (advance/writeoff), CR clearing
            # For negative variance reverse the sign
            move_vals_list.append({
                'journal_id': journal.id,
                'company_id': shift.company_id.id,
                'date': shift.date,
                'ref': label,
                'fms_shift_id': shift.id,
                'line_ids': [
                    (0, 0, {
                        'account_id': resolution_account.id,
                        'name': label,
                        'debit': variance if variance > 0 else 0.0,
                        'credit': -variance if variance < 0 else 0.0,
                        'partner_id': line.attendant_id.address_home_id.id if line.attendant_id.address_home_id else False,
                    }),
                    (0, 0, {
                        'account_id': clearing_account.id,
                        'name': label,
                        'debit': -variance if variance < 0 else 0.0,
                        'credit': variance if variance > 0 else 0.0,
                    }),
                ],
            })

        if move_vals_list:
            moves = self.env['account.move'].create(move_vals_list)
            moves.action_post()

        # Move shift to closing — gate already passed (variances resolved by journal entries above)
        shift.write({
            'state': 'closing',
            'closing_meter_date': fields.Datetime.now(),
            'closing_meter_user_id': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window_close'}


class FmsShiftReconWizardLine(models.TransientModel):
    _name = 'fms.shift.recon.wizard.line'
    _description = 'FC Cash Variance Resolution — Attendant Line'

    wizard_id = fields.Many2one('fms.shift.recon.wizard', required=True, ondelete='cascade')
    attendant_id = fields.Many2one('hr.employee', 'Attendant', readonly=True)
    fc_captured = fields.Float('Captured', readonly=True, digits=(16, 2))
    fc_collected = fields.Float('Collected', readonly=True, digits=(16, 2))
    fc_variance = fields.Float('Variance', readonly=True, digits=(16, 2))
    resolution = fields.Selection([
        ('advance', 'Post to Staff Advance'),
        ('writeoff', 'Write Off'),
    ], 'Resolution', required=True, default='advance')
    writeoff_account_id = fields.Many2one(
        'account.account', 'Write-Off Account',
        help="Defaults from Site Preferences. Override per attendant if needed.",
    )
    allow_writeoff = fields.Boolean(
        related='wizard_id.allow_variance_writeoff', store=False,
    )
