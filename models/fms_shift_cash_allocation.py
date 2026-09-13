"""
fms_shift_cash_allocation.py — Per-product cash allocation for shift reconciliation.

Problem:
  Attendants handle multiple products (Diesel, Petrol, Carwash…).
  They declare one lump cash figure and one lump set of digital amounts.
  Management needs to know which product each payment mode covered.

Algorithm (called at shift close via fms.shift._compute_cash_allocation):
  For each attendant:
    1. Compute per-product revenue from their assigned nozzle meter entries.
    2. Allocate digital payments (M-Pesa + Card + AR) proportionally by revenue share.
    3. Allocate declared cash against remaining product revenue in priority order:
         fuel products by pump sequence first, then non-fuel alphabetically.
       a. Take min(remaining_cash, remaining_product_revenue).
       b. Create an allocation record.
       c. Move to next product with residual cash.

Invariant:
  sum(allocation.cash_amount where attendant=A) ≤ attendant.cash_collected
  No GL entries are created — this is a reconciliation view only.
  Revenue is already posted by action_close_shift. Allocations do NOT post again.

Reference: FMS_Complete_Specification_Technical_Guide.md §7.1, §8.1
"""

from odoo import models, fields, api
from odoo.tools.float_utils import float_compare, float_round


class FMSShiftCashAllocation(models.Model):
    """
    One row = one product's share of an attendant's payments for a shift.

    Created/replaced by fms.shift._compute_cash_allocation() on shift close.
    Read-only after creation — regenerate by calling _compute_cash_allocation().
    """

    _name = 'fms.shift.cash.allocation'
    _description = 'Shift Cash Allocation per Product'
    _order = 'shift_id, attendant_id, product_priority, product_id'
    _rec_name = 'product_id'

    shift_id = fields.Many2one(
        'fms.shift', 'Shift', required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', related='shift_id.company_id', store=True, readonly=True,
    )
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True, readonly=True,
    )
    product_id = fields.Many2one(
        'product.product', 'Product', required=True, readonly=True,
    )
    is_fuel = fields.Boolean(
        'Fuel', related='product_id.fms_is_fuel', store=True, readonly=True,
    )
    product_priority = fields.Integer(
        'Sort Priority', default=0, readonly=True,
        help="Lower = processed first. Fuel products get priority 0, non-fuel get 100.",
    )

    # Revenue for this product from this attendant's nozzles this shift
    product_revenue = fields.Float(
        'Product Revenue', digits=(16, 2), readonly=True,
        help="meter_volume × price for this product, from attendant's assigned nozzles.",
    )
    product_qty = fields.Float(
        'Product Qty (L)', digits=(16, 2), readonly=True,
        help="Liters dispensed from attendant's nozzles for this product.",
    )

    # Share of digital payments allocated to this product (proportional)
    digital_allocated = fields.Float(
        'Digital Allocated', digits=(16, 2), readonly=True,
        help="Share of M-Pesa + Card + AR allocated to this product (proportional by revenue).",
    )

    # Cash coverage after digital deduction
    cash_allocated = fields.Float(
        'Cash Allocated', digits=(16, 2), readonly=True,
        help="Declared cash applied to this product's remaining revenue after digital deduction.",
    )

    # Uncovered residual (positive = under-collected, negative = over-collected)
    uncovered = fields.Float(
        'Uncovered', digits=(16, 2), readonly=True,
        help="product_revenue − digital_allocated − cash_allocated. "
             "Non-zero indicates a shortfall or surplus for this product.",
    )

    currency_id = fields.Many2one(
        'res.currency', related='shift_id.company_id.currency_id', readonly=True,
    )

    def write(self, vals):
        raise models.ValidationError(
            "Cash allocation records are regenerated on shift close and cannot be edited directly."
        )

    def unlink(self):
        # Only the shift close process (via _compute_cash_allocation) may delete these.
        if self.env.context.get('fms_regen_cash_alloc'):
            return super().unlink()
        raise models.ValidationError(
            "Cash allocation records cannot be deleted manually. "
            "They are regenerated automatically on shift close."
        )


class FMSShiftCashAllocationMixin:
    """
    Mixin with the cash allocation algorithm.
    Applied to fms.shift via _inherit in fms_shift.py is impractical for a mixin,
    so the method is defined here and monkey-patched onto fms.shift at module load.

    Instead, we add a new model that inherits fms.shift to add the method cleanly.
    """


