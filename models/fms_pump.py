"""
fms_pump.py — Fuel pump and nozzle master data

Pump   → physical dispenser machine with a name and code.
Nozzle → single product outlet on a pump. Requires initialization
         (3 opening meter readings + date) before it can be used in shifts.

Nozzle lifecycle:
  draft → initialized (enter 3 meter readings + init date/shift)
        → active (test passed, ready for shift recording)
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSPump(models.Model):
    """Physical fuel dispenser unit at the forecourt."""

    _name = 'fms.pump'
    _description = 'Fuel Pump'
    _order = 'order, name'

    name = fields.Char('Pump Name', required=True)
    code = fields.Char('Pump Code', required=True,
                       help="Short unique code used on reports (e.g. UX1, DX2).")
    order = fields.Integer('Display Order', required=True, default=1)
    active = fields.Boolean(default=True)

    nozzle_ids = fields.One2many('fms.pump.nozzle', 'pump_id', 'Nozzles')

    nozzle_count = fields.Integer(compute='_compute_nozzle_count')

    def _compute_nozzle_count(self):
        for pump in self:
            pump.nozzle_count = len(pump.nozzle_ids)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Pump name must be unique.'),
        ('code_unique', 'UNIQUE(code)', 'Pump code must be unique.'),
    ]


class FMSPumpNozzle(models.Model):
    """
    Single nozzle on a pump, dispensing one fuel product.

    Must be initialized with 3 opening meter readings before it can
    participate in shift recording.
    """

    _name = 'fms.pump.nozzle'
    _description = 'Fuel Pump Nozzle'
    _order = 'pump_id, order, letter'

    # ── Identity ──────────────────────────────────────────────────────
    pump_id   = fields.Many2one('fms.pump', 'Pump', required=True, ondelete='cascade')
    name      = fields.Char('Nozzle Label', required=True)
    letter    = fields.Char('Letter', required=True,
                             help="Single letter or number identifying this nozzle on the pump (A, B, 1, 2…).")
    order     = fields.Integer('Display Order', required=True, default=1)
    product_id = fields.Many2one(
        'product.product', 'Fuel Product', required=True,
        domain=[('fms_is_fuel', '=', True)],
    )
    active = fields.Boolean(default=True)

    # ── Lifecycle state ───────────────────────────────────────────────
    state = fields.Selection([
        ('draft',        'Draft'),
        ('initialized',  'Initialized'),
        ('active',       'Active'),
    ], default='draft', string='Status', readonly=True, copy=False)

    # ── Initialization readings (entered once when nozzle is commissioned) ──
    init_elec_volume = fields.Float(
        'Opening Elec Volume (L)', digits=(16, 2),
        help="Electronic totalizer volume reading at commissioning.",
    )
    init_elec_cash = fields.Float(
        'Opening Elec Cash (KES)', digits=(16, 2),
        help="Electronic cash totalizer reading at commissioning.",
    )
    init_mech_volume = fields.Float(
        'Opening Mech Volume (L)', digits=(16, 2),
        help="Mechanical totalizer volume reading at commissioning.",
    )
    init_date = fields.Date(
        'Initialization Date', help="Date the nozzle was commissioned.",
    )
    init_shift_id = fields.Many2one(
        'fms.shift', 'Initialization Shift',
        help="Shift during which the nozzle was commissioned.",
        ondelete='set null',
    )

    # ── Current meter positions (updated by shift close) ─────────────
    current_elec_volume = fields.Float(
        'Current Elec Volume (L)', digits=(16, 2), readonly=True,
        help="Latest closing electronic volume reading. Auto-updated on shift close.",
    )
    current_elec_cash = fields.Float(
        'Current Elec Cash (KES)', digits=(16, 2), readonly=True,
        help="Latest closing electronic cash reading. Auto-updated on shift close.",
    )
    current_mech_volume = fields.Float(
        'Current Mech Volume (L)', digits=(16, 2), readonly=True,
        help="Latest closing mechanical reading. Auto-updated on shift close.",
    )

    # ── Actions ───────────────────────────────────────────────────────

    def action_initialize(self):
        """Enter the three opening meter readings and mark as initialized."""
        for nozzle in self:
            if nozzle.state != 'draft':
                raise ValidationError(
                    f"Nozzle '{nozzle.name}' is already {nozzle.state}."
                )
            if not nozzle.init_date:
                raise ValidationError("Please set an Initialization Date before initializing.")
            if nozzle.init_elec_volume < 0 or nozzle.init_elec_cash < 0 or nozzle.init_mech_volume < 0:
                raise ValidationError("Opening meter readings cannot be negative.")
            # Copy init readings to current positions
            nozzle.write({
                'state': 'initialized',
                'current_elec_volume': nozzle.init_elec_volume,
                'current_elec_cash':   nozzle.init_elec_cash,
                'current_mech_volume': nozzle.init_mech_volume,
            })

    def action_activate(self):
        """Mark nozzle as active — test passed, ready for shift recording."""
        for nozzle in self:
            if nozzle.state != 'initialized':
                raise ValidationError(
                    f"Nozzle must be initialized before activation. Current state: {nozzle.state}."
                )
            nozzle.write({'state': 'active'})

    def action_reset_draft(self):
        """Reset to draft (e.g. wrong readings entered)."""
        for nozzle in self:
            nozzle.write({
                'state': 'draft',
                'current_elec_volume': 0.0,
                'current_elec_cash':   0.0,
                'current_mech_volume': 0.0,
            })

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
