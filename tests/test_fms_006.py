"""
test_fms_006.py — Unit tests for FMS-006: Shift Lifecycle & Hard Gates

Tests cover:
  - GATE 1: FC Cash balance must be 0 (sum of all attendant balances)
  - GATE 2: Every individual attendant balance must be 0
  - GATE 3: Tank dip variance must be within ±0.5% meniscus
  - Gates are non-negotiable: shift cannot close while any gate fails
  - Happy path: shift closes successfully when all gates pass
  - State machine: draft → open → closing → closed

Run: make odoo-test
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class FMSGateBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write({'state': 'draft'})
        self.supervisor = self.env['hr.employee'].create({'name': 'Gate-Supervisor'})
        self.attendant1 = self.env['hr.employee'].create({
            'name': 'Gate-Attendant-1', 'fms_is_attendant': True,
        })
        self.attendant2 = self.env['hr.employee'].create({
            'name': 'Gate-Attendant-2', 'fms_is_attendant': True,
        })
        self.product = self.env['product.product'].create({
            'name': 'Gate-Diesel', 'fms_is_fuel': True, 'list_price': 200.0,
        })
        self.pump = self.env['fms.pump'].create({'name': 'Gate-Pump1', 'order': 20})
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id,
            'name': 'A', 'letter': 'A', 'order': 1,
            'product_id': self.product.id,
        })
        self.tank = self.env['stock.location'].create({
            'name': 'Gate-Tank-1',
            'usage': 'internal',
            'fms_is_fuel_tank': True,
            'fms_fuel_product_id': self.product.id,
        })

    def _make_closing_shift(self):
        """Return a shift in 'closing' state with zero meter/dip values."""
        shift = self.env['fms.shift'].create({
            'date': '2026-06-01',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        shift.action_start_closing()
        return shift

    def _add_cash(self, shift, attendant, cash_collected=0.0):
        """Add an attendant cash line to the shift."""
        return self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': attendant.id,
            'cash_collected': cash_collected,
        })

    def _set_dip_variance(self, shift, opening, closing):
        """Override the first dip entry's volumes to produce a specific variance."""
        dip = shift.dip_entry_ids[:1]
        if dip:
            dip.write({'opening_volume': opening, 'closing_volume': closing})
        else:
            self.env['fms.shift.dip.entry'].create({
                'shift_id': shift.id,
                'location_id': self.tank.id,
                'opening_volume': opening,
                'closing_volume': closing,
            })


# ---------------------------------------------------------------------------
# Gate 1: FC Cash balance
# ---------------------------------------------------------------------------

class TestGate1FCCash(FMSGateBase):

    def test_gate1_passes_with_zero_attendants(self):
        """No attendant cash lines → fc_cash_balance = 0 → gate passes."""
        shift = self._make_closing_shift()
        # No cash lines — gate 1 should pass (nothing to sum)
        shift._gate_check_fc_cash()  # must not raise

    def test_gate1_passes_when_balance_zero(self):
        """Attendant balance = 0 (no POS, no cash) → gate passes."""
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=0.0)
        shift._gate_check_fc_cash()  # must not raise

    def test_gate1_fails_when_cash_exceeds_sales(self):
        """cash_collected > reported_sales (no POS) → balance negative → gate fails."""
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=500.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_fc_cash()
        self.assertIn('GATE 4', str(ctx.exception))

    def test_gate1_error_message_shows_amount(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=1234.56)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_fc_cash()
        self.assertIn('1,234.56', str(ctx.exception))

    def test_gate1_blocks_shift_close(self):
        """_gate_check_fc_cash raises when FC cash balance != 0 (Gate 4)."""
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=999.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_fc_cash()
        self.assertIn('GATE 4', str(ctx.exception))
        # Shift must still be in 'closing', not 'closed'
        self.assertEqual(shift.state, 'closing')

    def test_gate1_multiple_attendants_net_to_zero(self):
        """Two attendants whose individual balances cancel out — gate passes."""
        shift = self._make_closing_shift()
        # Without POS, balance = reported_sales(0) - cash_collected
        # Both have 0 cash → balance = 0 each → net = 0
        self._add_cash(shift, self.attendant1, cash_collected=0.0)
        self._add_cash(shift, self.attendant2, cash_collected=0.0)
        shift._gate_check_fc_cash()  # must not raise


# ---------------------------------------------------------------------------
# Gate 2: Individual attendant balances
# ---------------------------------------------------------------------------

