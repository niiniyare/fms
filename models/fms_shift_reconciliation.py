"""
fms_shift_reconciliation.py — Residual allocation and reconciliation

Handles the residual allocation algorithm:
- Detect gap between meter-reported sales and attendant-reported collections
- Auto-allocate residual to non-fuel products (carwash, LPG, etc.)
- Generate GL journal entries for the reallocation

Full implementation in FMS-003.
"""

from odoo import models, fields, api


class FMSShiftResidualAllocation(models.Model):
    """Auto-calculated residual allocation line for one shift."""

    _name = 'fms.shift.residual.allocation'
    _description = 'Shift Residual Allocation'
    _order = 'shift_id, product_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    source_product_id = fields.Many2one('product.product', 'Source Product (e.g. Diesel)')
    target_product_id = fields.Many2one('product.product', 'Allocated To (e.g. Carwash)')

    qty_litres = fields.Float('Qty (L)', digits=(16, 2))
    amount = fields.Float('Amount (KES)', digits=(16, 2))

    notes = fields.Char('Allocation Notes')
