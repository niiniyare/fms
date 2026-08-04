"""
test_fms_002.py — Unit tests for FMS-002 child models & entry forms

Tests cover:
  - fms.shift.meter.entry: creation, qty/amount computation, locking on closed shift
  - fms.shift.dip.entry:   creation, qty/variance computation, locking
  - fms.shift.attendant.cash: creation, totals/balance computation, locking
  - fms.shift.product.sales: rollup via _refresh_product_sales
  - fms.shift: summary totals (total_meter_sales, fc_cash_balance)

Run: make odoo-test
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------

class FMSBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.supervisor = self.env['hr.employee'].create({'name': 'Supervisor A'})
        self.product_diesel = self.env['product.product'].create({
            'name': 'Diesel', 'fms_is_fuel': True, 'list_price': 222.8,
        })
        self.product_vpower = self.env['product.product'].create({
            'name': 'V-Power', 'fms_is_fuel': True, 'list_price': 250.0,
        })
        self.pump = self.env['fms.pump'].create({'name': 'TEST-UX5', 'order': 1})
        self.nozzle_a = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.product_diesel.id,
        })
        self.nozzle_b = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'B', 'letter': 'B',
            'order': 2, 'product_id': self.product_vpower.id,
        })
        self.tank = self.env['stock.location'].create({
            'name': 'Diesel Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True,
            'fms_fuel_product_id': self.product_diesel.id,
        })
        self.attendant = self.env['hr.employee'].create({
            'name': 'Attendant A', 'fms_is_attendant': True,
        })

    def _open_shift(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-01-15',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        return shift

    def _closed_shift(self):
        shift = self._open_shift()
        shift.action_start_closing()
        shift.action_close_shift()
        return shift


# ---------------------------------------------------------------------------
# Meter entry tests
# ---------------------------------------------------------------------------

class TestFMSMeterEntry(FMSBase):

    def _add_meter_entry(self, shift, opening=1000.0, closing=1150.0):
        return self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_a.id,
            'opening_elec_volume': opening,
            'closing_elec_volume': closing,
        })

    def test_meter_entry_creation(self):
        shift = self._open_shift()
        entry = self._add_meter_entry(shift)
        self.assertEqual(entry.pump_id.id, self.pump.id)
        self.assertEqual(entry.product_id.id, self.product_diesel.id)

    def test_meter_entry_qty_computed(self):
        shift = self._open_shift()
        entry = self._add_meter_entry(shift, opening=1000.0, closing=1150.0)
        self.assertAlmostEqual(entry.qty_sold_elec, 150.0)

    def test_meter_entry_amount_computed(self):
        shift = self._open_shift()
        entry = self._add_meter_entry(shift, opening=0.0, closing=100.0)
        self.assertAlmostEqual(entry.amount_elec, 100.0 * 222.8)

    def test_meter_entry_locked_on_closed_shift(self):
        shift = self._closed_shift()
        entry = self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_a.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,
        })
        with self.assertRaises(ValidationError):
            entry.write({'closing_elec_volume': 200.0})

    def test_meter_entry_unlink_locked_on_closed_shift(self):
        shift = self._closed_shift()
        entry = self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_a.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,
        })
        with self.assertRaises(ValidationError):
            entry.unlink()

    def test_meter_entry_editable_on_open_shift(self):
        shift = self._open_shift()
        entry = self._add_meter_entry(shift)
        entry.write({'closing_elec_volume': 1200.0})
        self.assertAlmostEqual(entry.closing_elec_volume, 1200.0)

    def test_meter_entry_snapshot_to_log(self):
        shift = self._open_shift()
        entry = self._add_meter_entry(shift, opening=1000.0, closing=1100.0)
        log = entry._create_meter_log()
        self.assertEqual(log.shift_id.id, shift.id)
        self.assertAlmostEqual(log.qty_sold_elec, 100.0)


# ---------------------------------------------------------------------------
# Dip entry tests
# ---------------------------------------------------------------------------

class TestFMSDipEntry(FMSBase):

    def _add_dip_entry(self, shift, opening=10000.0, closing=9500.0):
        return self.env['fms.shift.dip.entry'].create({
            'shift_id': shift.id,
            'location_id': self.tank.id,
            'opening_volume': opening,
            'closing_volume': closing,
        })

    def test_dip_entry_creation(self):
        shift = self._open_shift()
        entry = self._add_dip_entry(shift)
        self.assertEqual(entry.product_id.id, self.product_diesel.id)

    def test_dip_entry_qty_change(self):
        shift = self._open_shift()
        entry = self._add_dip_entry(shift, opening=10000.0, closing=9500.0)
        self.assertAlmostEqual(entry.qty_change, -500.0)

    def test_dip_entry_variance_pct(self):
        shift = self._open_shift()
        entry = self._add_dip_entry(shift, opening=10000.0, closing=9500.0)
        expected = 500.0 / 9500.0 * 100.0
        self.assertAlmostEqual(entry.variance_pct, expected, places=2)

    def test_dip_entry_locked_on_closed_shift(self):
        shift = self._closed_shift()
        entry = self._add_dip_entry(shift)
        with self.assertRaises(ValidationError):
            entry.write({'closing_volume': 1.0})

    def test_dip_entry_snapshot_to_log(self):
        shift = self._open_shift()
        entry = self._add_dip_entry(shift, opening=10000.0, closing=9500.0)
        log = entry._create_dip_log()
        self.assertEqual(log.shift_id.id, shift.id)
        self.assertAlmostEqual(log.qty_change, -500.0)


# ---------------------------------------------------------------------------
# Attendant cash tests
# ---------------------------------------------------------------------------

class TestFMSAttendantCash(FMSBase):

    def _add_cash(self, shift, reported=50000.0, cash=30000.0, mpesa=15000.0,
                  card=0.0, ar=5000.0, expense=0.0):
        return self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.attendant.id,
            'reported_sales': reported,
            'cash_collected': cash,
            'mpesa_amount': mpesa,
            'card_amount': card,
            'ar_amount': ar,
            'expense_amount': expense,
        })

    def test_attendant_cash_creation(self):
        shift = self._open_shift()
        rec = self._add_cash(shift)
        self.assertEqual(rec.attendant_id.id, self.attendant.id)

    def test_total_accounted_computed(self):
        shift = self._open_shift()
        # 30k + 15k + 0 + 5k - 0 = 50k
        rec = self._add_cash(shift, cash=30000.0, mpesa=15000.0, ar=5000.0)
        self.assertAlmostEqual(rec.total_accounted, 50000.0)

    def test_balance_zero_when_balanced(self):
        shift = self._open_shift()
        rec = self._add_cash(shift, reported=50000.0, cash=30000.0,
                              mpesa=15000.0, ar=5000.0)
        self.assertAlmostEqual(rec.balance, 0.0)

    def test_balance_nonzero_when_gap(self):
        shift = self._open_shift()
        rec = self._add_cash(shift, reported=50000.0, cash=20000.0,
                              mpesa=10000.0, ar=5000.0)
        # accounted = 35k, reported = 50k → balance = 15k
        self.assertAlmostEqual(rec.balance, 15000.0)

    def test_expense_reduces_accounted(self):
        shift = self._open_shift()
        rec = self._add_cash(shift, reported=45000.0, cash=50000.0,
                              mpesa=0.0, ar=0.0, expense=5000.0)
        # accounted = 50k - 5k = 45k, balance = 0
        self.assertAlmostEqual(rec.total_accounted, 45000.0)
        self.assertAlmostEqual(rec.balance, 0.0)

    def test_cash_locked_on_closed_shift(self):
        shift = self._closed_shift()
        rec = self._add_cash(shift)
        with self.assertRaises(ValidationError):
            rec.write({'cash_collected': 99999.0})


# ---------------------------------------------------------------------------
# Shift summary totals + product sales rollup
# ---------------------------------------------------------------------------

class TestFMSShiftSummary(FMSBase):

    def test_total_meter_sales(self):
        shift = self._open_shift()
        self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_a.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,   # 100L × 222.8 = 22,280
        })
        self.assertAlmostEqual(shift.total_meter_sales, 100.0 * 222.8)

    def test_fc_cash_balance_computed(self):
        shift = self._open_shift()
        self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_a.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,   # 22,280 KES
        })
        self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.attendant.id,
            'reported_sales': 25000.0,       # attendant reported more
        })
        # balance = 25,000 - 22,280 = 2,720
        self.assertAlmostEqual(shift.fc_cash_balance, 25000.0 - (100.0 * 222.8))

    def test_refresh_product_sales_creates_lines(self):
        shift = self._open_shift()
        self.env['fms.shift.meter.entry'].create([
            {
                'shift_id': shift.id,
                'pump_id': self.pump.id,
                'nozzle_id': self.nozzle_a.id,
                'opening_elec_volume': 0.0,
                'closing_elec_volume': 100.0,
            },
            {
                'shift_id': shift.id,
                'pump_id': self.pump.id,
                'nozzle_id': self.nozzle_b.id,
                'opening_elec_volume': 0.0,
                'closing_elec_volume': 50.0,
            },
        ])
        shift._refresh_product_sales()
        self.assertEqual(len(shift.product_sales_ids), 2)

    def test_refresh_product_sales_aggregates_same_product(self):
        """Two nozzles dispensing the same product must be summed."""
        nozzle_c = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'C', 'letter': 'C',
            'order': 3, 'product_id': self.product_diesel.id,
        })
        shift = self._open_shift()
        self.env['fms.shift.meter.entry'].create([
            {
                'shift_id': shift.id,
                'pump_id': self.pump.id,
                'nozzle_id': self.nozzle_a.id,
                'opening_elec_volume': 0.0,
                'closing_elec_volume': 100.0,
            },
            {
                'shift_id': shift.id,
                'pump_id': self.pump.id,
                'nozzle_id': nozzle_c.id,
                'opening_elec_volume': 0.0,
                'closing_elec_volume': 80.0,
            },
        ])
        shift._refresh_product_sales()
        # Both nozzles are Diesel → should produce 1 product sales line
        diesel_lines = shift.product_sales_ids.filtered(
            lambda l: l.product_id.id == self.product_diesel.id
        )
        self.assertEqual(len(diesel_lines), 1)
        self.assertAlmostEqual(diesel_lines.qty_sold_elec, 180.0)
