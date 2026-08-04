"""
test_fms_003.py — Unit tests for FMS-003: Residual Allocation Algorithm

Tests cover:
  - _run_greedy_allocation (pure algorithm, no DB needed)
  - _calculate_residuals  (ORM integration: meter entries → allocations)
  - Edge cases: balanced, all-under, all-over, multiple products

Run: make odoo-test
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError
from odoo.addons.fms.models.fms_shift import FMSShift


# ---------------------------------------------------------------------------
# Pure algorithm tests (no DB required, use staticmethod directly)
# ---------------------------------------------------------------------------

class TestGreedyAlgorithm(TransactionCase):
    """
    Test _run_greedy_allocation without any ORM involvement.
    Input:  over_reported / under_reported dicts {product_id_int: amount}
    Output: list of (over_pid, under_pid, amount) tuples
    """

    def test_single_match(self):
        """One over-reported exactly covers one under-reported."""
        over  = {1: 7000.0}
        under = {2: 7000.0}
        result = FMSShift._run_greedy_allocation(over, under)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], (1, 2, 7000.0))

    def test_partial_match(self):
        """Over-reported is less than under-reported — partial allocation."""
        over  = {1: 3000.0}
        under = {2: 7000.0}
        result = FMSShift._run_greedy_allocation(over, under)
        self.assertEqual(len(result), 1)
        over_pid, under_pid, amt = result[0]
        self.assertEqual(over_pid, 1)
        self.assertEqual(under_pid, 2)
        self.assertAlmostEqual(amt, 3000.0)

    def test_one_over_many_under(self):
        """One over-reported product absorbs into multiple under-reported."""
        over  = {1: 10000.0}
        under = {2: 6000.0, 3: 5000.0}   # 11k needed, only 10k available
        result = FMSShift._run_greedy_allocation(over, under)
        self.assertEqual(len(result), 2)
        total_allocated = sum(r[2] for r in result)
        self.assertAlmostEqual(total_allocated, 10000.0)

    def test_many_over_one_under(self):
        """Multiple over-reported products fill one under-reported."""
        over  = {1: 3000.0, 2: 4000.0}
        under = {3: 6000.0}
        result = FMSShift._run_greedy_allocation(over, under)
        total_allocated = sum(r[2] for r in result)
        # 3k + 4k = 7k available, 6k needed → 6k allocated total
        self.assertAlmostEqual(total_allocated, 6000.0)

    def test_no_over_no_allocation(self):
        """No over-reported → no allocations regardless of under-reported."""
        result = FMSShift._run_greedy_allocation({}, {3: 5000.0})
        self.assertEqual(result, [])

    def test_no_under_no_allocation(self):
        """No under-reported → no allocations regardless of over-reported."""
        result = FMSShift._run_greedy_allocation({1: 5000.0}, {})
        self.assertEqual(result, [])

    def test_balanced_no_allocation(self):
        result = FMSShift._run_greedy_allocation({}, {})
        self.assertEqual(result, [])

    def test_spec_example(self):
        """
        Walkthrough from Spec Section 7.1 Example:
          Diesel (pid=1) over-reported by 7,200
          UX     (pid=2) under-reported by 7,000
          LPG    (pid=3) under-reported by 5,000
        Expected allocations:
          Diesel → UX  7,000  (UX exhausted first; diesel still has 200)
          Diesel → LPG   200  (remaining diesel goes to LPG)
        """
        over  = {1: 7200.0}
        under = {2: 7000.0, 3: 5000.0}
        result = FMSShift._run_greedy_allocation(over, under)
        # Two allocations
        self.assertEqual(len(result), 2)
        result_map = {(r[0], r[1]): r[2] for r in result}
        # Diesel → UX: 7000 (full UX deficit)
        self.assertAlmostEqual(result_map[(1, 2)], 7000.0)
        # Diesel → LPG: 200 (remaining diesel surplus)
        self.assertAlmostEqual(result_map[(1, 3)], 200.0)

    def test_greedy_sorts_largest_first(self):
        """Largest over-reported product is matched first."""
        over  = {1: 100.0, 2: 5000.0}   # pid=2 is bigger
        under = {3: 4000.0}
        result = FMSShift._run_greedy_allocation(over, under)
        # pid=2 (5000) should match pid=3 (4000) first, leaving 1000 unmatched
        # pid=1 (100) has nothing left to match
        total = sum(r[2] for r in result)
        self.assertAlmostEqual(total, 4000.0)
        # The match must come from pid=2 (bigger over)
        matched_overs = {r[0] for r in result}
        self.assertIn(2, matched_overs)


# ---------------------------------------------------------------------------
# ORM integration tests
# ---------------------------------------------------------------------------

class FMSResidualBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.supervisor = self.env['hr.employee'].create({'name': 'Sup-003'})
        self.diesel = self.env['product.product'].create({
            'name': 'TEST-Diesel-003', 'fms_is_fuel': True, 'list_price': 222.8,
        })
        self.carwash = self.env['product.product'].create({
            'name': 'TEST-Carwash-003', 'fms_is_fuel': False, 'list_price': 500.0,
        })
        self.pump = self.env['fms.pump'].create({'name': 'TEST-RES-UX1', 'order': 99})
        self.nozzle_d = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.diesel.id,
        })

    def _make_open_shift(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-02-01', 'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        return shift

    def _add_meter(self, shift, nozzle, opening=0.0, closing=1000.0):
        return self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': nozzle.pump_id.id,
            'nozzle_id': nozzle.id,
            'opening_elec_volume': opening,
            'closing_elec_volume': closing,
        })


class TestCalculateResiduals(FMSResidualBase):

    def test_no_pos_all_under_reported(self):
        """
        Without POS sessions: accounted = 0 for all products.
        All products are under-reported (meter > 0, accounted = 0).
        No over-reported → no allocations created.
        """
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=1000.0)
        count = shift._calculate_residuals()
        self.assertEqual(count, 0)
        self.assertEqual(len(shift.residual_allocation_ids), 0)

    def test_residual_type_set_on_product_sales(self):
        """Without POS: all products should be marked 'under'."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=1000.0)
        shift._calculate_residuals()
        for ps in shift.product_sales_ids:
            self.assertEqual(ps.residual_type, 'under')

    def test_balanced_product_marked_none(self):
        """Product with meter = 0 (no sales) stays 'none'."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, opening=0.0, closing=0.0)
        shift._calculate_residuals()
        for ps in shift.product_sales_ids:
            self.assertEqual(ps.residual_type, 'none')

    def test_recalculate_clears_previous_allocations(self):
        """Calling _calculate_residuals twice does not duplicate records."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=1000.0)
        shift._calculate_residuals()
        shift._calculate_residuals()
        # Still 0 (no POS, no over-reported to match)
        self.assertEqual(len(shift.residual_allocation_ids), 0)

    def test_product_sales_refreshed(self):
        """_calculate_residuals rebuilds product_sales_ids from meter entries."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=500.0)
        shift._calculate_residuals()
        self.assertGreater(len(shift.product_sales_ids), 0)
        diesel_ps = shift.product_sales_ids.filtered(
            lambda p: p.product_id.id == self.diesel.id
        )
        self.assertEqual(len(diesel_ps), 1)
        self.assertAlmostEqual(diesel_ps.qty_sold_elec, 500.0)

    def test_residual_amount_equals_meter_when_no_pos(self):
        """Without POS: residual_amount = meter_amount (accounted = 0)."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=100.0)  # 100L × 222.8 = 22,280
        shift._calculate_residuals()
        diesel_ps = shift.product_sales_ids.filtered(
            lambda p: p.product_id.id == self.diesel.id
        )
        self.assertAlmostEqual(diesel_ps.residual_amount, 100.0 * 222.8, places=0)

    def test_action_calculate_residuals_returns_notification(self):
        """action_calculate_residuals should return a client action dict."""
        shift = self._make_open_shift()
        result = shift.action_calculate_residuals()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('type'), 'ir.actions.client')

    def test_start_closing_triggers_residual_calculation(self):
        """action_start_closing auto-runs _calculate_residuals."""
        shift = self._make_open_shift()
        self._add_meter(shift, self.nozzle_d, closing=200.0)
        shift.action_start_closing()
        self.assertEqual(shift.state, 'closing')
        # Product sales should have been built
        self.assertGreater(len(shift.product_sales_ids), 0)
