"""
fms_price_period.py — EPRA price period model (build order 0)

One record per EPRA gazette revision.  Used as a first-class date preset
("This price period") on every report and as a join key for margin reports.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSPricePeriod(models.Model):
    _name = 'fms.price.period'
    _description = 'EPRA Price Period'
    _order = 'date_start desc'

    name = fields.Char(
        'Period Name', compute='_compute_name', store=True,
        help="Auto-generated from gazette ref and dates.",
    )
    date_start = fields.Date('Effective From', required=True)
    date_end   = fields.Date('Effective To',   required=True)
    gazette_ref = fields.Char(
        'Gazette Reference', required=True,
        help="EPRA notice reference number, e.g. LN 112/2026.",
    )
    region = fields.Selection([
        ('nairobi',   'Nairobi'),
        ('machakos',  'Machakos / Maanzoni'),
        ('mombasa',   'Mombasa'),
        ('kisumu',    'Kisumu'),
        ('nakuru',    'Nakuru'),
    ], string='Region', required=True, default='machakos',
        help="EPRA caps differ by region — Machakos and Nairobi are separate.",
    )
    pricelist_id = fields.Many2one(
        'product.pricelist', 'Pricelist Version',
        help="Link to the Odoo pricelist that was active during this period.",
    )
    notes = fields.Text('Notes')
    active = fields.Boolean(default=True)

    # ── Price lines (one row per regulated product) ───────────────────────
    price_line_ids = fields.One2many(
        'fms.price.period.line', 'period_id', 'Regulated Prices',
    )

    @api.depends('gazette_ref', 'date_start', 'region')
    def _compute_name(self):
        for p in self:
            region = dict(self._fields['region'].selection).get(p.region, '')
            date   = p.date_start.strftime('%b %Y') if p.date_start else ''
            p.name = f"{p.gazette_ref} · {region} · {date}" if p.gazette_ref else date

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for p in self:
            if p.date_start and p.date_end and p.date_start > p.date_end:
                raise ValidationError("Effective From must be before Effective To.")

    @api.constrains('date_start', 'date_end', 'region')
    def _check_no_overlap(self):
        for p in self:
            domain = [
                ('region', '=', p.region),
                ('id', '!=', p.id),
                ('date_start', '<=', p.date_end),
                ('date_end',   '>=', p.date_start),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    f"This period overlaps an existing period for region {p.region}."
                )

    def current_period(self, region='machakos'):
        """Return the active price period for today, or False."""
        today = fields.Date.today()
        return self.search([
            ('region', '=', region),
            ('date_start', '<=', today),
            ('date_end',   '>=', today),
            ('active', '=', True),
        ], limit=1)


class FMSPricePeriodLine(models.Model):
    _name = 'fms.price.period.line'
    _description = 'EPRA Regulated Price Line'
    _order = 'period_id desc, product_id'

    period_id  = fields.Many2one('fms.price.period', 'Period', required=True, ondelete='cascade')
    product_id = fields.Many2one(
        'product.product', 'Product', required=True,
        domain=[('fms_is_fuel', '=', True)],
    )
    epra_cap   = fields.Float('EPRA Cap (KES/L)', required=True, digits=(16, 4))
    pump_price = fields.Float('Pump Price (KES/L)', required=True, digits=(16, 4))
    landed_cost = fields.Float('Landed Cost (KES/L)', digits=(16, 4),
                               help="AVCO landed cost at start of period — for F11.")
    margin_per_litre = fields.Float(
        'Margin (KES/L)', compute='_compute_margin', store=True, digits=(16, 4),
    )

    @api.depends('pump_price', 'landed_cost')
    def _compute_margin(self):
        for line in self:
            line.margin_per_litre = line.pump_price - line.landed_cost
