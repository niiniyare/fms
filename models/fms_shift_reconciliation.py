"""
fms_shift_reconciliation.py — Product sales summary and residual allocations

Two independent reconciliation dimensions per product per shift:

  VOLUME SIDE (inventory):
    meter_volume (liters dispensed per pump)  vs  accounted_volume (POS liters)
    volume_residual = meter_volume − accounted_volume
    Used by: Gate 1, residual allocation algorithm, wetstock reports

  CASH SIDE (revenue):
    elec_cash_sold (KES per cash meter) vs pos_cash_collected (total POS KES)
    cash_residual = elec_cash_sold − pos_cash_collected
    Used by: Gate 2, cash reconciliation report
    NOTE: pos_cash_collected is total POS revenue (all payment modes combined).
    Payment-mode breakdown (cash/mpesa/card/ar) lives at the attendant level.

Reference: FMS_Complete_Specification_Technical_Guide.md, Sections 7.1 & 8.1
"""

from odoo import models, fields, api


class FMSShiftProductSales(models.Model):
    _name = 'fms.shift.product.sales'
    _description = 'Shift Product Sales Summary'
    _order = 'product_id'

    shift_id   = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Product', required=True, readonly=True)

    # ── VOLUME SIDE — inventory reconciliation ────────────────────────────────
    meter_volume = fields.Float(
        'Meter Volume (L)', digits=(16, 2), readonly=True,
        help="Sum of qty_sold_elec across all nozzles for this product.",
    )
    meter_volume_man = fields.Float(
        'Manual Meter Volume (L)', digits=(16, 2), readonly=True,
        help="Sum of qty_sold_man across all nozzles (backup reading).",
    )
    price_at_close = fields.Float(
        'Price at Close (/L)', digits=(16, 4), readonly=True,
        help="Product list price at the time of refresh — used for meter_revenue.",
    )
    meter_revenue = fields.Float(
        'Meter Revenue', compute='_compute_volume', store=True, digits=(16, 2),
        help="meter_volume × price_at_close. Theoretical value if all volume was sold at list price.",
    )
    accounted_volume = fields.Float(
        'POS Volume (L)', compute='_compute_accounted', digits=(16, 2),
        help="Liters from POS order lines for this product across linked sessions.",
    )
    volume_residual = fields.Float(
        'Volume Residual (L)', compute='_compute_volume', store=True, digits=(16, 2),
        help="meter_volume − accounted_volume. "
             "+ve = under-invoiced (meter dispensed more than POS recorded). "
             "-ve = over-invoiced (POS recorded more than meter dispensed).",
    )
    allocated_volume = fields.Float(
        'Allocated Volume (L)', digits=(16, 2), readonly=True,
        help="Liters reallocated TO this product by the residual algorithm.",
    )
    allocated_amount = fields.Float(
        'Allocated Amount', digits=(16, 2), readonly=True,
        help="allocated_volume × price_at_close (for GL posting).",
    )

    # ── CASH SIDE — revenue reconciliation ───────────────────────────────────
    elec_cash_sold = fields.Float(
        'Cash Meter', digits=(16, 2), readonly=True,
        help="Sum of elec_cash_sold across all nozzles for this product. "
             "What the pump's electronic cash register says was collected.",
    )
    pos_cash_collected = fields.Float(
        'POS Total', compute='_compute_accounted', digits=(16, 2),
        help="Total POS revenue for this product (all payment modes). "
             "Payment-mode breakdown lives at the attendant cash level.",
    )
    cash_residual = fields.Float(
        'Cash Residual', compute='_compute_cash_residual', store=True, digits=(16, 2),
        help="elec_cash_sold − pos_cash_collected. "
             "+ve = pump charged more than POS recorded (pump over-charged or POS missed a sale). "
             "-ve = POS recorded more than pump charged (price mismatch or POS error).",
    )

    # ── STATUS ────────────────────────────────────────────────────────────────
    residual_type = fields.Selection([
        ('none',  'Balanced'),
        ('over',  'Over-invoiced (POS > meter)'),
        ('under', 'Under-invoiced (meter > POS)'),
    ], string='Volume Status', readonly=True, default='none')

    # ── Legacy aliases (kept for backward-compat with existing views/tests) ──
    qty_sold_elec = fields.Float(related='meter_volume',   string='Qty Sold Elec (L)')
    qty_sold_man  = fields.Float(related='meter_volume_man', string='Qty Sold Manual (L)')
    amount_elec   = fields.Float(related='meter_revenue',  string='Meter Revenue [alias]')
    residual_qty  = fields.Float(related='volume_residual', string='Residual Qty (L)')
    residual_amount = fields.Float(related='cash_residual', string='Residual Amount')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('meter_volume', 'price_at_close', 'accounted_volume')
    def _compute_volume(self):
        for rec in self:
            rec.meter_revenue   = rec.meter_volume * (rec.price_at_close or 0.0)
            rec.volume_residual = rec.meter_volume - rec.accounted_volume

    @api.depends('elec_cash_sold', 'pos_cash_collected')
    def _compute_cash_residual(self):
        for rec in self:
            rec.cash_residual = rec.elec_cash_sold - rec.pos_cash_collected

    @api.depends('shift_id.pos_session_ids', 'product_id')
    def _compute_accounted(self):
        for rec in self:
            sessions = rec.shift_id.pos_session_ids
            if not sessions or not rec.product_id:
                rec.accounted_volume   = 0.0
                rec.pos_cash_collected = 0.0
                continue
            lines = self.env['pos.order.line'].search([
                ('order_id.session_id', 'in', sessions.ids),
                ('product_id', '=', rec.product_id.id),
            ])
            rec.accounted_volume   = sum(lines.mapped('qty'))
            rec.pos_cash_collected = sum(lines.mapped('price_subtotal_incl'))


class FMSShiftResidualAllocation(models.Model):
    """
    One line of the residual volume reallocation for a shift.

    Operates on VOLUME only (liters), after both volume and cash gates pass.
    Records how many liters moved from an over-invoiced product to an
    under-invoiced one (e.g., attendant lumped Carwash into Diesel).

    GL entry: DR to_product COGS | CR from_product COGS
    Amount = qty_litres × to_product price_at_close
    """

    _name = 'fms.shift.residual.allocation'
    _description = 'Shift Residual Allocation'
    _order = 'shift_id, source_product_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    source_product_id = fields.Many2one(
        'product.product', 'From Product (Over-invoiced)',
        help="Product that was over-invoiced in POS — meter shows less than POS claimed.",
    )
    target_product_id = fields.Many2one(
        'product.product', 'To Product (Under-invoiced)',
        help="Product that absorbs the surplus — meter shows more than POS recorded.",
    )

    qty_litres = fields.Float('Qty (L)', digits=(16, 2),
                              help="Liters reallocated from source to target.")
    amount = fields.Float('Amount', digits=(16, 2),
                          help="qty_litres × target product price_at_close.")

    journal_entry_id = fields.Many2one(
        'account.move', 'Journal Entry', readonly=True,
        help="GL entry posted on shift close.",
    )
    notes = fields.Char('Notes')
