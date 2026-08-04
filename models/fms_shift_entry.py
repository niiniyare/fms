"""
fms_shift_entry.py — Editable child entry models for a shift

These are the working records attendants fill in during a shift.
On shift close they are snapshotted into immutable fms.meter_log / fms.dip_log.

Models:
  - fms.shift.meter.entry  — one pump nozzle's opening/closing meter reading
  - fms.shift.dip.entry    — one tank's opening/closing dip volume
  - fms.shift.attendant.cash — per-attendant cash + payment-mode breakdown

Reference: FMS_Complete_Specification_Technical_Guide.md, Section 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSShiftMeterEntry(models.Model):
    """
    Editable meter reading for one nozzle during a shift.

    Locked (no write/unlink) once the parent shift reaches 'closed'.
    On close, a corresponding fms.meter_log record is written.
    """

    _name = 'fms.shift.meter.entry'
    _description = 'Shift Meter Entry'
    _order = 'pump_id, nozzle_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')

    pump_id = fields.Many2one('fms.pump', 'Pump', required=True)
    nozzle_id = fields.Many2one(
        'fms.pump.nozzle', 'Nozzle', required=True,
        domain="[('pump_id', '=', pump_id)]",
    )
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='nozzle_id.product_id', store=True, readonly=True,
    )

    # Readings
    opening_elec_volume = fields.Float('Opening Electronic (L)', digits=(16, 2))
    closing_elec_volume = fields.Float('Closing Electronic (L)', digits=(16, 2))
    opening_man_mech = fields.Float('Opening Manual (L)', digits=(16, 2))
    closing_man_mech = fields.Float('Closing Manual (L)', digits=(16, 2))

    # Computed sales quantities
    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    amount_elec = fields.Float(
        'Amount (Elec)', compute='_compute_amount', store=True, digits=(16, 2),
    )

    notes = fields.Char('Notes')

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends('closing_elec_volume', 'opening_elec_volume',
                 'closing_man_mech', 'opening_man_mech')
    def _compute_qty(self):
        for e in self:
            e.qty_sold_elec = e.closing_elec_volume - (e.opening_elec_volume or 0.0)
            e.qty_sold_man = e.closing_man_mech - (e.opening_man_mech or 0.0)

    @api.depends('qty_sold_elec', 'product_id', 'product_id.list_price')
    def _compute_amount(self):
        for e in self:
            e.amount_elec = e.qty_sold_elec * (e.product_id.list_price or 0.0)

    # ------------------------------------------------------------------
    # Auto-fill pump from nozzle
    # ------------------------------------------------------------------

    @api.onchange('nozzle_id')
    def _onchange_nozzle_id(self):
        if self.nozzle_id and self.nozzle_id.pump_id:
            self.pump_id = self.nozzle_id.pump_id

    # ------------------------------------------------------------------
    # Locking: no edits once shift is closed
    # ------------------------------------------------------------------

    def _check_shift_open(self):
        for entry in self:
            if entry.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit meter entries on a closed shift. "
                    "The shift's meter logs are the immutable record."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()

    # ------------------------------------------------------------------
    # Snapshot to immutable log
    # ------------------------------------------------------------------

    def _create_meter_log(self):
        """Copy this entry to fms.meter_log (called by shift on close)."""
        self.ensure_one()
        return self.env['fms.meter_log'].sudo().create({
            'shift_id': self.shift_id.id,
            'pump_id': self.pump_id.id,
            'nozzle_id': self.nozzle_id.id,
            'opening_elec_volume': self.opening_elec_volume,
            'opening_man_mech': self.opening_man_mech,
            'closing_elec_volume': self.closing_elec_volume,
            'closing_man_mech': self.closing_man_mech,
        })


class FMSShiftDipEntry(models.Model):
    """
    Editable tank dip volume for one shift.

    Locked once parent shift is closed.  On close, copied to fms.dip_log.
    """

    _name = 'fms.shift.dip.entry'
    _description = 'Shift Dip Entry'
    _order = 'location_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    location_id = fields.Many2one(
        'stock.location', 'Tank', required=True,
        domain=[('fms_is_fuel_tank', '=', True)],
    )
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='location_id.fms_fuel_product_id', store=True, readonly=True,
    )

    opening_volume = fields.Float('Opening Volume (L)', digits=(16, 2))
    closing_volume = fields.Float('Closing Volume (L)', digits=(16, 2))

    qty_change = fields.Float(
        'Volume Change (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    variance_pct = fields.Float(
        'Variance %', compute='_compute_variance', store=True, digits=(16, 4),
    )

    notes = fields.Char('Notes')

    @api.depends('closing_volume', 'opening_volume')
    def _compute_qty(self):
        for e in self:
            e.qty_change = e.closing_volume - (e.opening_volume or 0.0)

    @api.depends('qty_change', 'closing_volume')
    def _compute_variance(self):
        for e in self:
            if e.closing_volume > 0:
                e.variance_pct = abs(e.qty_change) / e.closing_volume * 100.0
            else:
                e.variance_pct = 0.0

    def _check_shift_open(self):
        for entry in self:
            if entry.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit dip entries on a closed shift."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()

    def _create_dip_log(self):
        """Copy this entry to fms.dip_log (called by shift on close)."""
        self.ensure_one()
        return self.env['fms.dip_log'].sudo().create({
            'shift_id': self.shift_id.id,
            'location_id': self.location_id.id,
            'opening_volume': self.opening_volume,
            'closing_volume': self.closing_volume,
        })


class FMSShiftAttendantCash(models.Model):
    """
    Per-attendant payment breakdown for one shift.

    The supervisor enters what each attendant brought in (cash, MPesa,
    card, AR) and what they paid out (expenses).  The balance must be
    zero for the shift to close (hard gate, enforced in FMS-006).
    """

    _name = 'fms.shift.attendant.cash'
    _description = 'Shift Attendant Cash Reconciliation'
    _order = 'attendant_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True,
        domain=[('fms_is_attendant', '=', True)],
    )

    # Sales reported by attendant
    reported_sales = fields.Float('Reported Sales (KES)', digits=(16, 2))

    # Payment modes collected
    cash_collected = fields.Float('Cash (KES)', digits=(16, 2))
    mpesa_amount = fields.Float('MPesa (KES)', digits=(16, 2))
    card_amount = fields.Float('Card (KES)', digits=(16, 2))
    ar_amount = fields.Float('Accounts Receivable (KES)', digits=(16, 2))

    # Outflows
    expense_amount = fields.Float('Expenses Paid (KES)', digits=(16, 2))

    # Computed
    total_accounted = fields.Float(
        'Total Accounted (KES)', compute='_compute_totals', store=True, digits=(16, 2),
    )
    balance = fields.Float(
        'Balance (KES)', compute='_compute_totals', store=True, digits=(16, 2),
        help="Reported Sales minus Total Accounted. Must be 0 to close shift.",
    )

    notes = fields.Char('Notes')

    @api.depends('reported_sales', 'cash_collected', 'mpesa_amount',
                 'card_amount', 'ar_amount', 'expense_amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_accounted = (
                rec.cash_collected
                + rec.mpesa_amount
                + rec.card_amount
                + rec.ar_amount
                - rec.expense_amount
            )
            rec.balance = rec.reported_sales - rec.total_accounted

    def _check_shift_open(self):
        for rec in self:
            if rec.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit attendant cash records on a closed shift."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()
