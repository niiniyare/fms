"""
fms_incident.py — Drive-off & Incident Register (build order 2 / R9)

fms.incident:  one record per event (drive-off, no-pay, spillage, etc.)
On approval the model posts a stock.move to remove the litres from inventory
under an "Incident Loss" location, keeping the stock ledger accurate and
preventing the volume from landing in R3's wetstock variance.
"""

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class FMSIncident(models.Model):
    _name = 'fms.incident'
    _description = 'Drive-off & Incident Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, name desc'
    _rec_name = 'name'

    # ── Identity ──────────────────────────────────────────────────────────
    name = fields.Char(
        'Reference', required=True, copy=False, readonly=True,
        default='New',
    )
    date        = fields.Date('Incident Date', required=True, default=fields.Date.today,
                              tracking=True)
    shift_id    = fields.Many2one('fms.shift', 'Shift', tracking=True,
                                  domain=[('state', 'in', ['open', 'closing', 'closed'])])
    attendant_id = fields.Many2one('hr.employee', 'Attendant on Duty', tracking=True,
                                   domain=[('fms_is_attendant', '=', True)])
    nozzle_id   = fields.Many2one('fms.pump.nozzle', 'Nozzle', tracking=True)
    reported_by = fields.Many2one('res.users', 'Reported By',
                                  default=lambda self: self.env.user, tracking=True)

    # ── Incident classification ───────────────────────────────────────────
    incident_type = fields.Selection([
        ('drive_off',        'Drive-off (fuel taken, no payment)'),
        ('no_pay',           'No-pay (attendant dispute)'),
        ('spillage',         'Spillage / Overflow'),
        ('wrong_fuel',       'Wrong Fuel Dispensed'),
        ('calibration_test', 'Calibration Test'),
        ('own_use',          'Own Use / Internal Transfer'),
        ('transfer',         'Inter-tank Transfer'),
        ('other',            'Other'),
    ], string='Incident Type', required=True, tracking=True)

    # ── Quantities ────────────────────────────────────────────────────────
    product_id  = fields.Many2one(
        'product.product', 'Product',
        domain=[('fms_is_fuel', '=', True)], tracking=True,
    )
    litres      = fields.Float('Litres',    digits=(16, 3), tracking=True)
    unit_price  = fields.Float('Price/L (KES)', digits=(16, 4))
    amount      = fields.Float('Value (KES)', compute='_compute_amount', store=True,
                               digits=(16, 2))

    # ── Evidence ─────────────────────────────────────────────────────────
    plate       = fields.Char('Vehicle Plate / Registration')
    ob_number   = fields.Char('OB Number', help="Police occurrence book reference.")
    description = fields.Text('Description')

    # ── Recovery ─────────────────────────────────────────────────────────
    recovery_status = fields.Selection([
        ('open',         'Open / Unrecovered'),
        ('partial',      'Partially Recovered'),
        ('recovered',    'Fully Recovered'),
        ('written_off',  'Written Off'),
    ], string='Recovery Status', default='open', required=True, tracking=True)
    recovery_notes  = fields.Text('Recovery Notes')
    recovery_amount = fields.Float('Amount Recovered (KES)', digits=(16, 2))

    # ── Workflow ──────────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',    'Draft'),
        ('reported', 'Reported'),
        ('approved', 'Approved'),
        ('closed',   'Closed'),
    ], default='draft', required=True, tracking=True, string='Status')

    approved_by    = fields.Many2one('res.users', 'Approved By', readonly=True, tracking=True)
    approved_date  = fields.Datetime('Approved At', readonly=True)

    # ── GL / Stock link ───────────────────────────────────────────────────
    stock_move_id  = fields.Many2one('stock.move', 'Stock Write-off Move', readonly=True)
    company_id     = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env.company,
    )

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends('litres', 'unit_price')
    def _compute_amount(self):
        for inc in self:
            inc.amount = inc.litres * inc.unit_price

    # ── Sequence ──────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fms.incident') or 'New'
        return super().create(vals_list)

    # ── Workflow actions ──────────────────────────────────────────────────
    def action_report(self):
        """Supervisor confirms the incident is recorded correctly."""
        for inc in self.filtered(lambda r: r.state == 'draft'):
            inc.state = 'reported'

    def action_approve(self):
        """
        Approve the incident.  Posts a stock write-off move so the litres
        leave inventory as an incident loss rather than showing as an
        unexplained R3 variance.
        """
        for inc in self.filtered(lambda r: r.state == 'reported'):
            if inc.litres and inc.product_id:
                inc._post_stock_writeoff()
            inc.approved_by   = self.env.user
            inc.approved_date = fields.Datetime.now()
            inc.state         = 'approved'

    def action_close(self):
        for inc in self.filtered(lambda r: r.state == 'approved'):
            inc.state = 'closed'

    def action_reset_draft(self):
        for inc in self.filtered(lambda r: r.state in ('reported',)):
            inc.state = 'draft'

    # ── Stock write-off ───────────────────────────────────────────────────
    def _post_stock_writeoff(self):
        """
        Create and validate a stock.move from the fuel tank to the virtual
        'Incident Loss' location.  This keeps the stock ledger accurate and
        ensures the loss appears in F12 when valued at AVCO.
        """
        self.ensure_one()

        # Source location: the nozzle's tank, or any fuel tank for this product
        src_location = None
        if self.nozzle_id and self.nozzle_id.pump_id:
            # Try to find the tank from nozzle → pump → site preferences
            tank = self.env['stock.location'].search([
                ('fms_is_fuel_tank', '=', True),
                ('fms_fuel_product_id', '=', self.product_id.id),
            ], limit=1)
            src_location = tank or None

        if not src_location:
            src_location = self.env['stock.location'].search([
                ('fms_is_fuel_tank', '=', True),
                ('fms_fuel_product_id', '=', self.product_id.id),
            ], limit=1)

        if not src_location:
            raise UserError(
                f"No fuel tank found for product {self.product_id.name}. "
                "Cannot post stock write-off."
            )

        # Destination: virtual loss location (create if needed)
        loss_location = self._get_loss_location()

        # Picking type: internal transfer (no receipt/delivery involved)
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        move = self.env['stock.move'].create({
            'name': f"Incident write-off: {self.name} — {self.incident_type}",
            'product_id': self.product_id.id,
            'product_uom_qty': self.litres,
            'product_uom': self.product_id.uom_id.id,
            'location_id': src_location.id,
            'location_dest_id': loss_location.id,
            'company_id': self.company_id.id,
            'picking_type_id': picking_type.id if picking_type else False,
            'origin': self.name,
        })
        move._action_confirm()
        move._action_assign()
        move.quantity = self.litres
        move.picked = True
        move._action_done()
        self.stock_move_id = move

    def _get_loss_location(self):
        """Return (or create) a virtual location for incident losses."""
        Location = self.env['stock.location']
        loss_loc = Location.search([
            ('name', '=', 'Incident Losses'),
            ('usage', '=', 'inventory'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not loss_loc:
            parent = self.env.ref('stock.stock_location_locations_virtual',
                                  raise_if_not_found=False)
            loss_loc = Location.create({
                'name': 'Incident Losses',
                'usage': 'inventory',
                'location_id': parent.id if parent else
                               Location.search([('usage', '=', 'view')], limit=1).id,
                'company_id': self.company_id.id,
            })
        return loss_loc
