"""
fms_shift_correction_wizard.py — Post supervisor corrections on closed shifts.

Two correction types:
  expense     : Record a missed expense (DR Expense | CR Cash/Clearing)
  rtt         : Record a Return-to-Tank volume (reverse overstated revenue)

Each correction posts one balanced account.move linked to the shift
and writes a chatter message with the reason.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FmsShiftCorrectionWizard(models.TransientModel):
    _name = 'fms.shift.correction.wizard'
    _description = 'Closed Shift Correction'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, readonly=True)

    correction_type = fields.Selection([
        ('expense',  'Missed Expense'),
        ('rtt',      'Return to Tank (RTT) — Volume Correction'),
    ], 'Correction Type', required=True, default='expense')

    # ── Expense fields ────────────────────────────────────────────────────
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant',
        domain=[('fms_is_attendant', '=', True)],
        help="Attendant who incurred the expense (for reference only).",
    )
    expense_amount = fields.Monetary(
        'Expense Amount', currency_field='currency_id',
        help="Amount of the missed expense.",
    )
    expense_account_id = fields.Many2one(
        'account.account', 'Expense Account',
        domain="[('account_type', 'in', ('expense', 'expense_direct_cost')), ('deprecated', '=', False)]",
    )
    cash_account_id = fields.Many2one(
        'account.account', 'Cash / Clearing Account',
        domain="[('deprecated', '=', False)]",
        help="Account to credit (usually the forecourt cash clearing account).",
    )

    # ── RTT fields ────────────────────────────────────────────────────────
    meter_log_id = fields.Many2one(
        'fms.meter_log', 'Meter Log Entry',
        domain="[('shift_id', '=', shift_id)]",
        help="Original meter log entry that contains the RTT volume.",
    )
    rtt_volume = fields.Float('RTT Volume (L)', digits=(16, 3))
    rtt_price_unit = fields.Float(
        'Price per Litre', digits=(16, 4),
        help="Price used to calculate the revenue reversal amount.",
    )
    rtt_amount = fields.Monetary(
        'RTT Amount', currency_field='currency_id',
        compute='_compute_rtt_amount', store=False,
    )
    rtt_revenue_account_id = fields.Many2one(
        'account.account', 'Revenue Account',
        domain="[('account_type', 'in', ('income', 'income_other')), ('deprecated', '=', False)]",
        help="Account to debit (reverse the overstated revenue).",
    )
    rtt_clearing_account_id = fields.Many2one(
        'account.account', 'Clearing / Cash Account',
        domain="[('deprecated', '=', False)]",
        help="Account to credit for the RTT reversal.",
    )

    # ── Common ────────────────────────────────────────────────────────────
    reason = fields.Char('Reason / Reference', required=True)
    journal_id = fields.Many2one(
        'account.journal', 'Journal',
        domain="[('type', 'in', ('general', 'sale', 'cash'))]",
        help="Journal for the correcting entry. Defaults to site sales journal.",
    )
    currency_id = fields.Many2one(related='shift_id.company_id.currency_id', readonly=True)
    company_id = fields.Many2one(related='shift_id.company_id', readonly=True)

    @api.depends('rtt_volume', 'rtt_price_unit')
    def _compute_rtt_amount(self):
        for w in self:
            w.rtt_amount = w.rtt_volume * w.rtt_price_unit

    @api.onchange('shift_id', 'correction_type')
    def _onchange_shift(self):
        if not self.shift_id:
            return
        prefs = self.env['fms.site.preferences'].get_for_company(self.shift_id.company_id)
        if prefs.sales_journal_id:
            self.journal_id = prefs.sales_journal_id
        if prefs.clearing_account_id:
            self.cash_account_id = prefs.clearing_account_id
            self.rtt_clearing_account_id = prefs.clearing_account_id

    @api.onchange('meter_log_id')
    def _onchange_meter_log(self):
        if self.meter_log_id:
            self.rtt_price_unit = self.meter_log_id.product_id.list_price or 0.0
            if self.meter_log_id.product_id.fms_revenue_account_id:
                self.rtt_revenue_account_id = self.meter_log_id.product_id.fms_revenue_account_id

    def _validate(self):
        if self.correction_type == 'expense':
            if not self.expense_amount or self.expense_amount <= 0:
                raise ValidationError("Expense amount must be > 0.")
            if not self.expense_account_id:
                raise ValidationError("Expense account is required.")
            if not self.cash_account_id:
                raise ValidationError("Cash / clearing account is required.")
        else:
            if not self.rtt_volume or self.rtt_volume <= 0:
                raise ValidationError("RTT volume must be > 0.")
            if not self.rtt_price_unit or self.rtt_price_unit <= 0:
                raise ValidationError("Price per litre must be > 0.")
            if not self.rtt_revenue_account_id:
                raise ValidationError("Revenue account is required.")
            if not self.rtt_clearing_account_id:
                raise ValidationError("Clearing account is required.")
        if not self.journal_id:
            raise ValidationError("Journal is required.")

    def action_post_correction(self):
        self.ensure_one()
        self._validate()

        shift = self.shift_id
        if shift.state != 'closed':
            raise UserError("This wizard only applies to closed shifts.")

        if self.correction_type == 'expense':
            move = self._post_expense_correction(shift)
        else:
            move = self._post_rtt_correction(shift)

        shift.message_post(
            body=(
                f"<b>Correction posted by {self.env.user.name}</b><br/>"
                f"Type: {dict(self._fields['correction_type'].selection)[self.correction_type]}<br/>"
                f"Reason: {self.reason}<br/>"
                f"Journal Entry: <a href='/odoo/accounting/journal-entries/{move.id}'>"
                f"{move.name}</a>"
            )
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _post_expense_correction(self, shift):
        """DR Expense | CR Cash/Clearing — missed expense."""
        move = self.env['account.move'].with_company(shift.company_id).create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'company_id': shift.company_id.id,
            'date': shift.date,
            'ref': f"Correction: {self.reason} (Shift {shift.display_name})",
            'line_ids': [
                (0, 0, {
                    'account_id': self.expense_account_id.id,
                    'name': f"Missed expense — {self.reason}",
                    'debit': self.expense_amount,
                    'credit': 0.0,
                    'partner_id': self.attendant_id.address_id.id if self.attendant_id.address_id else False,
                }),
                (0, 0, {
                    'account_id': self.cash_account_id.id,
                    'name': f"Missed expense — {self.reason}",
                    'debit': 0.0,
                    'credit': self.expense_amount,
                }),
            ],
        })
        move.action_post()
        return move

    def _post_rtt_correction(self, shift):
        """DR Revenue | CR Clearing — RTT overstated revenue reversal."""
        amount = self.rtt_amount
        product_name = self.meter_log_id.product_id.name if self.meter_log_id else ''
        ref = f"RTT correction {self.rtt_volume:.2f}L {product_name} — {self.reason}"
        move = self.env['account.move'].with_company(shift.company_id).create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'company_id': shift.company_id.id,
            'date': shift.date,
            'ref': f"{ref} (Shift {shift.display_name})",
            'line_ids': [
                (0, 0, {
                    'account_id': self.rtt_revenue_account_id.id,
                    'name': ref,
                    'debit': amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': self.rtt_clearing_account_id.id,
                    'name': ref,
                    'debit': 0.0,
                    'credit': amount,
                }),
            ],
        })
        move.action_post()
        # Update the meter_log rtt_volume for audit visibility (log is read-only in UI
        # but correction wizard has the authority to update it).
        if self.meter_log_id:
            self.env.cr.execute(
                "UPDATE fms_meter_log SET rtt_volume = COALESCE(rtt_volume,0) + %s WHERE id = %s",
                (self.rtt_volume, self.meter_log_id.id),
            )
        return move
