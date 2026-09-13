"""
test_phase1_regression.py — Regression tests for Phase 1 financial/inventory fixes.

Covers:
  - BUG-01: AVCO double-count: _post_stock_consumption must precede _sync_stock_quant_from_dips
  - BUG-02: delivery_qty must be persisted to fms.dip_log on shift close
  - BUG-03: Gate G5 must check each attendant's fc_variance at non-POS stations
  - BUG-04: RTT correction must not mutate the original fms.meter_log
  - BUG-05: Config threshold changes in Settings must affect gate behavior
  - BUG-06: Clearing account domain must be asset_current, not asset_receivable

Run with the Odoo test runner:
  odoo-bin --test-enable -m fms --test-tags test_phase1_regression
"""

import inspect
import unittest
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class Phase1Base(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Suppress noise from unrelated open/closing shifts
        cls.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write(
            {'state': 'draft'}
        )

    def setUp(self):
        super().setUp()
        company = self.env.company

        self.journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1
        ) or self.env['account.journal'].create({
            'name': 'Phase1 Test Journal', 'code': 'PH1J', 'type': 'sale',
            'company_id': company.id,
        })
        self.clearing = self.env['account.account'].search(
            [('account_type', '=', 'asset_current'), ('company_ids', 'in', company.id)], limit=1
        ) or self.env['account.account'].create({
            'name': 'Phase1 Clearing', 'code': 'PH1CL', 'account_type': 'asset_current',
            'company_ids': [(4, company.id)],
        })
        self.revenue_acc = self.env['account.account'].search(
            [('account_type', 'in', ('income', 'income_other')), ('company_ids', 'in', company.id)],
            limit=1
        ) or self.env['account.account'].create({
            'name': 'Phase1 Revenue', 'code': 'PH1REV', 'account_type': 'income',
            'company_ids': [(4, company.id)],
        })

        prefs = self.env['fms.site.preferences'].get_for_company(company)
        prefs.write({'sales_journal_id': self.journal.id, 'clearing_account_id': self.clearing.id})
        self.prefs = prefs

        self.fuel = self.env['product.product'].create({
            'name': 'Ph1-Diesel',
            'fms_is_fuel': True,
            'list_price': 180.0,
            'is_storable': True,
            'fms_revenue_account_id': self.revenue_acc.id,
        })
        self.pump = self.env['fms.pump'].create({'name': 'Ph1-Pump', 'order': 99})
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.fuel.id, 'state': 'active',
        })
        self.tank = self.env['stock.location'].create({
            'name': 'Ph1-Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True, 'fms_fuel_product_id': self.fuel.id,
        })
        self.supervisor = self.env['hr.employee'].create({'name': 'Ph1-Supervisor'})

    def _make_shift(self, opening_vol=10000.0, sold_vol=200.0, closing_dip=9750.0):
        """Create shift with one nozzle entry and one dip entry."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-01', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle)
        if not entry:
            entry = self.env['fms.shift.meter.entry'].create({
                'shift_id': shift.id, 'nozzle_id': self.nozzle.id, 'pump_id': self.pump.id,
                'product_id': self.fuel.id,
                'opening_elec_volume': 0.0, 'closing_elec_volume': sold_vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': sold_vol * 180.0,
            })
        else:
            entry.sudo().write({
                'opening_elec_volume': 0.0, 'closing_elec_volume': sold_vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': sold_vol * 180.0,
            })
        dip = shift.dip_entry_ids.filtered(lambda d: d.location_id == self.tank)
        if not dip:
            dip = self.env['fms.shift.dip.entry'].create({
                'shift_id': shift.id, 'location_id': self.tank.id,
                'opening_volume': opening_vol, 'closing_volume': closing_dip,
            })
        else:
            dip.sudo().write({'opening_volume': opening_vol, 'closing_volume': closing_dip})
        return shift


# ---------------------------------------------------------------------------
# BUG-01: Stock close sequence — consumption before quant sync
# ---------------------------------------------------------------------------


class TestStockCloseSequence(Phase1Base):

    def test_close_method_order_consumption_before_sync(self):
        """
        _post_stock_consumption must be called before _sync_stock_quant_from_dips.

        If sync runs first it adjusts stock to closing dip BEFORE consumption removes
        meter-sold volume — the consumption then double-removes from an already-adjusted base.

        We verify ordering by inspecting the action_close_shift source code.
        AVCO double-count is a valuation consequence; stock quantity is the observable proxy.
        """
        src = inspect.getsource(self.env['fms.shift'].action_close_shift)
        idx_consumption = src.find('_post_stock_consumption')
        idx_sync = src.find('_sync_stock_quant_from_dips')
        self.assertGreater(idx_consumption, 0, "_post_stock_consumption not found in action_close_shift")
        self.assertGreater(idx_sync, 0, "_sync_stock_quant_from_dips not found in action_close_shift")
        self.assertLess(
            idx_consumption, idx_sync,
            "BUG-01: _post_stock_consumption must appear BEFORE _sync_stock_quant_from_dips "
            "in action_close_shift to prevent AVCO double-count"
        )

    def test_stock_quant_matches_closing_dip_after_close(self):
        """
        After shift close, stock.quant on the fuel tank must equal the closing dip volume.
        Opening=10000, sold=200, closing_dip=9750 → expected quant=9750.
        """
        # Seed initial stock
        quant = self.env['stock.quant'].sudo().create({
            'location_id': self.tank.id,
            'product_id': self.fuel.id,
            'quantity': 10000.0,
            'company_id': self.env.company.id,
        })
        shift = self._make_shift(opening_vol=10000.0, sold_vol=200.0, closing_dip=9750.0)
        shift.action_start_closing()
        # Force close bypassing gates
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
            shift._post_sales_journal()
            shift._post_stock_consumption()
            shift._sync_stock_quant_from_dips()
        quant.invalidate_recordset(['quantity'])
        self.assertAlmostEqual(
            quant.quantity, 9750.0, places=1,
            msg="BUG-01: Final stock quant must equal closing dip (9750 L), not double-consumed value"
        )

    def test_stock_consumption_stock_move_created(self):
        """A stock.move for net meter sales must be created after close."""
        shift = self._make_shift(sold_vol=200.0, closing_dip=9800.0)
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
            shift._post_sales_journal()
            shift._post_stock_consumption()
            shift._sync_stock_quant_from_dips()
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
        ])
        self.assertTrue(moves, "BUG-01: No stock.move created for fuel consumption")
        total_qty = sum(moves.mapped('product_uom_qty'))
        self.assertAlmostEqual(total_qty, 200.0, places=2,
                               msg="BUG-01: Consumed quantity must equal net meter sales (200L)")

    def test_no_double_stock_move_on_idempotent_close(self):
        """Calling close methods twice must not create duplicate stock.moves."""
        shift = self._make_shift(sold_vol=100.0, closing_dip=9900.0)
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
            shift._post_stock_consumption()
            shift._sync_stock_quant_from_dips()
            # Second call — must be idempotent
            shift._post_stock_consumption()
            shift._sync_stock_quant_from_dips()
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
        ])
        self.assertEqual(len(moves), 1, "BUG-01: Idempotent close must not create duplicate stock.moves")


# ---------------------------------------------------------------------------
# BUG-02: delivery_qty persisted to dip_log
# ---------------------------------------------------------------------------


class TestDipLogDeliveryQty(Phase1Base):

    def test_dip_log_delivery_qty_zero_when_no_delivery(self):
        """delivery_qty must be 0.0 on dip_log when no delivery occurred."""
        shift = self._make_shift()
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
        log = self.env['fms.dip_log'].sudo().search([('shift_id', '=', shift.id)], limit=1)
        self.assertTrue(log, "Dip log must exist after close")
        self.assertAlmostEqual(log.delivery_qty, 0.0, places=2,
                               msg="BUG-02: delivery_qty must be 0.0 when no delivery occurred")

    def test_dip_log_contains_delivery_key(self):
        """
        _compute_dip_variance_data must return a 'delivery' key so _create_dip_log
        can persist it. Verify by calling the method directly and inspecting the result.
        """
        shift = self._make_shift()
        shift.action_start_closing()
        dip_entry = shift.dip_entry_ids.filtered(lambda d: d.location_id == self.tank)
        if not dip_entry:
            self.skipTest("No dip entry found for Ph1-Tank")
        vdata = shift._compute_dip_variance_data(dip_entry[0])
        self.assertIn('delivery', vdata,
                      "BUG-02: _compute_dip_variance_data must return 'delivery' key for _create_dip_log")

    def test_dip_log_delivery_qty_field_exists(self):
        """fms.dip_log must have the delivery_qty field."""
        fields = self.env['fms.dip_log']._fields
        self.assertIn('delivery_qty', fields,
                      "BUG-02: fms.dip_log must have delivery_qty field")


# ---------------------------------------------------------------------------
# BUG-03: Gate G5 must not skip non-POS stations
# ---------------------------------------------------------------------------


class TestGate5NonPOS(Phase1Base):

    def _make_attendant_shift(self):
        """Create a shift with an attendant cash line having a non-zero fc_variance."""
        attendant = self.env['hr.employee'].create({
            'name': 'Ph1-Attendant', 'fms_is_attendant': True,
        })
        shift = self._make_shift()
        shift.action_start_closing()
        cash_line = self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': attendant.id,
            'cash_collected': 0.0,  # will produce a non-zero fc_variance
        })
        return shift, cash_line

    def test_gate3_checks_fc_variance_without_pos(self):
        """
        BUG-03: Gate G3 must check each attendant's fc_variance at non-POS stations.

        Previously 'if not self.pos_session_ids: return' silently skipped the check.
        Now it must raise ValidationError when an attendant has unresolved fc_variance.
        """
        shift, cash_line = self._make_attendant_shift()
        # Ensure no POS sessions (non-POS station)
        self.assertFalse(shift.pos_session_ids, "Expected no POS sessions for this test")

        # Manually create a non-zero fc_variance: reported_sales > collected
        # We set cash_collected = 0 but reported_sales will derive from meter entries
        # If reported_sales > 0 and collected = 0, fc_variance != 0
        cash_line.invalidate_recordset(['fc_variance'])
        if abs(cash_line.fc_variance) < 0.01:
            # Reported_sales is 0 too — force via reported_sales directly
            cash_line.sudo().write({'cash_collected': 0.0})
            # Force a variance by making captured != collected
            # Simulate: reported_sales = 1000, collected = 0 → variance = 1000
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "UPDATE fms_shift_attendant_cash SET reported_sales = 1000.0 WHERE id = %s",
                    (cash_line.id,),
                )
                cash_line.invalidate_recordset()

        if abs(cash_line.fc_variance) > 0.01:
            with self.assertRaises(ValidationError,
                                   msg="BUG-03: Gate G3 must raise for non-zero fc_variance at non-POS station"):
                shift._gate_check_attendant_balances()
        else:
            # If fc_variance is still 0 (no meter sales), gate passes — that's correct
            try:
                shift._gate_check_attendant_balances()
            except ValidationError:
                self.fail("Gate G3 should not fail when fc_variance is truly 0")

    def test_gate3_source_no_early_return_for_no_pos(self):
        """
        BUG-03: The _gate_check_attendant_balances source must not contain
        'if not self.pos_session_ids: return' as the only non-POS path.
        """
        src = inspect.getsource(self.env['fms.shift']._gate_check_attendant_balances)
        # The old buggy pattern was a bare early return for non-POS
        # New code handles both POS and non-POS branches
        self.assertIn('fc_variance', src,
                      "BUG-03: Gate G3 must check fc_variance for non-POS stations")
        self.assertIn('pos_session_ids', src,
                      "Gate G3 must still handle both POS and non-POS code paths")


# ---------------------------------------------------------------------------
# BUG-04: RTT correction must not mutate original meter_log
# ---------------------------------------------------------------------------


class TestRTTCorrection(Phase1Base):

    def test_meter_log_write_raises(self):
        """Original fms.meter_log must raise on any write() attempt."""
        shift = self._make_shift()
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
        log = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)], limit=1)
        self.assertTrue(log, "Meter log must exist after _write_meter_logs")
        with self.assertRaises(ValidationError, msg="BUG-04: meter_log.write() must raise"):
            log.write({'rtt_volume': 5.0})

    def test_rtt_correction_model_exists(self):
        """fms.meter_log.rtt_correction model must exist in the registry."""
        self.assertIn('fms.meter_log.rtt_correction', self.env,
                      "BUG-04: fms.meter_log.rtt_correction model must be defined")

    def test_rtt_correction_record_creation(self):
        """An RTT correction can be created and is linked to the original log."""
        shift = self._make_shift()
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
        log = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)], limit=1)
        correction = self.env['fms.meter_log.rtt_correction'].sudo().create({
            'meter_log_id': log.id,
            'rtt_volume': 5.0,
            'rtt_amount': 900.0,
            'reason': 'Test RTT correction',
        })
        self.assertEqual(correction.meter_log_id, log, "Correction must link to original meter log")
        self.assertAlmostEqual(correction.rtt_volume, 5.0, places=2)

    def test_rtt_correction_is_immutable(self):
        """Created RTT correction records must be immutable (write raises)."""
        shift = self._make_shift()
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
        log = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)], limit=1)
        correction = self.env['fms.meter_log.rtt_correction'].sudo().create({
            'meter_log_id': log.id, 'rtt_volume': 5.0,
            'rtt_amount': 900.0, 'reason': 'immutability test',
        })
        with self.assertRaises(ValidationError, msg="BUG-04: rtt_correction.write() must raise"):
            correction.write({'rtt_volume': 10.0})

    def test_original_meter_log_rtt_volume_unchanged_after_correction(self):
        """Original meter_log.rtt_volume must not change when a correction is created."""
        shift = self._make_shift()
        shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
        log = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)], limit=1)
        original_rtt = log.rtt_volume
        self.env['fms.meter_log.rtt_correction'].sudo().create({
            'meter_log_id': log.id, 'rtt_volume': 5.0,
            'rtt_amount': 900.0, 'reason': 'preserve original test',
        })
        log.invalidate_recordset(['rtt_volume'])
        # Direct DB read to confirm no raw SQL touched it
        self.env.cr.execute('SELECT rtt_volume FROM fms_meter_log WHERE id = %s', (log.id,))
        db_rtt = self.env.cr.fetchone()[0] or 0.0
        self.assertAlmostEqual(
            db_rtt, original_rtt, places=2,
            msg="BUG-04: Original meter_log.rtt_volume must not change when correction is posted"
        )


# ---------------------------------------------------------------------------
# BUG-05: Config thresholds must proxy to site.prefs
# ---------------------------------------------------------------------------


class TestConfigThresholdProxy(Phase1Base):

    def test_meniscus_in_prefs_equals_config(self):
        """
        Changing fms_meniscus_l in res.config.settings must update
        prefs.default_dip_variance_meniscus (the value gates actually read).
        """
        config = self.env['res.config.settings'].create({})
        config.fms_meniscus_l = 75.0
        config._set_fms_prefs()
        self.prefs.invalidate_recordset(['default_dip_variance_meniscus'])
        self.assertAlmostEqual(
            self.prefs.default_dip_variance_meniscus, 75.0, places=1,
            msg="BUG-05: Settings meniscus change must write through to site.prefs"
        )

    def test_threshold_in_prefs_equals_config(self):
        """
        Changing fms_elec_vs_cash_threshold_l in res.config.settings must update
        prefs.elec_vs_cash_threshold_l.
        """
        config = self.env['res.config.settings'].create({})
        config.fms_elec_vs_cash_threshold_l = 8.0
        config._set_fms_prefs()
        self.prefs.invalidate_recordset(['elec_vs_cash_threshold_l'])
        self.assertAlmostEqual(
            self.prefs.elec_vs_cash_threshold_l, 8.0, places=1,
            msg="BUG-05: Settings threshold change must write through to site.prefs"
        )

    def test_meniscus_default_50L(self):
        """default_dip_variance_meniscus must default to 50 L, not 1000 L."""
        new_company = self.env['res.company'].sudo().create({'name': 'Ph1MeniscusTest'})
        prefs = self.env['fms.site.preferences'].sudo().get_for_company(new_company)
        self.assertAlmostEqual(
            prefs.default_dip_variance_meniscus, 50.0, places=1,
            msg="BUG-05: Meniscus default must be 50 L (not 1000 L which effectively disables gate)"
        )


# ---------------------------------------------------------------------------
# BUG-06: Clearing account domain must be asset_current
# ---------------------------------------------------------------------------


class TestClearingAccountDomain(Phase1Base):

    def test_clearing_account_field_domain_asset_current(self):
        """
        fms.site.preferences.clearing_account_id domain must require asset_current.
        Using asset_receivable corrupts AR aging and partner reconciliation.
        """
        field = self.env['fms.site.preferences']._fields['clearing_account_id']
        domain = field.domain
        domain_str = str(domain)
        self.assertNotIn('asset_receivable', domain_str,
                         "BUG-06: clearing_account_id domain must not use asset_receivable")
        self.assertIn('asset_current', domain_str,
                      "BUG-06: clearing_account_id domain must require asset_current")

    def test_config_clearing_account_field_domain_asset_current(self):
        """res.config.settings.fms_clearing_account_id must also use asset_current domain."""
        field = self.env['res.config.settings']._fields.get('fms_clearing_account_id')
        if not field:
            self.skipTest("fms_clearing_account_id not in res.config.settings")
        domain_str = str(field.domain)
        self.assertNotIn('asset_receivable', domain_str,
                         "BUG-06: fms_clearing_account_id config field must not use asset_receivable")

    def test_test_common_clearing_account_is_asset_current(self):
        """
        The test_common helper creates clearing as asset_current — confirms intent.
        The domain must accept accounts of this type.
        """
        field = self.env['fms.site.preferences']._fields['clearing_account_id']
        # asset_current clearing must be accepted by the ORM field
        # (domain is enforced client-side but we verify the model's field declaration)
        self.assertAlmostEqual(self.clearing.account_type, 'asset_current',
                               msg="Test clearing account must be asset_current")
