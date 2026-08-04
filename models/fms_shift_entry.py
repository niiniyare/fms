"""
fms_shift_entry.py — Editable entry child models for a shift

These are the forms attendants fill in during a shift:
- fms.shift.meter.entry: pump nozzle opening/closing readings (editable until shift closes)
- fms.shift.dip.entry: tank dip volume readings (editable until shift closes)
- fms.shift.attendant.cash: per-attendant cash reconciliation

Full implementation in FMS-002.
"""

from odoo import models, fields, api


class FMSShiftMeterEntry(models.Model):
    """Editable pump meter readings for one shift. Copied to fms.meter_log on close."""

    _name = 'fms.shift.meter.entry'
    _description = 'Shift Meter Entry'
    _order = 'shift_id, pump_id, nozzle_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    pump_id = fields.Many2one('fms.pump', 'Pump', required=True)
    nozzle_id = fields.Many2one('fms.pump.nozzle', 'Nozzle', required=True)

    opening_elec_volume = fields.Float('Opening Electronic (L)', digits=(16, 2))
    closing_elec_volume = fields.Float('Closing Electronic (L)', digits=(16, 2))
    opening_man_mech = fields.Float('Opening Manual (L)', digits=(16, 2))
    closing_man_mech = fields.Float('Closing Manual (L)', digits=(16, 2))

    qty_sold_elec = fields.Float(
        'Qty Sold (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )

    @api.depends('closing_elec_volume', 'opening_elec_volume')
    def _compute_qty(self):
        for entry in self:
            entry.qty_sold_elec = entry.closing_elec_volume - (entry.opening_elec_volume or 0.0)


class FMSShiftDipEntry(models.Model):
    """Editable tank dip readings for one shift. Copied to fms.dip_log on close."""

    _name = 'fms.shift.dip.entry'
    _description = 'Shift Dip Entry'
    _order = 'shift_id, location_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    location_id = fields.Many2one(
        'stock.location', 'Tank', required=True,
        domain=[('fms_is_fuel_tank', '=', True)],
    )

    opening_volume = fields.Float('Opening Volume (L)', digits=(16, 2))
    closing_volume = fields.Float('Closing Volume (L)', digits=(16, 2))

    qty_change = fields.Float(
        'Volume Change (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )

    @api.depends('closing_volume', 'opening_volume')
    def _compute_qty(self):
        for entry in self:
            entry.qty_change = entry.closing_volume - (entry.opening_volume or 0.0)


class FMSShiftAttendantCash(models.Model):
    """Per-attendant cash reconciliation for one shift."""

    _name = 'fms.shift.attendant.cash'
    _description = 'Shift Attendant Cash Reconciliation'
    _order = 'shift_id, attendant_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    attendant_id = fields.Many2one('hr.employee', 'Attendant', required=True)

    cash_collected = fields.Float('Cash Collected', digits=(16, 2))
    ar_amount = fields.Float('Accounts Receivable', digits=(16, 2))
    card_amount = fields.Float('Card Payments', digits=(16, 2))
    expense_amount = fields.Float('Expenses', digits=(16, 2))
    mpesa_amount = fields.Float('MPesa', digits=(16, 2))

    total_accounted = fields.Float(
        'Total Accounted', compute='_compute_total', store=True, digits=(16, 2),
    )

    @api.depends('cash_collected', 'ar_amount', 'card_amount', 'expense_amount', 'mpesa_amount')
    def _compute_total(self):
        for entry in self:
            entry.total_accounted = (
                entry.cash_collected
                + entry.ar_amount
                + entry.card_amount
                + entry.mpesa_amount
                - entry.expense_amount
            )
