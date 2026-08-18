"""
fms_logs.py — Immutable audit logs for meter readings and tank dips

Once written, these records are locked: write() and unlink() raise ValidationError.
This satisfies EPRA compliance requirements for tamper-proof audit trails.

Reference: FMS_Complete_Specification_Technical_Guide.md, Section 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSMeterLog(models.Model):
    """Immutable record of pump nozzle opening/closing readings for one shift."""

    _name = 'fms.meter_log'
    _description = 'Meter Reading Audit Log (Immutable)'
    _order = 'shift_id, pump_id, nozzle_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade', index=True)
    pump_id = fields.Many2one('fms.pump', 'Pump', required=True)
    nozzle_id = fields.Many2one('fms.pump.nozzle', 'Nozzle', required=True)
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='nozzle_id.product_id', store=True, readonly=True,
    )

    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', readonly=True,
        help="Attendant who was responsible for this nozzle during this shift.",
    )

    # Meter 1: Electronic Volume
    opening_elec_volume = fields.Float('Opening Elec Vol (L)', digits=(16, 2))
    closing_elec_volume = fields.Float('Closing Elec Vol (L)', required=True, digits=(16, 2))

    # Meter 2: Electronic Cash (KES totalizer)
    opening_elec_cash = fields.Float('Opening Elec Cash', digits=(16, 2))
    closing_elec_cash = fields.Float('Closing Elec Cash', digits=(16, 2))
    elec_cash_sold = fields.Float(
        'Cash Sold', compute='_compute_qty', store=True, digits=(16, 2),
    )

    # Meter 3: Manual Mechanical
    opening_man_mech = fields.Float('Opening Manual (L)', digits=(16, 2))
    closing_man_mech = fields.Float('Closing Manual (L)', digits=(16, 2))

    # RTT
    rtt_volume = fields.Float('RTT Volume (L)', digits=(16, 2))

    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    amount_elec = fields.Float(
        'Volume × Price', compute='_compute_amount', store=True, digits=(16, 2),
    )

    recorded_date = fields.Datetime('Recorded At', default=fields.Datetime.now, readonly=True)
    recorded_user_id = fields.Many2one(
        'res.users', 'Recorded By',
        default=lambda self: self.env.user, readonly=True,
    )

    @api.depends(
        'closing_elec_volume', 'opening_elec_volume',
        'closing_elec_cash', 'opening_elec_cash',
        'closing_man_mech', 'opening_man_mech',
        'rtt_volume',
    )
    def _compute_qty(self):
        for log in self:
            log.qty_sold_elec  = (log.closing_elec_volume - (log.opening_elec_volume or 0.0)) - (log.rtt_volume or 0.0)
            log.elec_cash_sold = log.closing_elec_cash   - (log.opening_elec_cash   or 0.0)
            log.qty_sold_man   = log.closing_man_mech    - (log.opening_man_mech    or 0.0)

    @api.depends('qty_sold_elec', 'product_id', 'product_id.list_price')
    def _compute_amount(self):
        for log in self:
            log.amount_elec = log.qty_sold_elec * (log.product_id.list_price or 0.0)

    def write(self, vals):
        raise ValidationError(
            "Meter logs are immutable. Contact your supervisor to post a correction entry."
        )

    def unlink(self):
        raise ValidationError(
            "Meter logs cannot be deleted — they form part of the EPRA audit trail."
        )


class FMSDipLog(models.Model):
    """Immutable record of tank dip (volume) readings for one shift."""

    _name = 'fms.dip_log'
    _description = 'Tank Dip Audit Log (Immutable)'
    _order = 'shift_id, location_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade', index=True)
    location_id = fields.Many2one(
        'stock.location', 'Tank', required=True,
        domain=[('fms_is_fuel_tank', '=', True)],
    )
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='location_id.fms_fuel_product_id', store=True, readonly=True,
    )

    opening_volume = fields.Float('Opening Volume (L)', digits=(16, 2))
    closing_volume = fields.Float('Closing Volume (L)', required=True, digits=(16, 2))

    qty_change = fields.Float(
        'Volume Change (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    variance_pct = fields.Float(
        'Variance %', compute='_compute_variance', store=True, digits=(16, 4),
    )

    recorded_date = fields.Datetime('Recorded At', default=fields.Datetime.now, readonly=True)
    recorded_user_id = fields.Many2one(
        'res.users', 'Recorded By',
        default=lambda self: self.env.user, readonly=True,
    )

    @api.depends('closing_volume', 'opening_volume')
    def _compute_qty(self):
        for log in self:
            log.qty_change = log.closing_volume - (log.opening_volume or 0.0)

    @api.depends('qty_change', 'closing_volume')
    def _compute_variance(self):
        for log in self:
            if log.closing_volume > 0:
                log.variance_pct = abs(log.qty_change) / log.closing_volume * 100.0
            else:
                log.variance_pct = 0.0

    def write(self, vals):
        raise ValidationError(
            "Dip logs are immutable. Contact your supervisor to post a correction entry."
        )

    def unlink(self):
        raise ValidationError(
            "Dip logs cannot be deleted — they form part of the EPRA audit trail."
        )