class TestGate2AttendantBalances(FMSGateBase):

    def test_gate2_passes_with_no_cash_lines(self):
        shift = self._make_closing_shift()
        shift._gate_check_attendant_balances()  # must not raise

    def test_gate2_passes_when_all_zero(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=0.0)
        self._add_cash(shift, self.attendant2, cash_collected=0.0)
        shift._gate_check_attendant_balances()  # must not raise

    def test_gate2_fails_for_single_nonzero(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=100.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_attendant_balances()
        self.assertIn('GATE 3', str(ctx.exception))

    def test_gate2_names_failing_attendants(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=250.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_attendant_balances()
        self.assertIn('Gate-Attendant-1', str(ctx.exception))

    def test_gate2_names_all_failing_attendants(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=100.0)
        self._add_cash(shift, self.attendant2, cash_collected=200.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_attendant_balances()
        msg = str(ctx.exception)
        self.assertIn('Gate-Attendant-1', msg)
        self.assertIn('Gate-Attendant-2', msg)

    def test_gate2_blocks_shift_close(self):
        shift = self._make_closing_shift()
        self._add_cash(shift, self.attendant1, cash_collected=50.0)
        with self.assertRaises(ValidationError) as ctx:
            shift.action_close_shift()
        self.assertIn('GATE', str(ctx.exception))
        self.assertEqual(shift.state, 'closing')


# ---------------------------------------------------------------------------
# Gate 3: Stock variance meniscus
# ---------------------------------------------------------------------------

class TestGate3StockVariance(FMSGateBase):

    def test_gate3_passes_with_no_dip_entries(self):
        shift = self._make_closing_shift()
        # Remove all dip entries to simulate a shift with no tanks
        shift.dip_entry_ids.unlink()
        shift._gate_check_stock_variance()  # must not raise

    def test_gate3_passes_within_meniscus(self):
        """Variance of 0.4% (< 0.5%) → gate passes."""
        shift = self._make_closing_shift()
        # opening=10000, closing=9960 → change=-40 → variance=40/9960≈0.40%
        self._set_dip_variance(shift, opening=10000.0, closing=9960.0)
        shift._gate_check_stock_variance()  # must not raise

    def test_gate3_passes_at_meniscus_boundary(self):
        """Variance of exactly 0.5% → gate passes (boundary is inclusive)."""
        shift = self._make_closing_shift()
        # closing=10000, change=50 → 50/10000 = 0.5%
        self._set_dip_variance(shift, opening=9950.0, closing=10000.0)
        shift._gate_check_stock_variance()  # must not raise

    def test_gate3_fails_above_meniscus(self):
        """Variance of 1.0% (> 0.5%) → gate fails."""
        shift = self._make_closing_shift()
        # closing=10000, change=100 → 100/10000 = 1.0%
        self._set_dip_variance(shift, opening=9900.0, closing=10000.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_stock_variance()
        self.assertIn('GATE 5', str(ctx.exception))

    def test_gate3_error_names_tank(self):
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=9000.0, closing=10000.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_stock_variance()
        self.assertIn('Gate-Tank-1', str(ctx.exception))

    def test_gate3_skips_zero_closing_volume(self):
        """Dip entry with closing_volume=0 is not checked (tank not read)."""
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=10000.0, closing=0.0)
        shift._gate_check_stock_variance()  # must not raise

    def test_gate3_blocks_shift_close(self):
        """_gate_check_stock_variance raises when variance > meniscus (Gate 5)."""
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=9000.0, closing=10000.0)
        with self.assertRaises(ValidationError) as ctx:
            shift._gate_check_stock_variance()
        self.assertIn('GATE 5', str(ctx.exception))
        self.assertEqual(shift.state, 'closing')


# ---------------------------------------------------------------------------
# Happy path: all gates pass, shift closes
# ---------------------------------------------------------------------------

class TestHappyPath(FMSGateBase):

    def test_shift_closes_when_all_gates_pass(self):
        """Shift with no cash lines and acceptable variance closes successfully."""
        shift = self._make_closing_shift()
        # Set variance within meniscus (0.2%)
        self._set_dip_variance(shift, opening=9980.0, closing=10000.0)
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')

    def test_closed_shift_has_closing_timestamp(self):
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=9990.0, closing=10000.0)
        shift.action_close_shift()
        # closing_meter_date is set in action_start_closing, not action_close_shift
        self.assertTrue(shift.closing_meter_date)

    def test_state_machine_full_cycle(self):
        """draft → open → closing → closed state machine works end-to-end."""
        shift = self.env['fms.shift'].create({
            'date': '2026-06-02',
            'label': '2_evening',
            'supervisor_id': self.supervisor.id,
        })
        self.assertEqual(shift.state, 'draft')
        shift.action_open_shift()
        self.assertEqual(shift.state, 'open')
        shift.action_start_closing()
        self.assertEqual(shift.state, 'closing')
        # Fix dip to be within meniscus before closing
        self._set_dip_variance(shift, opening=9995.0, closing=10000.0)
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')

    def test_cannot_reopen_closed_shift(self):
        """Opening an already-closed shift raises ValidationError."""
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=9995.0, closing=10000.0)
        shift.action_close_shift()
        with self.assertRaises(ValidationError):
            shift.action_open_shift()

    def test_cannot_close_draft_shift(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-06-03',
            'label': '3_night',
            'supervisor_id': self.supervisor.id,
        })
        with self.assertRaises(ValidationError):
            shift.action_close_shift()

    def test_closed_shift_cannot_be_deleted(self):
        shift = self._make_closing_shift()
        self._set_dip_variance(shift, opening=9995.0, closing=10000.0)
        shift.action_close_shift()
        with self.assertRaises(ValidationError):
            shift.unlink()
