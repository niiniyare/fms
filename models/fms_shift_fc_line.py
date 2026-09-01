"""
fms_shift_fc_line.py — Non-fuel forecourt stock and service lines per shift.

One row per product per attendant per shift.

Goods lines: opening_qty (from stock.quant snapshot) + delivery_qty - closing_qty = qty_sold
Service lines: attendant enters amount directly.

Formula mirrors fuel dip:
    fuel:    dispensed  = opening_dip + delivery - closing_dip
    product: qty_sold   = opening_qty + delivery_qty - closing_qty
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError


class FmsShiftFcLine(models.Model):
    _name = 'fms.shift.fc.line'
    _description = 'Non Fuel Sales Line'
    _order = 'shift_id, attendant_id, line_type, product_id'

    shift_id = fields.Many2one(
        'fms.shift', 'Shift', required=True, ondelete='cascade', index=True,
    )
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True,
        domain=[('fms_is_attendant', '=', True)],
    )
    product_id = fields.Many2one(
        'product.product', 'Product / Service', required=True,
        domain=[('fms_is_fuel', '=', False)],
    )
    line_type = fields.Selection(
        [('goods', 'Goods'), ('service', 'Service')],
        'Type', required=True, default='goods',
        help="Auto-set from product type. Goods: qty tracked. Service: amount entered directly.",
    )

    # ── Goods fields ─────────────────────────────────────────────────────────

    opening_qty = fields.Float(
        'Opening (units)', digits=(16, 3),
        help="Snapshotted from stock.quant at forecourt location when shift opens. "
             "Editable by supervisor before shift validates.",
    )
    delivery_qty = fields.Float(
        'Received', digits=(16, 3), default=0.0,
        help="Units delivered/restocked to the forecourt during this shift.",
    )
    closing_qty = fields.Float(
        'Closing (units)', digits=(16, 3),
        help="Physical count by attendant at end of shift.",
    )
    qty_sold = fields.Float(
        'Qty Sold', digits=(16, 3),
        compute='_compute_qty_sold', store=True,
        help="opening_qty + delivery_qty − closing_qty",
    )
    price_unit = fields.Float(
        'Unit Price', digits=(16, 2),
        help="Fetched from pricelist effective on shift date. Editable by supervisor.",
    )

    # ── Service field ─────────────────────────────────────────────────────────

    amount = fields.Float(
        'Amount', digits=(16, 2),
        help="Service only — enter collected amount directly.",
    )

    # ── Unified output ────────────────────────────────────────────────────────

    sales_amount = fields.Float(
        'Sales Amount', digits=(16, 2),
        compute='_compute_sales_amount', store=True,
        help="Goods: qty_sold × price_unit. Service: amount.",
    )

    # ── Company (for multi-company safety) ───────────────────────────────────

    company_id = fields.Many2one(
        related='shift_id.company_id', store=True, readonly=True,
    )

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends('opening_qty', 'delivery_qty', 'closing_qty', 'line_type')
    def _compute_qty_sold(self):
        for line in self:
            if line.line_type == 'goods':
                line.qty_sold = line.opening_qty + line.delivery_qty - line.closing_qty
            else:
                line.qty_sold = 0.0

    @api.depends('line_type', 'qty_sold', 'price_unit', 'amount')
    def _compute_sales_amount(self):
        for line in self:
            if line.line_type == 'goods':
                line.sales_amount = line.qty_sold * line.price_unit
            else:
                line.sales_amount = line.amount

    # ── Onchange: auto-set line_type + price from product ────────────────────

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if not line.product_id:
                continue
            p = line.product_id
            line.line_type = 'service' if p.detailed_type == 'service' else 'goods'
            line.price_unit = self._get_fc_price(p, line.shift_id)

    # ── Price helper ──────────────────────────────────────────────────────────

    def _get_fc_price(self, product, shift):
        """Pricelist price effective on shift.date. Falls back to list_price."""
        if not product or not shift:
            return product.list_price if product else 0.0
        pricelist = shift.company_id.property_product_pricelist
        if pricelist:
            try:
                price = pricelist._get_product_price(product, 1.0, date=shift.date)
                if price:
                    return price
            except Exception:
                pass
        return product.list_price or 0.0

    # ── Immutability: block edits when shift is closing/closed ────────────────

    def write(self, vals):
        for line in self:
            if line.shift_id.state in ('closing', 'closed'):
                raise UserError(
                    f"Shift '{line.shift_id.display_name}' is {line.shift_id.state}. "
                    "Non Fuel Sales lines cannot be modified."
                )
        return super().write(vals)

    def unlink(self):
        for line in self:
            if line.shift_id.state in ('closing', 'closed'):
                raise UserError(
                    f"Shift '{line.shift_id.display_name}' is {line.shift_id.state}. "
                    "Cannot delete Non Fuel Sales lines."
                )
        return super().unlink()

    # ── Constraint: company consistency ──────────────────────────────────────

    @api.constrains('shift_id', 'company_id')
    def _check_company(self):
        for line in self:
            if line.shift_id and line.shift_id.company_id != line.company_id:
                raise ValidationError(
                    "FC line company must match shift company."
                )
