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
    Read-only rollup: total litres and amount sold per product in a shift.

    Aggregated from fms.shift.meter.entry lines.  The supervisor and
    accountant use this to verify that what the pumps dispensed matches
    what attendants reported.
    """

    _name = 'fms.shift.product.sales'
    _description = 'Shift Product Sales Summary'
    _order = 'product_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', 'Product', required=True, readonly=True)

    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', digits=(16, 2), readonly=True,
        help="Sum of closing − opening electronic meter readings across all nozzles for this product.",
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', digits=(16, 2), readonly=True,
    )
    amount_elec = fields.Float(
        'Amount (KES)', digits=(16, 2), readonly=True,
        help="qty_sold_elec × product list_price.",
    )

    residual_qty = fields.Float(
        'Residual Qty (L)', digits=(16, 2), readonly=True,
        help="Positive = under-reported (gap to fill). Negative = over-reported.",
    )
    residual_amount = fields.Float(
        'Residual Amount (KES)', digits=(16, 2), readonly=True,
    )


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
