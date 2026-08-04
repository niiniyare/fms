"""
test_fms_001.py — Unit tests for FMS-001 core models

Tests cover: fms.pump, fms.pump.nozzle, fms.shift, fms.meter_log, fms.dip_log

Run: pytest tests/test_fms_001.py -v
 or: python -m pytest tests/test_fms_001.py -v  (inside Odoo env)
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestFMSPump(TransactionCase):

    def setUp(self):
        super().setUp()
        self.pump_model = self.env['fms.pump']
        self.nozzle_model = self.env['fms.pump.nozzle']
        # Create a fuel product for nozzle tests
        self.product = self.env['product.product'].create({
            'name': 'Test V-Power',
            'fms_is_fuel': True,
        })

    def test_pump_creation(self):
        pump = self.pump_model.create({'name': 'UX5', 'order': 1})
        self.assertEqual(pump.name, 'UX5')
        self.assertTrue(pump.active)
        self.assertEqual(pump.order, 1)

    def test_pump_default_active(self):
        pump = self.pump_model.create({'name': 'DX6', 'order': 2})
        self.assertTrue(pump.active)

    def test_nozzle_creation(self):
        pump = self.pump_model.create({'name': 'UX5', 'order': 1})
        nozzle = self.nozzle_model.create({
            'pump_id': pump.id,
            'name': 'A',
            'letter': 'A',
            'order': 1,
            'product_id': self.product.id,
        })
        self.assertEqual(nozzle.letter, 'A')
        self.assertEqual(nozzle.pump_id.id, pump.id)

    def test_nozzle_unique_constraint(self):
        pump = self.pump_model.create({'name': 'UX5', 'order': 1})
        self.nozzle_model.create({
            'pump_id': pump.id,
            'name': 'A',
            'letter': 'A',
            'order': 1,
            'product_id': self.product.id,
        })
        with self.assertRaises(ValidationError):
            self.nozzle_model.create({
                'pump_id': pump.id,
                'name': 'A-dup',
                'letter': 'A',  # duplicate letter on same pump
                'order': 2,
                'product_id': self.product.id,
            })

    def test_nozzle_same_letter_different_pump_allowed(self):
        """Same letter on different pumps must be allowed."""
        pump1 = self.pump_model.create({'name': 'UX5', 'order': 1})
        pump2 = self.pump_model.create({'name': 'UX6', 'order': 2})
        self.nozzle_model.create({
            'pump_id': pump1.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.product.id,
        })
        # Should NOT raise
        nozzle2 = self.nozzle_model.create({
            'pump_id': pump2.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.product.id,
        })
        self.assertTrue(nozzle2.id)


class TestFMSShift(TransactionCase):

    def setUp(self):
        super().setUp()
        self.shift_model = self.env['fms.shift']
        self.supervisor = self.env['hr.employee'].create({'name': 'Jane Supervisor'})

    def _make_shift(self, **kw):
        vals = {
            'date': '2026-01-15',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        }
        vals.update(kw)
        return self.shift_model.create(vals)

    def test_shift_creation_draft(self):
        shift = self._make_shift()
        self.assertEqual(shift.state, 'draft')

    def test_shift_company_auto_set(self):
        shift = self._make_shift()
        self.assertEqual(shift.company_id.id, self.env.company.id)

    def test_shift_open(self):
        shift = self._make_shift()
        shift.action_open_shift()
        self.assertEqual(shift.state, 'open')
        self.assertIsNotNone(shift.opening_meter_date)
        self.assertEqual(shift.opening_meter_user_id.id, self.env.user.id)

    def test_cannot_open_already_open_shift(self):
        shift = self._make_shift()
        shift.action_open_shift()
        with self.assertRaises(ValidationError):
            shift.action_open_shift()

    def test_start_closing(self):
        shift = self._make_shift()
        shift.action_open_shift()
        shift.action_start_closing()
        self.assertEqual(shift.state, 'closing')
        self.assertIsNotNone(shift.closing_meter_date)

    def test_close_shift(self):
        shift = self._make_shift()
        shift.action_open_shift()
        shift.action_start_closing()
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')

    def test_cannot_delete_closed_shift(self):
        shift = self._make_shift()
        shift.action_open_shift()
        shift.action_start_closing()
        shift.action_close_shift()
        with self.assertRaises(ValidationError):
            shift.unlink()

    def test_can_delete_draft_shift(self):
        shift = self._make_shift()
        shift_id = shift.id
        shift.unlink()
        self.assertFalse(self.shift_model.browse(shift_id).exists())


class TestFMSMeterLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.supervisor = self.env['hr.employee'].create({'name': 'John'})
        self.shift = self.env['fms.shift'].create({
            'date': '2026-01-15',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        self.pump = self.env['fms.pump'].create({'name': 'UX5', 'order': 1})
        self.product = self.env['product.product'].create({
            'name': 'Diesel', 'fms_is_fuel': True, 'list_price': 222.8,
        })
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id,
            'name': 'A', 'letter': 'A', 'order': 1,
            'product_id': self.product.id,
        })

    def _make_log(self, opening=0.0, closing=100.0):
        return self.env['fms.meter_log'].create({
            'shift_id': self.shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle.id,
            'opening_elec_volume': opening,
            'closing_elec_volume': closing,
        })

    def test_meter_log_qty_calculation(self):
        log = self._make_log(opening=1000.0, closing=1150.0)
        self.assertAlmostEqual(log.qty_sold_elec, 150.0)

    def test_meter_log_amount_calculation(self):
        log = self._make_log(opening=0.0, closing=100.0)
        # 100L × 222.8 = 22,280
        self.assertAlmostEqual(log.amount_elec, 100.0 * 222.8)

    def test_meter_log_immutable_write(self):
        log = self._make_log()
        with self.assertRaises(ValidationError):
            log.write({'closing_elec_volume': 999.0})

    def test_meter_log_immutable_unlink(self):
        log = self._make_log()
        with self.assertRaises(ValidationError):
            log.unlink()


class TestFMSDipLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.supervisor = self.env['hr.employee'].create({'name': 'John'})
        self.shift = self.env['fms.shift'].create({
            'date': '2026-01-15',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        self.product = self.env['product.product'].create({
            'name': 'Diesel', 'fms_is_fuel': True,
        })
        self.tank = self.env['stock.location'].create({
            'name': 'Diesel Tank 1',
            'usage': 'internal',
            'fms_is_fuel_tank': True,
            'fms_fuel_product_id': self.product.id,
        })

    def _make_dip(self, opening=10000.0, closing=9500.0):
        return self.env['fms.dip_log'].create({
            'shift_id': self.shift.id,
            'location_id': self.tank.id,
            'opening_volume': opening,
            'closing_volume': closing,
        })

    def test_dip_log_qty_change(self):
        log = self._make_dip(opening=10000.0, closing=9500.0)
        self.assertAlmostEqual(log.qty_change, -500.0)

    def test_dip_log_variance_pct(self):
        # qty_change = -500, closing = 9500 → variance = 500/9500 * 100 ≈ 5.26%
        log = self._make_dip(opening=10000.0, closing=9500.0)
        expected = 500.0 / 9500.0 * 100.0
        self.assertAlmostEqual(log.variance_pct, expected, places=2)

    def test_dip_log_zero_closing_volume(self):
        log = self._make_dip(opening=0.0, closing=0.0)
        self.assertEqual(log.variance_pct, 0.0)

    def test_dip_log_immutable_write(self):
        log = self._make_dip()
        with self.assertRaises(ValidationError):
            log.write({'closing_volume': 1.0})

    def test_dip_log_immutable_unlink(self):
        log = self._make_dip()
        with self.assertRaises(ValidationError):
            log.unlink()
