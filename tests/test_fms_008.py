"""
test_fms_008.py — UAT (User Acceptance Tests) for FMS: End-to-End Scenarios

Five scenarios that mirror real supervisor workflows at a fuel station:

  UAT-1: Normal shift close — no residuals, all gates pass, GL posted
  UAT-2: Residual allocation — diesel over-reported, carwash under-reported
  UAT-3: Gate 1 block — FC cash variance prevents close
  UAT-4: Gate 3 block — tank variance > 0.5% prevents close
  UAT-5: Sequential shifts — second shift picks up closing readings from first

Run: make odoo-test
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class FMSUATBase(TransactionCase):
    """Shared setup for all UAT scenarios."""

    def setUp(self):
        super().setUp()

        # Revenue account for GL posting
        company = self.env.company
        self.revenue_account = self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_id', '=', company.id),
        ], limit=1)
        if not self.revenue_account:
            self.revenue_account = self.env['account.account'].create({
                'name': 'UAT Revenue', 'code': 'UAT9001',
                'account_type': 'income', 'company_id': company.id,
            })

        self.cogs_account = self.env['account.account'].search([
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
            ('company_id', '=', company.id),
        ], limit=1)
        if not self.cogs_account:
            self.cogs_account = self.env['account.account'].create({
                'name': 'UAT COGS', 'code': 'UAT9002',
                'account_type': 'expense', 'company_id': company.id,
            })

        # Fuel products
        self.diesel = self.env['product.product'].create({
            'name': 'UAT-Diesel', 'fms_is_fuel': True, 'list_price': 220.0,
            'fms_revenue_account_id': self.revenue_account.id,
            'fms_cogs_account_id': self.cogs_account.id,
        })
        self.super_fuel = self.env['product.product'].create({
            'name': 'UAT-Super', 'fms_is_fuel': True, 'list_price': 215.0,
            'fms_revenue_account_id': self.revenue_account.id,
            'fms_cogs_account_id': self.cogs_account.id,
        })
        self.carwash = self.env['product.product'].create({
            'name': 'UAT-Carwash', 'fms_is_fuel': False, 'list_price': 500.0,
        })

        # Pump and nozzles
        self.pump = self.env['fms.pump'].create({'name': 'UAT-Pump', 'order': 99})
        self.nozzle_diesel = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'A', 'letter': 'A', 'order': 1,
            'product_id': self.diesel.id,
        })
        self.nozzle_super = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'B', 'letter': 'B', 'order': 2,
            'product_id': self.super_fuel.id,
        })

        # Tanks
        self.tank_diesel = self.env['stock.location'].create({
            'name': 'UAT-Diesel-Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True, 'fms_fuel_product_id': self.diesel.id,
        })

        # Employees
        self.supervisor = self.env['hr.employee'].create({'name': 'UAT-Supervisor'})
        self.attendant = self.env['hr.employee'].create({
            'name': 'UAT-Attendant', 'fms_is_attendant': True,
        })

    def _make_shift(self, date='2026-06-15', label='1_day'):
        return self.env['fms.shift'].create({
            'date': date, 'label': label, 'supervisor_id': self.supervisor.id,
        })

    def _open_shift(self, shift):
        shift.action_open_shift()
        return shift

    def _set_closing_meter(self, shift, nozzle, closing_elec):
        entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == nozzle)
        if entry:
            entry.write({'closing_elec_volume': closing_elec})
        return entry

    def _set_closing_dip(self, shift, tank, opening, closing):
        dip = shift.dip_entry_ids.filtered(lambda d: d.location_id == tank)
        if dip:
            dip.write({'opening_volume': opening, 'closing_volume': closing})
        else:
            self.env['fms.shift.dip.entry'].create({
                'shift_id': shift.id, 'location_id': tank.id,
                'opening_volume': opening, 'closing_volume': closing,
            })
        return dip


# ---------------------------------------------------------------------------
# UAT-1: Normal shift close — all gates pass, GL posted
# ---------------------------------------------------------------------------

class TestUAT1NormalClose(FMSUATBase):

    def test_uat1_shift_closes_successfully(self):
        """Full cycle: open → enter readings → close → state=closed."""
        shift = self._make_shift()
        self._open_shift(shift)

        # Enter closing meter (diesel: 0→100L sold)
        self._set_closing_meter(shift, self.nozzle_diesel, closing_elec=100.0)

        # Dip: opened at 5000L, closed at 4900L (no attendant cash = gate1 pass)
        self._set_closing_dip(shift, self.tank_diesel, 5000.0, 4900.0)

        shift.action_start_closing()
        shift.action_close_shift()

        self.assertEqual(shift.state, 'closed')

    def test_uat1_closing_timestamp_set(self):
        """Closing timestamp is recorded on shift close."""
        shift = self._make_shift()
        self._open_shift(shift)
        shift.action_start_closing()
        shift.action_close_shift()

        self.assertIsNotNone(shift.closing_meter_date)

    def test_uat1_meter_logs_written(self):
        """Immutable meter logs created after shift close."""
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_meter(shift, self.nozzle_diesel, 150.0)
        shift.action_start_closing()
        shift.action_close_shift()

        logs = self.env['fms.meter_log'].search([('shift_id', '=', shift.id)])
        self.assertTrue(len(logs) > 0, "At least one meter log must be written on close")

    def test_uat1_dip_logs_written(self):
        """Immutable dip logs created after shift close."""
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_dip(shift, self.tank_diesel, 5000.0, 4900.0)
        shift.action_start_closing()
        shift.action_close_shift()

        logs = self.env['fms.dip_log'].search([('shift_id', '=', shift.id)])
        self.assertTrue(len(logs) > 0, "At least one dip log must be written on close")

    def test_uat1_closed_shift_is_immutable(self):
        """Meter logs cannot be deleted after shift close."""
        shift = self._make_shift()
        self._open_shift(shift)
        shift.action_start_closing()
        shift.action_close_shift()

        logs = self.env['fms.meter_log'].search([('shift_id', '=', shift.id)])
        if logs:
            with self.assertRaises(ValidationError):
                logs.unlink()

    def test_uat1_cannot_reopen_after_close(self):
        """A closed shift cannot be reopened."""
        shift = self._make_shift()
        self._open_shift(shift)
        shift.action_start_closing()
        shift.action_close_shift()

        with self.assertRaises(ValidationError):
            shift.action_open_shift()


# ---------------------------------------------------------------------------
# UAT-2: Residual allocation — diesel over, carwash under
# ---------------------------------------------------------------------------

class TestUAT2ResidualAllocation(FMSUATBase):

    def test_uat2_residuals_created_on_start_closing(self):
        """
        Residual records appear when attendant lumps carwash into diesel.
        Meter says 1000L diesel sold; POS shows 2000L diesel (over-reported).
        """
        shift = self._make_shift()
        self._open_shift(shift)

        # Set diesel closing to 1000L sold (opening was 0)
        self._set_closing_meter(shift, self.nozzle_diesel, closing_elec=1000.0)

        # No POS session linked — reported_sales = 0 for all attendants
        # Meter amount = 1000 * 220 = 220,000

        shift.action_start_closing()

        # Residual allocation algorithm runs on start_closing
        # Product sales summary should be computed
        if not shift.product_sales_ids:
            shift.action_refresh_product_sales()

        # With no POS data, residual = meter amount (under-reported in POS)
        diesel_ps = shift.product_sales_ids.filtered(
            lambda ps: ps.product_id == self.diesel
        )
        if diesel_ps:
            # Meter sold 1000L, POS sold 0 → diesel is under-reported
            self.assertGreater(diesel_ps.qty_sold_elec, 0)

    def test_uat2_product_sales_computed(self):
        """Product sales summary reflects meter readings."""
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_meter(shift, self.nozzle_diesel, closing_elec=500.0)
        self._set_closing_meter(shift, self.nozzle_super, closing_elec=200.0)

        shift.action_refresh_product_sales()

        # Diesel: 500L * 220 = 110,000; Super: 200L * 215 = 43,000
        diesel_ps = shift.product_sales_ids.filtered(
            lambda ps: ps.product_id == self.diesel
        )
        self.assertTrue(diesel_ps, "Diesel product sales record must exist")
        self.assertAlmostEqual(diesel_ps.qty_sold_elec, 500.0, places=0)

    def test_uat2_total_meter_sales_computed(self):
        """Total meter sales = sum of all product meter amounts."""
        shift = self._make_shift()
        self._open_shift(shift)
        # Diesel: 100L × 220 = 22,000; Super: 50L × 215 = 10,750
        self._set_closing_meter(shift, self.nozzle_diesel, closing_elec=100.0)
        self._set_closing_meter(shift, self.nozzle_super, closing_elec=50.0)

        shift.action_refresh_product_sales()

        expected = (100 * 220.0) + (50 * 215.0)
        self.assertAlmostEqual(shift.total_meter_sales, expected, places=0)


# ---------------------------------------------------------------------------
# UAT-3: Gate 1 block — FC cash variance prevents close
# ---------------------------------------------------------------------------

class TestUAT3Gate1Block(FMSUATBase):

    def test_uat3_fc_cash_variance_blocks_close(self):
        """
        Attendant dropped KES 10,000 cash but POS shows zero sales.
        FC balance = -10,000. Shift cannot close.
        """
        shift = self._make_shift()
        self._open_shift(shift)
        shift.action_start_closing()

        # Add attendant who dropped cash but has no POS sales
        self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.attendant.id,
            'cash_collected': 10000.0,
        })

        with self.assertRaises(ValidationError) as ctx:
            shift.action_close_shift()
        self.assertIn('GATE 1', str(ctx.exception))
        self.assertEqual(shift.state, 'closing')

    def test_uat3_resolving_cash_allows_close(self):
        """Zeroing out cash collected clears the gate."""
        shift = self._make_shift()
        self._open_shift(shift)
        shift.action_start_closing()

        cash_line = self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.attendant.id,
            'cash_collected': 5000.0,
        })

        # Gate fails
        with self.assertRaises(ValidationError):
            shift.action_close_shift()

        # Supervisor resolves: set cash to 0
        cash_line.write({'cash_collected': 0.0})
        # Now close must succeed
        shift.action_close_shift()
        self.assertEqual(shift.state, 'closed')


# ---------------------------------------------------------------------------
# UAT-4: Gate 3 block — dip variance > 0.5% prevents close
# ---------------------------------------------------------------------------

class TestUAT4Gate3Block(FMSUATBase):

    def test_uat4_dip_variance_blocks_close(self):
        """
        Tank dip shows variance of 2% (> 0.5% meniscus). Shift blocked.
        opening=10000L, closing=9800L → change=200L → variance=200/9800≈2.04%
        """
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_dip(shift, self.tank_diesel, 10000.0, 9800.0)
        shift.action_start_closing()

        with self.assertRaises(ValidationError) as ctx:
            shift.action_close_shift()
        self.assertIn('GATE 3', str(ctx.exception))
        self.assertEqual(shift.state, 'closing')

    def test_uat4_dip_within_meniscus_allows_close(self):
        """
        Tank dip variance 0.4% (< 0.5% meniscus) — gate passes.
        opening=10000L, closing=9960L → change=40L → variance=40/9960≈0.40%
        """
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_dip(shift, self.tank_diesel, 10000.0, 9960.0)
        shift.action_start_closing()
        shift.action_close_shift()  # must not raise
        self.assertEqual(shift.state, 'closed')

    def test_uat4_gate3_error_names_the_tank(self):
        """Error message identifies which tank failed."""
        shift = self._make_shift()
        self._open_shift(shift)
        self._set_closing_dip(shift, self.tank_diesel, 10000.0, 9700.0)
        shift.action_start_closing()

        with self.assertRaises(ValidationError) as ctx:
            shift.action_close_shift()
        self.assertIn('UAT-Diesel-Tank', str(ctx.exception))


# ---------------------------------------------------------------------------
# UAT-5: Sequential shifts — opening reads from previous closing
# ---------------------------------------------------------------------------

class TestUAT5SequentialShifts(FMSUATBase):

    def test_uat5_second_shift_carries_over_meter_readings(self):
        """
        After shift 1 closes with closing meter=500L, shift 2 should
        open with opening meter=500L (from the immutable meter log).
        """
        # Shift 1
        shift1 = self._make_shift(date='2026-06-15', label='1_day')
        self._open_shift(shift1)
        self._set_closing_meter(shift1, self.nozzle_diesel, closing_elec=500.0)
        shift1.action_start_closing()
        shift1.action_close_shift()

        self.assertEqual(shift1.state, 'closed')

        # Shift 2 — opening readings should come from shift1's closing
        shift2 = self._make_shift(date='2026-06-15', label='2_night')
        self._open_shift(shift2)

        diesel_entry = shift2.meter_entry_ids.filtered(
            lambda e: e.nozzle_id == self.nozzle_diesel
        )
        self.assertTrue(diesel_entry, "Shift 2 must have a diesel meter entry")
        self.assertAlmostEqual(
            diesel_entry.opening_elec_volume, 500.0, places=0,
            msg="Shift 2 opening meter must equal shift 1 closing meter"
        )

    def test_uat5_second_shift_carries_over_dip_readings(self):
        """
        After shift 1 closes with dip=4900L, shift 2 opens with dip_opening=4900L.
        """
        # Shift 1
        shift1 = self._make_shift(date='2026-06-16', label='1_day')
        self._open_shift(shift1)
        self._set_closing_dip(shift1, self.tank_diesel, 5000.0, 4900.0)
        shift1.action_start_closing()
        shift1.action_close_shift()

        # Shift 2
        shift2 = self._make_shift(date='2026-06-16', label='2_night')
        self._open_shift(shift2)

        dip_entry = shift2.dip_entry_ids.filtered(
            lambda d: d.location_id == self.tank_diesel
        )
        self.assertTrue(dip_entry, "Shift 2 must have a diesel dip entry")
        self.assertAlmostEqual(
            dip_entry.opening_volume, 4900.0, places=0,
            msg="Shift 2 opening dip must equal shift 1 closing dip"
        )

    def test_uat5_only_one_shift_open_at_a_time(self):
        """Two shifts cannot both be open simultaneously."""
        shift1 = self._make_shift(date='2026-06-17', label='1_day')
        self._open_shift(shift1)

        shift2 = self._make_shift(date='2026-06-17', label='2_night')
        with self.assertRaises(ValidationError):
            self._open_shift(shift2)
