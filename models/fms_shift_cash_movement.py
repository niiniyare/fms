"""
fms_shift_cash_movement.py — Simplified float / drop entry per shift attendant.

Each row = one cash movement. Either float_amount OR drop_amount is filled, not both.
On save, an account.payment is auto-created (or updated) so FC Cash variance picks it up
through the existing SQL aggregation in _compute_fc_variance.

FC Cash impact:
  float_amount > 0  →  fms_payment_context='cash_float'  (DR attendant, increases FC Cash)
  drop_amount  > 0  →  fms_payment_context='cash_drop'   (CR attendant, reduces FC Cash)
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class FmsShiftCashMovement(models.Model):
    _name = 'fms.shift.cash.movement'
    _description = 'Shift Float / Drop'
    _order = 'shift_id, date, attendant_id'

    shift_id = fields.Many2one(
        'fms.shift', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', related='shift_id.company_id', store=True, readonly=True,
    )
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True,
        domain=[('fms_is_attendant', '=', True)],
    )
    float_amount = fields.Float(
        'Float', digits=(16, 2), default=0.0,
        help="Cash issued to attendant. Leave 0 if recording a drop.",
    )
    drop_amount = fields.Float(
        'Drop', digits=(16, 2), default=0.0,
        help="Cash collected from attendant. Leave 0 if recording a float.",
    )
    date = fields.Date(
        'Dropped At', required=True,
        default=lambda self: self._default_date(),
    )
    note = fields.Char('Note')
    payment_id = fields.Many2one(
        'account.payment', 'Payment', readonly=True, copy=False,
        ondelete='set null',
        help="Auto-created account.payment backing this movement.",
    )

    def _default_date(self):
        shift_id = self.env.context.get('default_shift_id')
        if shift_id:
            shift = self.env['fms.shift'].browse(shift_id)
            if shift.date:
                return shift.date
        return fields.Date.today()

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains('float_amount', 'drop_amount')
    def _check_one_side_only(self):
        for rec in self:
            if rec.float_amount > 0 and rec.drop_amount > 0:
                raise ValidationError(
                    "Enter either Float or Drop — not both on the same line.\n"
                    f"Attendant: {rec.attendant_id.name}"
                )
            if rec.float_amount < 0 or rec.drop_amount < 0:
                raise ValidationError("Float and Drop amounts must be zero or positive.")
            if rec.float_amount == 0 and rec.drop_amount == 0:
                raise ValidationError("Enter a Float or Drop amount (cannot be 0 on both).")

    @api.constrains('shift_id')
    def _check_shift_open(self):
        for rec in self:
            if rec.shift_id.state == 'closed':
                raise ValidationError(
                    f"Cannot add cash movements to closed shift '{rec.shift_id.display_name}'."
                )

    # ------------------------------------------------------------------
    # Auto-create / update account.payment on save
    # ------------------------------------------------------------------

    def _get_cash_journal(self):
        journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            raise UserError(
                "No Cash journal found for this company. "
                "Set up a Cash journal in Accounting → Configuration → Journals."
            )
        return journal

    def _build_payment_vals(self):
        self.ensure_one()
        journal = self._get_cash_journal()
        is_float = self.float_amount > 0
        amount = self.float_amount if is_float else self.drop_amount
        context = 'cash_float' if is_float else 'cash_drop'
        # Float = cash OUT of safe to attendant (outbound from company perspective)
        # Drop  = cash IN from attendant to safe (inbound from company perspective)
        payment_type = 'outbound' if is_float else 'inbound'
        return {
            'journal_id': journal.id,
            'company_id': self.company_id.id,
            'date': self.date,
            'amount': amount,
            'payment_type': payment_type,
            'partner_type': 'customer',
            'partner_id': self.attendant_id.address_home_id.id if self.attendant_id.address_home_id else False,
            'memo': self.note or (('Float' if is_float else 'Drop') + f' — {self.attendant_id.name} — {self.shift_id.display_name}'),
            'fms_shift_id': self.shift_id.id,
            'fms_attendant_id': self.attendant_id.id,
            'fms_payment_context': context,
        }

    def _sync_payment(self):
        """Create or update the backing account.payment, then post it."""
        for rec in self:
            vals = rec._build_payment_vals()
            if rec.payment_id:
                if rec.payment_id.state == 'posted':
                    # Already posted — cancel and recreate (amount/type changed)
                    try:
                        rec.payment_id.action_cancel()
                        rec.payment_id.action_draft()
                    except Exception:
                        raise UserError(
                            f"Cannot update posted payment for {rec.attendant_id.name}. "
                            "Cancel the existing payment manually then save again."
                        )
                rec.payment_id.write(vals)
                payment = rec.payment_id
            else:
                payment = self.env['account.payment'].create(vals)
                rec.payment_id = payment
            payment.action_post()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_payment()
        return records

    def write(self, vals):
        result = super().write(vals)
        amount_changed = any(k in vals for k in ('float_amount', 'drop_amount', 'date', 'attendant_id', 'note'))
        if amount_changed:
            self._sync_payment()
        return result

    def unlink(self):
        for rec in self:
            if rec.shift_id.state == 'closed':
                raise ValidationError("Cannot delete movements on a closed shift.")
            if rec.payment_id and rec.payment_id.state == 'posted':
                raise ValidationError(
                    f"Posted payment exists for {rec.attendant_id.name}. "
                    "Reverse the payment before deleting this line."
                )
            if rec.payment_id:
                rec.payment_id.unlink()
        return super().unlink()
