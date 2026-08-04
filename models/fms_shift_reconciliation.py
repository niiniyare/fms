"""
fms_shift_reconciliation.py — Computed product sales summary and residual allocations

Models:
  - fms.shift.product.sales  — computed rollup of meter sales per product per shift
  - fms.shift.residual.allocation — auto-calculated residual reallocation lines

fms.shift.product.sales is read-only and re-computed whenever meter entries change.
fms.shift.residual.allocation is populated by the residual algorithm (FMS-003).

Reference: FMS_Complete_Specification_Technical_Guide.md, Sections 7.1 & 8.1
"""

from odoo import models, fields, api


class FMSShiftProductSales(models.Model):
    """
    Per-product sales summary for a shift.

    Aggregated from fms.shift.meter.entry lines.  Accounted amounts are
    queried live from POS order lines when POS sessions are linked.
    Residual fields are written by the residual allocation algorithm
    (_calculate_residuals on fms.shift).

    Terminology (Spec Section 7.1):
      meter_amount   = what the pump physically dispensed (source of truth)
      accounted_amount = what POS recorded as sold for this product
      residual        = meter - accounted
        < 0  → OVER-REPORTED in POS (attendant lumped other products here)
        > 0  → UNDER-REPORTED in POS (product not credited in POS)
        = 0  → balanced
    """

    _name = 'fms.shift.product.sales'
    _description = 'Shift Product Sales Summary'
    _order = 'product_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Product', required=True, readonly=True)

    # ── Meter (from pump readings) ────────────────────────────────────────────
    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', digits=(16, 2), readonly=True,
        help="Sum of closing − opening electronic meter readings across all nozzles.",
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', digits=(16, 2), readonly=True,
    )
    amount_elec = fields.Float(
        'Meter Amount (KES)', digits=(16, 2), readonly=True,
        help="qty_sold_elec × product list_price.",
    )

    # ── Accounted (from POS order lines — live, non-stored) ──────────────────
    accounted_qty = fields.Float(
        'POS Qty (L)', compute='_compute_accounted', digits=(16, 2),
        help="Quantity from POS order lines for this product across linked sessions.",
    )
    accounted_amount = fields.Float(
        'POS Amount (KES)', compute='_compute_accounted', digits=(16, 2),
        help="Revenue from POS order lines for this product across linked sessions.",
    )

    @api.depends('shift_id.pos_session_ids', 'product_id')
    def _compute_accounted(self):
        for rec in self:
            sessions = rec.shift_id.pos_session_ids
            if not sessions or not rec.product_id:
                rec.accounted_qty    = 0.0
                rec.accounted_amount = 0.0
                continue
            lines = self.env['pos.order.line'].search([
                ('order_id.session_id', 'in', sessions.ids),
                ('product_id', '=', rec.product_id.id),
            ])
            rec.accounted_qty    = sum(lines.mapped('qty'))
            rec.accounted_amount = sum(lines.mapped('price_subtotal_incl'))

    # ── Residual (written by _calculate_residuals, read-only here) ───────────
    residual_qty = fields.Float(
        'Residual Qty (L)', digits=(16, 2), readonly=True,
        help="meter_qty − accounted_qty. "
             "Positive = under-reported; Negative = over-reported.",
    )
    residual_amount = fields.Float(
        'Residual Amount (KES)', digits=(16, 2), readonly=True,
        help="meter_amount − accounted_amount.",
    )
    residual_type = fields.Selection([
        ('none',  'Balanced'),
        ('over',  'Over-reported'),
        ('under', 'Under-reported'),
    ], string='Status', readonly=True, default='none')


class FMSShiftResidualAllocation(models.Model):
    """
    One line of the auto-calculated residual reallocation for a shift.

    The residual algorithm (FMS-003) detects when a product shows a gap
    between what the meter dispensed and what was reported, and allocates
    that gap to another product (e.g., Diesel surplus → Carwash).

    Each line records:
      - source_product_id: the product that was over-reported
      - target_product_id: the product that should absorb the surplus
      - qty_litres / amount: the reallocation quantum
    """

    _name = 'fms.shift.residual.allocation'
    _description = 'Shift Residual Allocation'
    _order = 'shift_id, source_product_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    source_product_id = fields.Many2one(
        'product.product', 'From Product',
        help="Product that was over-reported (e.g., Diesel).",
    )
    target_product_id = fields.Many2one(
        'product.product', 'To Product',
        help="Product that absorbs the surplus (e.g., Carwash).",
    )

    qty_litres = fields.Float('Qty (L)', digits=(16, 2))
    amount = fields.Float('Amount (KES)', digits=(16, 2))

    journal_entry_id = fields.Many2one(
        'account.move', 'Journal Entry',
        readonly=True,
        help="GL entry posted on shift close (FMS-005).",
    )

    notes = fields.Char('Allocation Notes')
