"""
fms_shift.py — Shift state machine and Odoo model extensions

One shift = one period of operation at the forecourt (Day / Evening / Night).
All meter readings, dip readings, and attendant cash entries live as child records.

State machine: draft → open → closing → closed

Reference: FMS_Complete_Specification_Technical_Guide.md, Sections 7 & 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Odoo core model extensions
# ---------------------------------------------------------------------------

class StockLocationFMS(models.Model):
    """Extend stock.location to mark fuel tanks and link their product."""

    _inherit = 'stock.location'

    fms_is_fuel_tank = fields.Boolean('Is Fuel Tank', default=False)
    fms_fuel_product_id = fields.Many2one(
        'product.product', 'Fuel Product in Tank',
        domain=[('fms_is_fuel', '=', True)],
    )


class ProductProductFMS(models.Model):
    """Extend product.product with fuel-specific accounting fields."""

    _inherit = 'product.product'

    fms_is_fuel = fields.Boolean('Is Fuel Product', default=False)
    fms_cogs_account_id = fields.Many2one('account.account', 'Fuel COGS Account')
    fms_revenue_account_id = fields.Many2one('account.account', 'Fuel Revenue Account')


class HREmployeeFMS(models.Model):
    """Extend hr.employee to flag forecourt attendants."""

    _inherit = 'hr.employee'

    fms_is_attendant = fields.Boolean('Is Forecourt Attendant', default=False)
    fms_pumps_assigned = fields.Many2many(
        'fms.pump', string='Assigned Pumps',
    )


# ---------------------------------------------------------------------------
# Main shift model
# ---------------------------------------------------------------------------

class FMSShift(models.Model):
    """
    Orchestrates a single forecourt shift.

    Acts as the root record for all readings, cash entries, and audit logs
    for one operational period (Day / Evening / Night).
    """

    _name = 'fms.shift'
    _description = 'Forecourt Shift'
    _order = 'date DESC, label'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    date = fields.Date('Shift Date', required=True, default=fields.Date.today)
    label = fields.Selection([
        ('1_day',     '1. Day (06:00–14:00)'),
        ('2_evening', '2. Evening (14:00–22:00)'),
        ('3_night',   '3. Night (22:00–06:00)'),
    ], string='Shift Period', required=True)

    supervisor_id = fields.Many2one('hr.employee', 'Supervisor', required=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        required=True, default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    state = fields.Selection([
        ('draft',   'Draft'),
        ('open',    'Open'),
        ('closing', 'Closing'),
        ('closed',  'Closed'),
    ], string='Status', default='draft', readonly=True, copy=False)

    # ------------------------------------------------------------------
    # Timestamps & tracking
    # ------------------------------------------------------------------

    opening_meter_date = fields.Datetime('Opened At', readonly=True, copy=False)
    opening_meter_user_id = fields.Many2one(
        'res.users', 'Opened By', readonly=True, copy=False,
    )
    closing_meter_date = fields.Datetime('Closed At', readonly=True, copy=False)
    closing_meter_user_id = fields.Many2one(
        'res.users', 'Closed By', readonly=True, copy=False,
    )

    # ------------------------------------------------------------------
    # Child tables
    # ------------------------------------------------------------------

    meter_entry_ids = fields.One2many('fms.shift.meter.entry', 'shift_id', 'Meter Entries')
    dip_entry_ids = fields.One2many('fms.shift.dip.entry', 'shift_id', 'Dip Entries')
    attendant_cash_ids = fields.One2many(
        'fms.shift.attendant.cash', 'shift_id', 'Attendant Cash',
    )
    product_sales_ids = fields.One2many(
        'fms.shift.product.sales', 'shift_id', 'Product Sales',
        help="Computed rollup of meter entries per product. Refreshed on save.",
    )
    residual_allocation_ids = fields.One2many(
        'fms.shift.residual.allocation', 'shift_id', 'Residual Allocations',
    )

    # ------------------------------------------------------------------
    # Summary computed fields
    # ------------------------------------------------------------------

    total_meter_sales = fields.Float(
        'Total Meter Sales (KES)', compute='_compute_totals', store=True, digits=(16, 2),
    )
    total_reported_sales = fields.Float(
        'Total Reported Sales (KES)', compute='_compute_totals', store=True, digits=(16, 2),
    )
    fc_cash_balance = fields.Float(
        'FC Cash Balance (KES)', compute='_compute_totals', store=True, digits=(16, 2),
        help="Total Reported Sales minus Total Meter Sales. Must be 0 to close.",
    )

    @api.depends(
        'meter_entry_ids.amount_elec',
        'attendant_cash_ids.reported_sales',
    )
    def _compute_totals(self):
        for shift in self:
            shift.total_meter_sales = sum(shift.meter_entry_ids.mapped('amount_elec'))
            shift.total_reported_sales = sum(shift.attendant_cash_ids.mapped('reported_sales'))
            shift.fc_cash_balance = shift.total_reported_sales - shift.total_meter_sales

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    notes = fields.Text('Supervisor Notes')

    # ------------------------------------------------------------------
    # Product sales rollup
    # ------------------------------------------------------------------

    def action_refresh_product_sales(self):
        """Re-aggregate meter entries into product sales summary lines."""
        for shift in self:
            shift._refresh_product_sales()

    def _refresh_product_sales(self):
        """
        Delete existing product_sales_ids and rebuild from meter_entry_ids.
        Called explicitly by the supervisor button or on shift close.
        """
        self.ensure_one()
        self.product_sales_ids.unlink()

        # Group meter entries by product
        by_product = {}
        for entry in self.meter_entry_ids:
            if not entry.product_id:
                continue
            pid = entry.product_id.id
            if pid not in by_product:
                by_product[pid] = {'qty_elec': 0.0, 'qty_man': 0.0, 'amount': 0.0}
            by_product[pid]['qty_elec'] += entry.qty_sold_elec
            by_product[pid]['qty_man'] += entry.qty_sold_man
            by_product[pid]['amount'] += entry.amount_elec

        for product_id, totals in by_product.items():
            self.env['fms.shift.product.sales'].create({
                'shift_id': self.id,
                'product_id': product_id,
                'qty_sold_elec': totals['qty_elec'],
                'qty_sold_man': totals['qty_man'],
                'amount_elec': totals['amount'],
            })

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------

    @api.depends('date', 'label')
    def _compute_display_name(self):
        label_map = dict(self._fields['label'].selection)
        for shift in self:
            period = label_map.get(shift.label, shift.label or '')
            shift.display_name = f"{shift.date} — {period}"

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('company_id', self.env.company.id)
        return super().create(vals_list)

    def unlink(self):
        if any(s.state == 'closed' for s in self):
            raise ValidationError(
                "Closed shifts cannot be deleted — they are part of the audit trail."
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def action_open_shift(self):
        """Move Draft → Open and stamp opening time."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                f"Cannot open a shift that is already '{self.state}'."
            )
        self.write({
            'state': 'open',
            'opening_meter_date': fields.Datetime.now(),
            'opening_meter_user_id': self.env.user.id,
        })

    def action_start_closing(self):
        """Move Open → Closing (supervisor initiates close process)."""
        self.ensure_one()
        if self.state != 'open':
            raise ValidationError(
                f"Cannot start closing a shift that is '{self.state}'."
            )
        self.write({
            'state': 'closing',
            'closing_meter_date': fields.Datetime.now(),
            'closing_meter_user_id': self.env.user.id,
        })

    def action_close_shift(self):
        """
        Move Closing → Closed after all hard gates pass.

        Hard gate checks and GL posting are added in FMS-005 and FMS-006.
        """
        self.ensure_one()
        if self.state != 'closing':
            raise ValidationError(
                f"Cannot close a shift that is '{self.state}'. "
                "Use 'Start Closing' first."
            )
        # FMS-006: hard gate validation goes here
        # FMS-005: GL journal posting goes here
        self.write({'state': 'closed'})
