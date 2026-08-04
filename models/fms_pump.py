"""
fms_pump.py — Fuel pump and nozzle master data

Reference: FMS_Complete_Specification_Technical_Guide.md, Section 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSPump(models.Model):
    """Physical fuel dispenser unit at the forecourt."""

    _name = 'fms.pump'
    _description = 'Fuel Pump'
    _order = 'order, name'

    name = fields.Char('Pump Name', required=True)
    order = fields.Integer('Display Order', required=True, default=1)
    active = fields.Boolean(default=True)

    # Optional link to POS hardware terminal
    pos_terminal_id = fields.Many2one('pos.terminal', 'POS Terminal')

    nozzle_ids = fields.One2many('fms.pump.nozzle', 'pump_id', 'Nozzles')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Pump name must be unique.'),
    ]


class FMSPumpNozzle(models.Model):
    """Single nozzle on a pump, dispensing one fuel product."""

    _name = 'fms.pump.nozzle'
    _description = 'Fuel Pump Nozzle'
    _order = 'pump_id, order, letter'

    pump_id = fields.Many2one('fms.pump', 'Pump', required=True, ondelete='cascade')
    name = fields.Char('Nozzle Label', required=True)
    order = fields.Integer('Display Order', required=True, default=1)
    letter = fields.Char('Letter/Number', required=True)

    product_id = fields.Many2one(
        'product.product', 'Fuel Product', required=True,
        domain=[('fms_is_fuel', '=', True)],
    )
    active = fields.Boolean(default=True)

    @api.constrains('letter', 'pump_id')
    def _check_unique_nozzle(self):
        for nozzle in self:
            duplicate = self.env['fms.pump.nozzle'].search([
                ('pump_id', '=', nozzle.pump_id.id),
                ('letter', '=', nozzle.letter),
                ('id', '!=', nozzle.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f"Nozzle '{nozzle.letter}' already exists on pump '{nozzle.pump_id.name}'."
                )