def _compute_cash_allocation(shift):
    """
    Compute and persist cash allocations for all attendants on this shift.

    This is a module-level function called from fms.shift. It operates on a single
    shift record and regenerates all fms.shift.cash.allocation rows.

    Safe to call multiple times — existing rows are deleted and recreated.
    Does NOT post any GL entries. Revenue is already posted separately.
    """
    Alloc = shift.env['fms.shift.cash.allocation']
    rounding = shift.company_id.currency_id.rounding or 0.01

    # Delete existing rows for this shift (idempotency)
    Alloc.with_context(fms_regen_cash_alloc=True).search(
        [('shift_id', '=', shift.id)]
    ).with_context(fms_regen_cash_alloc=True).unlink()

    for cash_line in shift.attendant_cash_ids:
        attendant = cash_line.attendant_id
        if not attendant:
            continue

        # ── Step 1: per-product revenue for this attendant ────────────────────
        # Meter entries for nozzles assigned to this attendant
        attendant_entries = shift.meter_entry_ids.filtered(
            lambda e: e.attendant_id == attendant and e.product_id
        )
        if not attendant_entries:
            continue

        # Group by product: {product: (qty, revenue)}
        product_data = {}
        for entry in attendant_entries:
            pid = entry.product_id.id
            qty = entry.qty_sold_elec or 0.0
            rev = entry.amount_elec or 0.0
            if pid not in product_data:
                product_data[pid] = {'product': entry.product_id, 'qty': 0.0, 'revenue': 0.0}
            product_data[pid]['qty'] += qty
            product_data[pid]['revenue'] += rev

        if not product_data:
            continue

        total_revenue = sum(d['revenue'] for d in product_data.values())

        # ── Step 2: sort products by priority (fuel first, then by name) ─────
        def sort_key(item):
            prod = item['product']
            fuel_priority = 0 if prod.fms_is_fuel else 100
            return (fuel_priority, (prod.name or '').lower())

        sorted_products = sorted(product_data.values(), key=sort_key)

        # ── Step 3: allocate digital payments in priority order ───────────────
        # Same priority as cash: fuel first. This matches the spec where 980L of
        # Diesel is "already allocated" to digital (not spread proportionally).
        digital_total = float_round(
            min(
                (cash_line.mpesa_amount or 0.0)
                + (cash_line.card_amount or 0.0)
                + (cash_line.ar_amount or 0.0)
                + (cash_line.direct_sales_digital or 0.0)
                + (cash_line.direct_sales_credit or 0.0),
                total_revenue,
            ),
            precision_rounding=rounding,
        )

        digital_remaining = digital_total
        for d in sorted_products:
            digital_for_product = float_round(
                min(digital_remaining, d['revenue']),
                precision_rounding=rounding,
            )
            d['digital'] = digital_for_product
            d['remaining'] = float_round(
                max(0.0, d['revenue'] - digital_for_product),
                precision_rounding=rounding,
            )
            digital_remaining = float_round(
                digital_remaining - digital_for_product,
                precision_rounding=rounding,
            )

        # ── Step 4: allocate declared cash to remaining in priority order ─────
        cash_remaining = float_round(
            max(0.0, cash_line.cash_collected or 0.0),
            precision_rounding=rounding,
        )

        alloc_rows = []
        for d in sorted_products:
            prod = d['product']
            fuel_priority = 0 if prod.fms_is_fuel else 100

            cash_for_product = float_round(
                min(cash_remaining, d['remaining']),
                precision_rounding=rounding,
            )
            cash_remaining = float_round(
                cash_remaining - cash_for_product,
                precision_rounding=rounding,
            )

            uncovered = float_round(
                d['revenue'] - d['digital'] - cash_for_product,
                precision_rounding=rounding,
            )

            alloc_rows.append({
                'shift_id': shift.id,
                'attendant_id': attendant.id,
                'product_id': prod.id,
                'product_priority': fuel_priority,
                'product_revenue': d['revenue'],
                'product_qty': d['qty'],
                'digital_allocated': d['digital'],
                'cash_allocated': cash_for_product,
                'uncovered': uncovered,
            })

        if alloc_rows:
            Alloc.sudo().create(alloc_rows)
