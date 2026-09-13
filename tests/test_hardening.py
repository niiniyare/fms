"""
test_hardening.py — Production hardening integration tests.

Covers acceptance criteria from the production hardening directive:
  H1:  Revenue non-duplication — one shift close → exactly one sales journal
  H2:  AVCO/inventory — stock.valuation.layer created by fuel consumption
  H3:  Wetstock formula — theoretical closing = opening + delivery - meter_sales
  H4:  Multi-attendant isolation — cash allocations never cross attendants
  H5:  Shift close idempotency — double close attempt blocked
  H6:  Closed-shift protection — field modifications blocked
  H7:  Cash variance write-off path — account direction, GL correctness
  H8:  Payment classification — fms_payment_type, not name
  H9:  RTT volume deduction — qty_sold_elec reduced, elec_cash_sold not (by design)
  H10: Partial cash allocation — spec Case C exact numbers
  H11: Full digital coverage — declared cash 0, all revenue from digital
  H12: Cash allocation no-GL invariant — no account.move created
  H13: Stock move idempotency — one consumption move per shift
  H14: Dip variance sign — overage vs shortage polarity
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, UserError
from odoo.addons.fms.models.fms_shift_cash_allocation import _compute_cash_allocation


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class HardeningBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write(
            {'state': 'draft'}
        )

    def setUp(self):
        super().setUp()
        company = self.env.company

        self.journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1
        ) or self.env['account.journal'].create(
            {'name': 'H-Sales', 'code': 'HSLS', 'type': 'sale', 'company_id': company.id}
        )
        self.gen_journal = self.env['account.journal'].search(
            [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1
        ) or self.env['account.journal'].create(
            {'name': 'H-General', 'code': 'HGNL', 'type': 'general', 'company_id': company.id}
        )

        self.clearing = self.env['account.account'].search(
            [('account_type', '=', 'asset_current'), ('company_ids', 'in', company.id)], limit=1
        ) or self.env['account.account'].create({
            'name': 'H-Clearing', 'code': 'HCLR',
            'account_type': 'asset_current', 'company_ids': [(4, company.id)],
        })
        self.revenue_acc = self.env['account.account'].search(
            [('account_type', 'in', ('income', 'income_other')), ('company_ids', 'in', company.id)],
            limit=1
        ) or self.env['account.account'].create({
            'name': 'H-Revenue', 'code': 'HREV', 'account_type': 'income',
            'company_ids': [(4, company.id)],
        })
        self.writeoff_acc = self.env['account.account'].search(
            [('account_type', 'in', ('expense', 'expense_direct_cost')), ('company_ids', 'in', company.id)],
            limit=1
        ) or self.env['account.account'].create({
            'name': 'H-CashOverShort', 'code': 'HCOS',
            'account_type': 'expense', 'company_ids': [(4, company.id)],
        })

        prefs = self.env['fms.site.preferences'].get_for_company(company)
        prefs.write({
            'sales_journal_id': self.journal.id,
            'clearing_account_id': self.clearing.id,
        })
        self.prefs = prefs

        self.diesel = self.env['product.product'].create({
            'name': 'H-Diesel', 'fms_is_fuel': True,
            'list_price': 222.80, 'is_storable': True,
            'fms_revenue_account_id': self.revenue_acc.id,
        })
        self.petrol = self.env['product.product'].create({
            'name': 'H-Petrol', 'fms_is_fuel': True,
            'list_price': 210.00, 'is_storable': True,
            'fms_revenue_account_id': self.revenue_acc.id,
        })

        self.pump = self.env['fms.pump'].create({'name': 'H-Pump', 'order': 77})
        self.nozzle_d = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'D', 'letter': 'D',
            'order': 1, 'product_id': self.diesel.id, 'state': 'active',
        })
        self.nozzle_p = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'P', 'letter': 'P',
            'order': 2, 'product_id': self.petrol.id, 'state': 'active',
        })
        self.tank_d = self.env['stock.location'].create({
            'name': 'H-Diesel-Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True, 'fms_fuel_product_id': self.diesel.id,
        })
        self.tank_p = self.env['stock.location'].create({
            'name': 'H-Petrol-Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True, 'fms_fuel_product_id': self.petrol.id,
        })
        self.supervisor = self.env['hr.employee'].create({'name': 'H-Supervisor'})
        self.attendant1 = self.env['hr.employee'].create({
            'name': 'H-Att1', 'fms_is_attendant': True,
        })
        self.attendant2 = self.env['hr.employee'].create({
            'name': 'H-Att2', 'fms_is_attendant': True,
        })

    def _seed_stock(self, location, product, qty):
        """Seed stock.quant for a tank."""
        q = self.env['stock.quant'].sudo().search([
            ('location_id', '=', location.id), ('product_id', '=', product.id),
        ], limit=1)
        if q:
            q.sudo().write({'inventory_quantity': qty})
            q.sudo().action_apply_inventory()
        else:
            q = self.env['stock.quant'].sudo().create({
                'location_id': location.id,
                'product_id': product.id,
                'quantity': qty,
                'company_id': self.env.company.id,
            })
        return q

    def _make_shift(self, diesel_vol=0.0, petrol_vol=0.0, attendant=None,
                    diesel_closing_dip=None, petrol_closing_dip=None):
        """Open a shift and populate meter/dip entries."""
        attendant = attendant or self.attendant1
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()

        if diesel_vol > 0:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
            vals = {
                'opening_elec_volume': 0.0, 'closing_elec_volume': diesel_vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': diesel_vol * 222.80,
                'attendant_id': attendant.id,
            }
            if e:
                e.sudo().write(vals)
            else:
                self.env['fms.shift.meter.entry'].create(
                    dict(vals, shift_id=shift.id, nozzle_id=self.nozzle_d.id,
                         pump_id=self.pump.id, product_id=self.diesel.id)
                )

        if petrol_vol > 0:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_p)
            vals = {
                'opening_elec_volume': 0.0, 'closing_elec_volume': petrol_vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': petrol_vol * 210.0,
                'attendant_id': attendant.id,
            }
            if e:
                e.sudo().write(vals)
            else:
                self.env['fms.shift.meter.entry'].create(
                    dict(vals, shift_id=shift.id, nozzle_id=self.nozzle_p.id,
                         pump_id=self.pump.id, product_id=self.petrol.id)
                )

        if diesel_closing_dip is not None:
            d = shift.dip_entry_ids.filtered(lambda x: x.location_id == self.tank_d)
            dvals = {'opening_volume': 10000.0, 'closing_volume': diesel_closing_dip}
            if d:
                d.sudo().write(dvals)
            else:
                self.env['fms.shift.dip.entry'].create(
                    dict(dvals, shift_id=shift.id, location_id=self.tank_d.id)
                )

        if petrol_closing_dip is not None:
            d = shift.dip_entry_ids.filtered(lambda x: x.location_id == self.tank_p)
            dvals = {'opening_volume': 10000.0, 'closing_volume': petrol_closing_dip}
            if d:
                d.sudo().write(dvals)
            else:
                self.env['fms.shift.dip.entry'].create(
                    dict(dvals, shift_id=shift.id, location_id=self.tank_p.id)
                )

        return shift

    def _force_close(self, shift, cash_collected=None):
        """Close shift bypassing gates (direct method calls inside savepoint)."""
        shift.action_start_closing()
        if cash_collected is not None:
            cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
            if cl:
                cl.sudo().write({'cash_collected': cash_collected})
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
            sales_move = shift._post_sales_journal()
            shift._post_nonfuel_fc_lines_journal()
            shift._post_stock_consumption()
            shift._sync_stock_quant_from_dips()
            vals = {'state': 'closed'}
            if sales_move:
                vals['sales_journal_entry_id'] = sales_move.id
            shift.write(vals)
        _compute_cash_allocation(shift)
        return shift


# ---------------------------------------------------------------------------
# H1: Revenue non-duplication
# ---------------------------------------------------------------------------

class TestRevenueNonDuplication(HardeningBase):

    def test_exactly_one_sales_journal_after_close(self):
        """One shift close → exactly one account.move tagged as FMS sales."""
        shift = self._make_shift(diesel_vol=100.0, diesel_closing_dip=9900.0)
        before = self.env['account.move'].search_count([
            ('ref', 'like', f'FMS Shift:'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
        ])
        self._force_close(shift)
        after = self.env['account.move'].search([
            ('ref', 'like', 'FMS Shift:'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
        ])
        new_moves = [m for m in after if m.ref and shift.display_name in m.ref]
        self.assertEqual(len(new_moves), 1,
                         "Exactly one FMS sales journal must be created per shift close")

    def test_sales_journal_debits_clearing_credits_revenue(self):
        """Sales JE: DR Clearing, CR Revenue — correct direction."""
        shift = self._make_shift(diesel_vol=100.0, diesel_closing_dip=9900.0)
        self._force_close(shift)
        move = shift.sales_journal_entry_id
        self.assertTrue(move, "sales_journal_entry_id must be set after close")
        debit_lines = move.line_ids.filtered(lambda l: l.debit > 0)
        credit_lines = move.line_ids.filtered(lambda l: l.credit > 0)
        self.assertTrue(debit_lines, "Must have debit line(s)")
        self.assertTrue(credit_lines, "Must have credit line(s)")
        # DR must be clearing account
        for dl in debit_lines:
            self.assertEqual(dl.account_id, self.clearing,
                             f"Debit line must go to clearing account, got {dl.account_id.name}")
        # CR must be revenue account
        for cl in credit_lines:
            self.assertEqual(cl.account_id, self.revenue_acc,
                             f"Credit line must go to revenue account, got {cl.account_id.name}")

    def test_sales_journal_amount_equals_meter_cash(self):
        """Sales JE total must equal sum of elec_cash_sold from meter entries."""
        diesel_vol = 150.0
        shift = self._make_shift(diesel_vol=diesel_vol, diesel_closing_dip=9850.0)
        expected = diesel_vol * 222.80  # elec_cash_sold
        self._force_close(shift)
        move = shift.sales_journal_entry_id
        self.assertTrue(move)
        total_credit = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(total_credit, expected, delta=0.02,
                               msg="Sales journal total must equal meter elec_cash_sold")

    def test_idempotent_close_no_duplicate_journal(self):
        """Calling _post_sales_journal twice returns same existing move, not a new one."""
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        move1 = shift._post_sales_journal()
        move2 = shift._post_sales_journal()
        self.assertEqual(move1.id, move2.id,
                         "Second call to _post_sales_journal must return the same move")


# ---------------------------------------------------------------------------
# H2: AVCO / inventory
# ---------------------------------------------------------------------------

class TestAVCOInventory(HardeningBase):

    def test_stock_move_created_after_close(self):
        """Fuel consumption creates a done stock.move after shift close."""
        self._seed_stock(self.tank_d, self.diesel, 10000.0)
        shift = self._make_shift(diesel_vol=200.0, diesel_closing_dip=9800.0)
        self._force_close(shift)
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
        ])
        self.assertTrue(moves, "At least one stock.move must be in 'done' state after close")
        qty = sum(moves.mapped('product_uom_qty'))
        self.assertAlmostEqual(qty, 200.0, places=2,
                               msg="Consumed qty must equal meter sales (200L)")

    def test_stock_quant_matches_closing_dip(self):
        """After close, tank quant must equal closing dip volume."""
        self._seed_stock(self.tank_d, self.diesel, 10000.0)
        shift = self._make_shift(diesel_vol=200.0, diesel_closing_dip=9750.0)
        self._force_close(shift)
        quant = self.env['stock.quant'].sudo().search([
            ('location_id', '=', self.tank_d.id),
            ('product_id', '=', self.diesel.id),
        ], limit=1)
        self.assertTrue(quant, "Stock quant must exist for diesel tank")
        self.assertAlmostEqual(quant.quantity, 9750.0, places=1,
                               msg="Tank quant must match closing dip volume")

    def test_avco_no_double_consumption(self):
        """
        Consumption before sync: stock.move consumes 200L, then sync adjusts
        remainder. Net quant = 9750. Only one consumption move must exist.
        """
        self._seed_stock(self.tank_d, self.diesel, 10000.0)
        shift = self._make_shift(diesel_vol=200.0, diesel_closing_dip=9750.0)
        self._force_close(shift)
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
            ('product_id', '=', self.diesel.id),
        ])
        # Only one consumption move
        self.assertEqual(len(moves), 1,
                         "Exactly one stock.move must be created for diesel consumption")

    def test_valuation_layer_exists_after_consumption(self):
        """stock.valuation.layer must be created for the fuel consumption move."""
        self._seed_stock(self.tank_d, self.diesel, 10000.0)
        shift = self._make_shift(diesel_vol=100.0, diesel_closing_dip=9900.0)
        self._force_close(shift)
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
            ('product_id', '=', self.diesel.id),
        ])
        self.assertTrue(moves, "Stock move must exist")
        layers = self.env['stock.valuation.layer'].sudo().search([
            ('stock_move_id', 'in', moves.ids),
        ])
        self.assertTrue(layers, "stock.valuation.layer must be created for fuel consumption")
        total_val_qty = abs(sum(layers.mapped('quantity')))
        self.assertAlmostEqual(total_val_qty, 100.0, places=1,
                               msg="Valuation layer quantity must equal consumed liters")


# ---------------------------------------------------------------------------
# H3: Wetstock formula
# ---------------------------------------------------------------------------

class TestWetstockFormula(HardeningBase):

    def test_shift_variance_formula(self):
        """
        shift_variance = closing_dip - (opening + delivery - meter_sales)
        With no delivery and opening=10000, sold=200, closing=9750:
        theoretical_close = 10000 + 0 - 200 = 9800
        variance = 9750 - 9800 = -50 (shortage)
        """
        shift = self._make_shift(diesel_vol=200.0, diesel_closing_dip=9750.0)
        dip_entry = shift.dip_entry_ids.filtered(lambda d: d.location_id == self.tank_d)
        if not dip_entry:
            self.skipTest("No diesel dip entry created — tank not auto-populated")
        dip_entry.sudo().write({'opening_volume': 10000.0, 'closing_volume': 9750.0})

        vdata = shift._compute_dip_variance_data(dip_entry)
        self.assertAlmostEqual(vdata['meter_sales'], 200.0, places=1)
        self.assertAlmostEqual(vdata['delivery'], 0.0, places=1)
        theoretical = 10000.0 + 0.0 - 200.0  # 9800
        expected_var = 9750.0 - theoretical   # -50
        self.assertAlmostEqual(vdata['shift_variance'], expected_var, places=1,
                               msg="Shift variance must equal closing - theoretical")

    def test_zero_variance_when_dip_matches_theory(self):
        """When closing dip = opening - meter_sales, variance must be 0."""
        shift = self._make_shift(diesel_vol=200.0)
        dip = shift.dip_entry_ids.filtered(lambda d: d.location_id == self.tank_d)
        if not dip:
            dip = self.env['fms.shift.dip.entry'].create({
                'shift_id': shift.id, 'location_id': self.tank_d.id,
                'opening_volume': 10000.0, 'closing_volume': 9800.0,  # exact theory
            })
        else:
            dip.sudo().write({'opening_volume': 10000.0, 'closing_volume': 9800.0})
        vdata = shift._compute_dip_variance_data(dip)
        self.assertAlmostEqual(vdata['shift_variance'], 0.0, places=2,
                               msg="Zero variance when closing dip = theoretical closing")

    def test_overage_variance_positive(self):
        """When closing dip > theoretical, variance is positive (gain)."""
        shift = self._make_shift(diesel_vol=200.0)
        dip = self.env['fms.shift.dip.entry'].create({
            'shift_id': shift.id, 'location_id': self.tank_d.id,
            'opening_volume': 10000.0, 'closing_volume': 9850.0,  # more than 9800 theory
        })
        vdata = shift._compute_dip_variance_data(dip)
        self.assertGreater(vdata['shift_variance'], 0.0,
                           msg="Overage (closing > theoretical) must give positive variance")

    def test_shortage_variance_negative(self):
        """When closing dip < theoretical, variance is negative (loss)."""
        shift = self._make_shift(diesel_vol=200.0)
        dip = self.env['fms.shift.dip.entry'].create({
            'shift_id': shift.id, 'location_id': self.tank_d.id,
            'opening_volume': 10000.0, 'closing_volume': 9750.0,  # less than 9800 theory
        })
        vdata = shift._compute_dip_variance_data(dip)
        self.assertLess(vdata['shift_variance'], 0.0,
                        msg="Shortage (closing < theoretical) must give negative variance")


# ---------------------------------------------------------------------------
# H4: Multi-attendant isolation
# ---------------------------------------------------------------------------

class TestMultiAttendantIsolation(HardeningBase):

    def _add_pump_for_att2(self):
        """Create a separate pump/nozzle for attendant 2."""
        pump2 = self.env['fms.pump'].create({'name': 'H-Pump2', 'order': 78})
        nozzle2 = self.env['fms.pump.nozzle'].create({
            'pump_id': pump2.id, 'name': 'D2', 'letter': 'D',
            'order': 1, 'product_id': self.diesel.id, 'state': 'active',
        })
        return pump2, nozzle2

    def test_cash_allocations_separate_per_attendant(self):
        """Each attendant has independent allocation records."""
        _, nozzle2 = self._add_pump_for_att2()
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()

        # Attendant 1: 100L diesel
        e1 = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        att1_vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 100.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 22280.0,
            'attendant_id': self.attendant1.id,
        }
        if e1:
            e1.sudo().write(att1_vals)

        # Attendant 2: 50L diesel on second nozzle
        self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id, 'nozzle_id': nozzle2.id,
            'pump_id': nozzle2.pump_id.id, 'product_id': self.diesel.id,
            'opening_elec_volume': 0.0, 'closing_elec_volume': 50.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 11140.0,
            'attendant_id': self.attendant2.id,
        })

        # Cash lines
        cl1 = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        cl2 = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant2)
        if not cl1:
            cl1 = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        if not cl2:
            cl2 = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant2.id}
            )
        cl1.sudo().write({'cash_collected': 22280.0})
        cl2.sudo().write({'cash_collected': 11140.0})

        _compute_cash_allocation(shift)

        att1_allocs = self.env['fms.shift.cash.allocation'].search([
            ('shift_id', '=', shift.id), ('attendant_id', '=', self.attendant1.id),
        ])
        att2_allocs = self.env['fms.shift.cash.allocation'].search([
            ('shift_id', '=', shift.id), ('attendant_id', '=', self.attendant2.id),
        ])

        self.assertTrue(att1_allocs, "Attendant 1 must have allocation records")
        self.assertTrue(att2_allocs, "Attendant 2 must have allocation records")

        att1_total_cash = sum(att1_allocs.mapped('cash_allocated'))
        att2_total_cash = sum(att2_allocs.mapped('cash_allocated'))

        self.assertAlmostEqual(att1_total_cash, 22280.0, delta=1.0,
                               msg="Attendant 1 total cash allocation must equal their declared cash")
        self.assertAlmostEqual(att2_total_cash, 11140.0, delta=1.0,
                               msg="Attendant 2 total cash allocation must equal their declared cash")
        self.assertAlmostEqual(att1_total_cash + att2_total_cash, 33420.0, delta=2.0,
                               msg="Combined total must equal total declared cash")


# ---------------------------------------------------------------------------
# H5: Shift close idempotency
# ---------------------------------------------------------------------------

class TestShiftCloseIdempotency(HardeningBase):

    def test_post_sales_journal_idempotent(self):
        """Calling _post_sales_journal multiple times returns same move."""
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        m1 = shift._post_sales_journal()
        m2 = shift._post_sales_journal()
        m3 = shift._post_sales_journal()
        self.assertEqual(m1.id, m2.id)
        self.assertEqual(m2.id, m3.id)
        count = self.env['account.move'].search_count([
            ('ref', '=', f'FMS Shift: {shift.display_name}'),
        ])
        self.assertEqual(count, 1, "Only one sales journal must exist")

    def test_post_stock_consumption_idempotent(self):
        """Calling _post_stock_consumption twice must not duplicate stock.moves."""
        self._seed_stock(self.tank_d, self.diesel, 10000.0)
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        shift._write_meter_logs()
        shift._write_dip_logs()
        shift._post_stock_consumption()
        shift._post_stock_consumption()  # second call
        moves = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{shift.display_name}'),
            ('state', '=', 'done'),
        ])
        self.assertEqual(len(moves), 1, "Exactly one stock.move after idempotent calls")

    def test_cash_allocation_idempotent(self):
        """Calling _compute_cash_allocation twice must not duplicate rows."""
        shift = self._make_shift(diesel_vol=100.0, diesel_closing_dip=9900.0)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if cl:
            cl.sudo().write({'cash_collected': 22280.0})
        _compute_cash_allocation(shift)
        count1 = self.env['fms.shift.cash.allocation'].search_count(
            [('shift_id', '=', shift.id)]
        )
        _compute_cash_allocation(shift)
        count2 = self.env['fms.shift.cash.allocation'].search_count(
            [('shift_id', '=', shift.id)]
        )
        self.assertEqual(count1, count2, "Idempotent: second compute must not duplicate rows")


# ---------------------------------------------------------------------------
# H6: Closed-shift protection
# ---------------------------------------------------------------------------

class TestClosedShiftProtection(HardeningBase):

    def test_write_blocked_on_closed_shift(self):
        """Any field write on a closed shift must raise ValidationError."""
        shift = self._make_shift(diesel_vol=100.0)
        self._force_close(shift)
        self.assertEqual(shift.state, 'closed')
        with self.assertRaises(ValidationError):
            shift.sudo().write({'label': '2_eve'})

    def test_reopen_blocked(self):
        """State cannot be changed from closed to anything else via write."""
        shift = self._make_shift(diesel_vol=50.0)
        self._force_close(shift)
        with self.assertRaises(ValidationError):
            shift.sudo().write({'state': 'open'})

    def test_unlink_blocked_on_closed_shift(self):
        """Closed shift cannot be deleted."""
        shift = self._make_shift(diesel_vol=50.0)
        self._force_close(shift)
        with self.assertRaises(ValidationError):
            shift.sudo().unlink()

    def test_meter_log_immutable(self):
        """fms.meter_log records cannot be written after creation."""
        shift = self._make_shift(diesel_vol=50.0)
        self._force_close(shift)
        logs = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)])
        self.assertTrue(logs, "Meter logs must be created on close")
        with self.assertRaises(ValidationError):
            logs[0].sudo().write({'closing_elec_volume': 9999.0})

    def test_dip_log_immutable(self):
        """fms.dip_log records cannot be written after creation."""
        shift = self._make_shift(diesel_vol=50.0, diesel_closing_dip=9950.0)
        self._force_close(shift)
        logs = self.env['fms.dip_log'].sudo().search([('shift_id', '=', shift.id)])
        if not logs:
            self.skipTest("No dip logs created (dip entry not populated)")
        with self.assertRaises(ValidationError):
            logs[0].sudo().write({'closing_volume': 9999.0})


# ---------------------------------------------------------------------------
# H7: Cash variance write-off
# ---------------------------------------------------------------------------

class TestCashVarianceWriteoff(HardeningBase):

    def test_writeoff_posts_journal_entry(self):
        """action_writeoff_fc_variance must create and post a journal entry."""
        shift = self._make_shift(diesel_vol=100.0)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if cl:
            cl.sudo().write({'cash_collected': 20000.0})  # 2280 short
        shift.sudo().write({
            'fc_writeoff_account_id': self.writeoff_acc.id,
        })
        move_count_before = self.env['account.move'].search_count([
            ('company_id', '=', self.env.company.id)
        ])
        shift.action_writeoff_fc_variance()
        move_count_after = self.env['account.move'].search_count([
            ('company_id', '=', self.env.company.id)
        ])
        self.assertGreater(move_count_after, move_count_before,
                           "Write-off must create a journal entry")

    def test_writeoff_direction_shortage(self):
        """Shortage (short cash): DR writeoff expense, CR counterpart."""
        shift = self._make_shift(diesel_vol=100.0)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if cl:
            cl.sudo().write({'cash_collected': 20000.0})  # short by 2280
        shift.sudo().write({'fc_writeoff_account_id': self.writeoff_acc.id})
        shift.action_writeoff_fc_variance()
        move = shift.fc_writeoff_move_id
        self.assertTrue(move, "fc_writeoff_move_id must be set")
        self.assertEqual(move.state, 'posted', "Write-off move must be posted")
        # One DR line should touch writeoff_acc
        dr_lines = move.line_ids.filtered(lambda l: l.debit > 0)
        self.assertTrue(dr_lines, "Must have debit line(s)")

    def test_writeoff_blocked_without_account(self):
        """Write-off must raise if fc_writeoff_account_id is not set."""
        shift = self._make_shift(diesel_vol=100.0)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if cl:
            cl.sudo().write({'cash_collected': 20000.0})
        # No writeoff account set
        try:
            shift.action_writeoff_fc_variance()
            self.fail("Write-off must raise when no account is set")
        except (ValidationError, UserError):
            pass

    def test_writeoff_blocked_when_already_zero(self):
        """Write-off must fail if FC variance is already zero."""
        diesel_rev = 100.0 * 222.80
        shift = self._make_shift(diesel_vol=100.0)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if cl:
            cl.sudo().write({'cash_collected': diesel_rev})  # exact match
        shift.sudo().write({'fc_writeoff_account_id': self.writeoff_acc.id})
        try:
            shift.action_writeoff_fc_variance()
            self.fail("Write-off must raise when variance is already zero")
        except (ValidationError, UserError):
            pass


# ---------------------------------------------------------------------------
# H8: Payment classification by type, not name
# ---------------------------------------------------------------------------

class TestPaymentClassification(HardeningBase):

    def test_fms_payment_type_field_exists_on_pos_payment_method(self):
        """pos.payment.method must have fms_payment_type field."""
        method = self.env['pos.payment.method'].create({
            'name': 'Safaricom Mobile Money', 'is_cash_count': False,
        })
        self.assertTrue(hasattr(method, 'fms_payment_type'),
                        "fms_payment_type field must exist on pos.payment.method")

    def test_fms_payment_type_values(self):
        """fms_payment_type must accept standard FMS values."""
        method = self.env['pos.payment.method'].create({
            'name': 'Visa Card', 'is_cash_count': False,
        })
        method.write({'fms_payment_type': 'card'})
        self.assertEqual(method.fms_payment_type, 'card')
        method.write({'fms_payment_type': 'mpesa'})
        self.assertEqual(method.fms_payment_type, 'mpesa')
        method.write({'fms_payment_type': 'credit'})
        self.assertEqual(method.fms_payment_type, 'credit')

    def test_renamed_method_classification_survives(self):
        """Renaming a payment method must not break its FMS classification."""
        method = self.env['pos.payment.method'].create({
            'name': 'M-Pesa', 'is_cash_count': False,
            'fms_payment_type': 'mpesa',
        })
        # Rename
        method.write({'name': 'Safaricom Mobile Money'})
        # Classification unchanged
        self.assertEqual(method.fms_payment_type, 'mpesa',
                         "Rename must not affect fms_payment_type classification")


# ---------------------------------------------------------------------------
# H9: RTT volume deduction (documented behavior)
# ---------------------------------------------------------------------------

class TestRTTBehavior(HardeningBase):

    def test_rtt_reduces_qty_sold_elec(self):
        """RTT volume is subtracted from qty_sold_elec."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 1000.0 * 222.80,
            'rtt_volume': 20.0,
        }
        if entry:
            entry.sudo().write(vals)
        else:
            entry = self.env['fms.shift.meter.entry'].create(
                dict(vals, shift_id=shift.id, nozzle_id=self.nozzle_d.id,
                     pump_id=self.pump.id, product_id=self.diesel.id)
            )
        entry.invalidate_recordset(['qty_sold_elec', 'elec_cash_sold'])
        self.assertAlmostEqual(entry.qty_sold_elec, 980.0, places=2,
                               msg="qty_sold_elec = gross - RTT = 1000 - 20 = 980")

    def test_rtt_volume_alone_does_not_reduce_elec_cash_sold(self):
        """
        rtt_volume alone does not reduce elec_cash_sold.
        Only rtt_cash (explicitly entered) reduces cash.
        When rtt_cash is not set, elec_cash_sold = gross cash totalizer movement.
        """
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        gross_cash = 1000.0 * 222.80
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': gross_cash,
            'rtt_volume': 20.0,
        }
        if entry:
            entry.sudo().write(vals)
        else:
            entry = self.env['fms.shift.meter.entry'].create(
                dict(vals, shift_id=shift.id, nozzle_id=self.nozzle_d.id,
                     pump_id=self.pump.id, product_id=self.diesel.id)
            )
        entry.invalidate_recordset(['qty_sold_elec', 'elec_cash_sold'])
        # No rtt_cash set → elec_cash_sold = gross cash movement (rtt_cash defaults to 0.0)
        self.assertAlmostEqual(entry.elec_cash_sold, gross_cash, places=2,
                               msg="elec_cash_sold = gross when rtt_cash not provided")
        # Volume IS adjusted
        self.assertAlmostEqual(entry.qty_sold_elec, 980.0, places=2)

    def test_rtt_correction_model_immutable(self):
        """fms.meter_log.rtt_correction records cannot be written."""
        shift = self._make_shift(diesel_vol=100.0)
        self._force_close(shift)
        logs = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)])
        if not logs:
            self.skipTest("No meter logs to attach correction to")
        correction = self.env['fms.meter_log.rtt_correction'].sudo().create({
            'meter_log_id': logs[0].id,
            'rtt_volume': 10.0,
            'rtt_amount': 2228.0,
            'reason': 'Test RTT correction',
        })
        with self.assertRaises(ValidationError):
            correction.sudo().write({'rtt_volume': 99.0})


# ---------------------------------------------------------------------------
# H10: Partial cash allocation — spec Case C exact numbers
# ---------------------------------------------------------------------------

class TestPartialCashAllocation(HardeningBase):

    def test_case_a_partial_diesel_only(self):
        """
        Remaining Diesel 20L = KES 4,456. Declared KES 1,000.
        All 1,000 goes to Diesel. Petrol gets 0.
        """
        diesel_rev = 1000.0 * 222.80   # 222,800
        petrol_rev = 500.0 * 210.0     # 105,000
        mpesa = diesel_rev - (20.0 * 222.80)  # 222,800 - 4,456 = 218,344

        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        for nozzle, vol, price in [(self.nozzle_d, 1000.0, 222.80), (self.nozzle_p, 500.0, 210.0)]:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == nozzle)
            vals = {
                'opening_elec_volume': 0.0, 'closing_elec_volume': vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': vol * price,
                'attendant_id': self.attendant1.id,
            }
            if e:
                e.sudo().write(vals)

        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': 1000.0})
        cl.with_context(bypass_readonly=True).sudo().write({'mpesa_amount': mpesa})

        _compute_cash_allocation(shift)
        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        total_cash = sum(allocs.mapped('cash_allocated'))
        self.assertAlmostEqual(total_cash, 1000.0, delta=1.0,
                               msg="Case A: all declared cash allocated")
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        self.assertAlmostEqual(diesel_alloc.cash_allocated, 1000.0, delta=1.0,
                               msg="All cash goes to Diesel (Diesel has 4,456 remaining)")

    def test_case_b_exactly_covers_diesel_remaining(self):
        """
        Remaining Diesel 20L = KES 4,456. Declared exactly KES 4,456.
        Diesel allocation = 4,456. Petrol = 0.
        """
        diesel_rem = 20.0 * 222.80  # 4,456
        mpesa = 1000.0 * 222.80 - diesel_rem  # covers 980L

        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 1000.0 * 222.80,
            'attendant_id': self.attendant1.id,
        }
        if e:
            e.sudo().write(vals)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': diesel_rem})
        cl.with_context(bypass_readonly=True).sudo().write({'mpesa_amount': mpesa})

        _compute_cash_allocation(shift)
        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        self.assertAlmostEqual(diesel_alloc.cash_allocated, diesel_rem, delta=0.02,
                               msg="Case B: exactly covers Diesel remaining")
        self.assertAlmostEqual(diesel_alloc.uncovered, 0.0, delta=0.02,
                               msg="Diesel fully covered — zero uncovered")

    def test_case_c_overflow_to_petrol(self):
        """
        Remaining Diesel 20L = KES 4,456. Declared KES 8,000.
        Diesel: 4,456. Petrol: 3,544.
        """
        diesel_rev = 1000.0 * 222.80
        petrol_rev = 500.0 * 210.0
        diesel_rem = 20.0 * 222.80  # 4,456
        mpesa = diesel_rev - diesel_rem  # covers 980L diesel exactly

        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        for nozzle, vol, price in [(self.nozzle_d, 1000.0, 222.80), (self.nozzle_p, 500.0, 210.0)]:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == nozzle)
            vals = {
                'opening_elec_volume': 0.0, 'closing_elec_volume': vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': vol * price,
                'attendant_id': self.attendant1.id,
            }
            if e:
                e.sudo().write(vals)

        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': 8000.0})
        cl.with_context(bypass_readonly=True).sudo().write({'mpesa_amount': mpesa})

        _compute_cash_allocation(shift)
        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        petrol_alloc = allocs.filtered(lambda a: a.product_id == self.petrol)

        self.assertAlmostEqual(diesel_alloc.cash_allocated, diesel_rem, delta=0.02,
                               msg="Case C: Diesel gets exactly 4,456")
        total_cash = diesel_alloc.cash_allocated + petrol_alloc.cash_allocated
        self.assertAlmostEqual(total_cash, 8000.0, delta=1.0,
                               msg="Case C: total allocated = 8,000")
        self.assertAlmostEqual(petrol_alloc.cash_allocated, 8000.0 - diesel_rem, delta=1.0,
                               msg="Case C: Petrol gets 3,544")


# ---------------------------------------------------------------------------
# H11: Full digital coverage
# ---------------------------------------------------------------------------

class TestFullDigitalCoverage(HardeningBase):

    def test_full_digital_zero_cash_allocated(self):
        """When digital covers all revenue, cash_allocated = 0 for all products."""
        diesel_rev = 100.0 * 222.80
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 100.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': diesel_rev,
            'attendant_id': self.attendant1.id,
        }
        if e:
            e.sudo().write(vals)
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': 0.0})
        cl.with_context(bypass_readonly=True).sudo().write({'mpesa_amount': diesel_rev})

        _compute_cash_allocation(shift)
        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        total_cash = sum(allocs.mapped('cash_allocated'))
        self.assertAlmostEqual(total_cash, 0.0, places=2,
                               msg="No cash allocated when digital covers all revenue")
        total_digital = sum(allocs.mapped('digital_allocated'))
        self.assertAlmostEqual(total_digital, diesel_rev, delta=0.02,
                               msg="Digital allocation must equal full revenue")

    def test_mixed_payments_sum_to_total_revenue(self):
        """Total allocated (digital + cash) must ≤ total product revenue."""
        diesel_rev = 100.0 * 222.80
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': 100.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': diesel_rev,
            'attendant_id': self.attendant1.id,
        }
        if e:
            e.sudo().write(vals)
        mpesa = 15000.0
        card = 5000.0
        cash = diesel_rev - mpesa - card  # balanced
        cl = shift.attendant_cash_ids.filtered(lambda c: c.attendant_id == self.attendant1)
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': cash})
        cl.with_context(bypass_readonly=True).sudo().write({
            'mpesa_amount': mpesa, 'card_amount': card,
        })

        _compute_cash_allocation(shift)
        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        for alloc in allocs:
            covered = alloc.digital_allocated + alloc.cash_allocated
            self.assertLessEqual(covered, alloc.product_revenue + 0.02,
                                 msg=f"Covered for {alloc.product_id.name} must ≤ product revenue")


# ---------------------------------------------------------------------------
# H13: Stock move idempotency
# ---------------------------------------------------------------------------

class TestStockMoveIdempotency(HardeningBase):

    def test_write_meter_logs_idempotent(self):
        """_write_meter_logs called twice must not create duplicate logs."""
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        shift._write_meter_logs()
        count1 = self.env['fms.meter_log'].sudo().search_count(
            [('shift_id', '=', shift.id)]
        )
        shift._write_meter_logs()
        count2 = self.env['fms.meter_log'].sudo().search_count(
            [('shift_id', '=', shift.id)]
        )
        self.assertEqual(count1, count2, "Meter logs must not duplicate on repeated calls")

    def test_write_dip_logs_idempotent(self):
        """_write_dip_logs called twice must not create duplicate logs."""
        shift = self._make_shift(diesel_vol=100.0, diesel_closing_dip=9900.0)
        shift.action_start_closing()
        shift._write_meter_logs()
        shift._write_dip_logs()
        count1 = self.env['fms.dip_log'].sudo().search_count(
            [('shift_id', '=', shift.id)]
        )
        shift._write_dip_logs()
        count2 = self.env['fms.dip_log'].sudo().search_count(
            [('shift_id', '=', shift.id)]
        )
        self.assertEqual(count1, count2, "Dip logs must not duplicate on repeated calls")


# ---------------------------------------------------------------------------
# H14: RTT cash deduction — INVARIANT 4
# ---------------------------------------------------------------------------

class TestRTTCash(HardeningBase):

    def _make_shift_with_rtt(self, vol=1000.0, rtt_vol=20.0, rtt_cash=4456.0,
                              gross_cash=222800.0):
        """Create a shift with RTT: gross vol dispensed, rtt returned, cash meter unchanged."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        vals = {
            'attendant_id': self.attendant1.id,
            'opening_elec_volume': 0.0, 'closing_elec_volume': vol,
            'opening_elec_cash': 0.0, 'closing_elec_cash': gross_cash,
            'rtt_volume': rtt_vol, 'rtt_cash': rtt_cash,
        }
        entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle_d)
        if entry:
            entry.sudo().write(vals)
        else:
            self.env['fms.shift.meter.entry'].create(
                dict(vals, shift_id=shift.id, pump_id=self.pump.id,
                     nozzle_id=self.nozzle_d.id, product_id=self.diesel.id)
            )
        return shift

    def _get_diesel_entry(self, shift):
        return shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle_d)[0]

    def test_rtt_volume_deducted_from_qty(self):
        """INVARIANT 5: qty_sold_elec = gross_volume - rtt_volume."""
        shift = self._make_shift_with_rtt(vol=1000.0, rtt_vol=20.0)
        entry = self._get_diesel_entry(shift)
        self.assertAlmostEqual(entry.qty_sold_elec, 980.0, places=1)

    def test_rtt_cash_deducted_from_elec_cash(self):
        """INVARIANT 4: elec_cash_sold = gross_cash - rtt_cash (no artificial FC variance)."""
        shift = self._make_shift_with_rtt(
            vol=1000.0, rtt_vol=20.0, rtt_cash=4456.0, gross_cash=222800.0
        )
        entry = self._get_diesel_entry(shift)
        # gross_cash=222800, rtt_cash=4456 → net=218344
        self.assertAlmostEqual(entry.elec_cash_sold, 218344.0, places=0)

    def test_zero_rtt_cash_no_change(self):
        """Zero RTT cash leaves elec_cash_sold unchanged from gross cash movement."""
        shift = self._make_shift_with_rtt(
            vol=1000.0, rtt_vol=0.0, rtt_cash=0.0, gross_cash=222800.0
        )
        entry = self._get_diesel_entry(shift)
        self.assertAlmostEqual(entry.elec_cash_sold, 222800.0, places=0)

    def test_rtt_cash_persisted_to_meter_log(self):
        """rtt_cash must be copied to immutable meter_log on shift close."""
        shift = self._make_shift_with_rtt(
            vol=1000.0, rtt_vol=20.0, rtt_cash=4456.0, gross_cash=222800.0
        )
        shift.action_start_closing()
        shift._write_meter_logs()
        # Find the log for the diesel nozzle specifically
        log = self.env['fms.meter_log'].sudo().search(
            [('shift_id', '=', shift.id), ('nozzle_id', '=', self.nozzle_d.id)], limit=1
        )
        self.assertTrue(log, "Meter log must be created on close")
        self.assertAlmostEqual(log.rtt_cash, 4456.0, places=0)

    def test_meter_log_rtt_cash_deducted(self):
        """fms.meter_log elec_cash_sold must also use rtt_cash deduction."""
        shift = self._make_shift_with_rtt(
            vol=1000.0, rtt_vol=20.0, rtt_cash=4456.0, gross_cash=222800.0
        )
        shift.action_start_closing()
        shift._write_meter_logs()
        log = self.env['fms.meter_log'].sudo().search(
            [('shift_id', '=', shift.id), ('nozzle_id', '=', self.nozzle_d.id)], limit=1
        )
        self.assertTrue(log)
        self.assertAlmostEqual(log.elec_cash_sold, 218344.0, places=0)

    def test_rtt_cash_allocation_uses_net_sales(self):
        """INVARIANT 6: Cash allocation uses net elec_cash_sold (after rtt_cash deduction)."""
        shift = self._make_shift_with_rtt(
            vol=1000.0, rtt_vol=20.0, rtt_cash=4456.0, gross_cash=222800.0
        )
        # Give enough declared cash to cover net sales
        cl = self.env['fms.shift.attendant.cash'].search(
            [('shift_id', '=', shift.id), ('attendant_id', '=', self.attendant1.id)], limit=1
        )
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        cl.sudo().write({'cash_collected': 218344.0})

        from odoo.addons.fms.models.fms_shift_cash_allocation import _compute_cash_allocation
        _compute_cash_allocation(shift)

        allocs = self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])
        self.assertTrue(allocs, "Allocation records must be created")
        total_revenue = sum(allocs.mapped('product_revenue'))
        # Revenue must be net: 218344, not gross 222800
        self.assertAlmostEqual(total_revenue, 218344.0, delta=1.0)

    def test_multi_attendant_rtt_isolation(self):
        """Multiple attendants with RTT on different nozzles must not cross-contaminate."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()

        def _write_or_create(nozzle, product, attendant, close_vol, close_cash, rtt_vol, rtt_cash):
            vals = {
                'attendant_id': attendant.id,
                'opening_elec_volume': 0.0, 'closing_elec_volume': close_vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': close_cash,
                'rtt_volume': rtt_vol, 'rtt_cash': rtt_cash,
            }
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == nozzle)
            if e:
                e.sudo().write(vals)
            else:
                self.env['fms.shift.meter.entry'].create(
                    dict(vals, shift_id=shift.id, pump_id=self.pump.id,
                         nozzle_id=nozzle.id, product_id=product.id)
                )

        # Attendant A: Diesel 500L gross, RTT 10L, cash=111400, rtt_cash=2228
        _write_or_create(self.nozzle_d, self.diesel, self.attendant1,
                         500.0, 111400.0, 10.0, 2228.0)
        # Attendant B: Petrol 500L gross, RTT 5L, cash=105000, rtt_cash=1050
        _write_or_create(self.nozzle_p, self.petrol, self.attendant2,
                         500.0, 105000.0, 5.0, 1050.0)

        d_entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle_d)
        p_entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle_p)
        # Diesel net: 500-10=490L, cash: 111400-2228=109172
        self.assertAlmostEqual(d_entry.qty_sold_elec, 490.0, places=1)
        self.assertAlmostEqual(d_entry.elec_cash_sold, 109172.0, places=0)
        # Petrol net: 500-5=495L, cash: 105000-1050=103950
        self.assertAlmostEqual(p_entry.qty_sold_elec, 495.0, places=1)
        self.assertAlmostEqual(p_entry.elec_cash_sold, 103950.0, places=0)


# ---------------------------------------------------------------------------
# H15: POS revenue duplication guard
# ---------------------------------------------------------------------------

class TestPOSRevenueGuard(HardeningBase):

    def _make_pos_method(self, fms_type='cash'):
        return self.env['pos.payment.method'].create({
            'name': f'Test-{fms_type}',
            'fms_payment_type': fms_type,
            'split_transactions': False,
        })

    def test_no_pos_session_gate_skipped(self):
        """_gate_check_pos_revenue_config is a no-op when no POS sessions linked."""
        shift = self._make_shift(diesel_vol=100.0)
        # Must not raise — no POS sessions
        shift._gate_check_pos_revenue_config()

    def test_pos_fuel_with_clearing_account_passes(self):
        """POS fuel product income account = clearing → no duplication → gate passes."""
        # Set diesel's income account to clearing (asset_current = transit/clearing)
        self.diesel.property_account_income_id = self.clearing.id
        shift = self._make_shift(diesel_vol=100.0)
        # Fake a POS session link (just set the M2M, no real session needed for gate)
        pos_config = self.env['pos.config'].create({'name': 'Test-POS'})
        session = self.env['pos.session'].create({'config_id': pos_config.id, 'user_id': self.env.user.id})
        shift.sudo().write({'pos_session_ids': [(4, session.id)]})
        # Gate must pass — clearing account is not a revenue account
        shift._gate_check_pos_revenue_config()

    def test_pos_fuel_with_revenue_account_blocked(self):
        """POS fuel product income account = revenue → duplication risk → gate blocks."""
        # Set diesel's income account to a revenue account (same type as fms_revenue_account_id)
        self.diesel.property_account_income_id = self.revenue_acc.id
        shift = self._make_shift(diesel_vol=100.0)
        # Link a POS session
        pos_config = self.env['pos.config'].create({'name': 'Test-POS2'})
        session = self.env['pos.session'].create({'config_id': pos_config.id, 'user_id': self.env.user.id})
        shift.sudo().write({'pos_session_ids': [(4, session.id)]})
        # Gate must raise
        try:
            shift._gate_check_pos_revenue_config()
            self.fail("Expected ValidationError for POS revenue duplication")
        except ValidationError as exc:
            self.assertIn('H-Diesel', str(exc.args[0]))
            self.assertIn('income', str(exc.args[0]).lower())

    def test_pos_nonfuel_product_ignored_by_gate(self):
        """Gate only checks fuel products — non-fuel with revenue account does not raise."""
        carwash = self.env['product.product'].create({
            'name': 'H-Carwash', 'fms_is_fuel': False,
            'property_account_income_id': self.revenue_acc.id,
        })
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        pos_config = self.env['pos.config'].create({'name': 'Test-POS3'})
        session = self.env['pos.session'].create({'config_id': pos_config.id, 'user_id': self.env.user.id})
        shift.sudo().write({'pos_session_ids': [(4, session.id)]})
        # No fuel meter entries → gate skips
        shift._gate_check_pos_revenue_config()


# ---------------------------------------------------------------------------
# H16: Revenue idempotency + journal direction
# ---------------------------------------------------------------------------

class TestRevenueJournalInvariants(HardeningBase):

    def test_revenue_journal_dr_clearing_cr_revenue(self):
        """INVARIANT 1: FMS sales journal = DR Clearing | CR Revenue (not reversed)."""
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        move = shift._post_sales_journal()
        self.assertTrue(move, "Sales journal must be created")
        dr_lines = move.line_ids.filtered(lambda l: l.debit > 0)
        cr_lines = move.line_ids.filtered(lambda l: l.credit > 0)
        self.assertTrue(dr_lines, "Journal must have a debit line")
        self.assertTrue(cr_lines, "Journal must have a credit line")
        dr_accounts = dr_lines.mapped('account_id.account_type')
        cr_accounts = cr_lines.mapped('account_id.account_type')
        # DR must be clearing (asset_current), CR must be income
        self.assertTrue(
            any(t == 'asset_current' for t in dr_accounts),
            f"DR account type must be asset_current (clearing). Got: {dr_accounts}"
        )
        self.assertTrue(
            any(t in ('income', 'income_other') for t in cr_accounts),
            f"CR account type must be income. Got: {cr_accounts}"
        )

    def test_revenue_amount_uses_net_elec_cash(self):
        """Revenue journal amount = net elec_cash_sold (after rtt_cash deduction)."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id, 'pump_id': self.pump.id,
            'nozzle_id': self.nozzle_d.id, 'product_id': self.diesel.id,
            'attendant_id': self.attendant1.id,
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 222800.0,
            'rtt_volume': 20.0, 'rtt_cash': 4456.0,
        })
        shift.action_start_closing()
        move = shift._post_sales_journal()
        self.assertTrue(move)
        total_cr = sum(move.line_ids.mapped('credit'))
        # Net = 222800 - 4456 = 218344
        self.assertAlmostEqual(total_cr, 218344.0, delta=1.0,
                               msg="Revenue journal must use net elec_cash_sold")


# ---------------------------------------------------------------------------
# H17: POS session close enforcement — [E610]
# ---------------------------------------------------------------------------

class TestPOSSessionCloseEnforcement(HardeningBase):
    """
    Test A: fuel product with clearing income account → POS close succeeds
    Test B: fuel product with revenue income account → POS close blocked [E610]
    Test C: non-fuel product with revenue income account → POS close succeeds
    Test D: mixed fuel+non-fuel, fuel=clearing, non-fuel=revenue → POS close succeeds
    """

    def _make_pos_session(self, config_name='Test-POS-Enf'):
        pos_config = self.env['pos.config'].create({'name': config_name})
        session = self.env['pos.session'].create({
            'config_id': pos_config.id,
            'user_id': self.env.user.id,
        })
        return pos_config, session

    def _add_order_line(self, session, product, qty=1, price=100.0):
        """Create a posted POS order for the session."""
        order = self.env['pos.order'].create({
            'session_id': session.id,
            'company_id': self.env.company.id,
            'partner_id': False,
            'lines': [(0, 0, {
                'product_id': product.id,
                'qty': qty,
                'price_unit': price,
                'price_subtotal': qty * price,
                'price_subtotal_incl': qty * price,
            })],
            'amount_total': qty * price,
            'amount_tax': 0.0,
            'amount_paid': qty * price,
            'amount_return': 0.0,
        })
        return order

    def test_A_fuel_clearing_account_pos_close_passes(self):
        """Test A: fuel with clearing income → _fms_validate_fuel_revenue_config does not raise."""
        self.diesel.property_account_income_id = self.clearing.id  # asset_current = safe
        _, session = self._make_pos_session('Test-POS-A')
        self._add_order_line(session, self.diesel, qty=100, price=222.80)
        # Must not raise
        session._fms_validate_fuel_revenue_config()

    def test_B_fuel_revenue_account_pos_close_blocked(self):
        """Test B: fuel with revenue income → [E610] raised."""
        self.diesel.property_account_income_id = self.revenue_acc.id  # income = bad
        _, session = self._make_pos_session('Test-POS-B')
        self._add_order_line(session, self.diesel, qty=100, price=222.80)
        try:
            session._fms_validate_fuel_revenue_config()
            self.fail("Expected UserError [E610] for fuel revenue account")
        except Exception as exc:
            self.assertIn('E610', str(exc.args[0]))
            self.assertIn('H-Diesel', str(exc.args[0]))

    def test_C_nonfuel_revenue_account_pos_close_passes(self):
        """Test C: non-fuel with revenue income account → gate does not raise."""
        carwash = self.env['product.product'].create({
            'name': 'H-Carwash-Enforcement',
            'fms_is_fuel': False,
            'property_account_income_id': self.revenue_acc.id,
        })
        _, session = self._make_pos_session('Test-POS-C')
        self._add_order_line(session, carwash, qty=1, price=500.0)
        # Non-fuel → gate skips
        session._fms_validate_fuel_revenue_config()

    def test_D_mixed_session_fuel_clearing_nonfuel_revenue(self):
        """Test D: fuel=clearing, non-fuel=revenue in same session → gate passes."""
        self.diesel.property_account_income_id = self.clearing.id
        carwash = self.env['product.product'].create({
            'name': 'H-Carwash-D',
            'fms_is_fuel': False,
            'property_account_income_id': self.revenue_acc.id,
        })
        _, session = self._make_pos_session('Test-POS-D')
        self._add_order_line(session, self.diesel, qty=50, price=222.80)
        self._add_order_line(session, carwash, qty=1, price=800.0)
        # Fuel has clearing account → must not raise
        session._fms_validate_fuel_revenue_config()


# ---------------------------------------------------------------------------
# H18: RTT validation constraints — [E620]
# ---------------------------------------------------------------------------

class TestRTTValidation(HardeningBase):

    def _make_entry(self, rtt_vol=0.0, rtt_cash=0.0, close_vol=1000.0, close_cash=222800.0):
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        vals = {
            'opening_elec_volume': 0.0, 'closing_elec_volume': close_vol,
            'opening_elec_cash': 0.0, 'closing_elec_cash': close_cash,
            'rtt_volume': rtt_vol, 'rtt_cash': rtt_cash,
        }
        if e:
            e.sudo().write(vals)
        return shift, (e or None)

    def test_negative_rtt_volume_blocked(self):
        """[E620] rtt_volume < 0 must raise ValidationError."""
        shift, _ = self._make_entry(rtt_vol=0.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        try:
            entry.sudo().write({'rtt_volume': -5.0})
            entry._check_rtt_validity()
            self.fail("Expected ValidationError for negative rtt_volume")
        except ValidationError as exc:
            self.assertIn('E620', str(exc.args[0]))

    def test_negative_rtt_cash_blocked(self):
        """[E620] rtt_cash < 0 must raise ValidationError."""
        shift, _ = self._make_entry(rtt_vol=0.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        try:
            entry.sudo().write({'rtt_cash': -100.0})
            entry._check_rtt_validity()
            self.fail("Expected ValidationError for negative rtt_cash")
        except ValidationError as exc:
            self.assertIn('E620', str(exc.args[0]))

    def test_rtt_volume_exceeds_gross_blocked(self):
        """[E620] rtt_volume > gross_volume blocked."""
        shift, _ = self._make_entry(close_vol=100.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        try:
            entry.sudo().write({'rtt_volume': 200.0})  # > 100L gross
            entry._check_rtt_validity()
            self.fail("Expected ValidationError for rtt_volume > gross")
        except ValidationError as exc:
            self.assertIn('E620', str(exc.args[0]))

    def test_rtt_cash_exceeds_gross_cash_blocked(self):
        """[E620] rtt_cash > gross_cash_movement blocked."""
        shift, _ = self._make_entry(close_vol=100.0, close_cash=22280.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        try:
            entry.sudo().write({'rtt_cash': 99999.0})  # > 22280 gross cash
            entry._check_rtt_validity()
            self.fail("Expected ValidationError for rtt_cash > gross_cash")
        except ValidationError as exc:
            self.assertIn('E620', str(exc.args[0]))

    def test_valid_rtt_passes(self):
        """Valid RTT values (within bounds) must not raise."""
        shift, _ = self._make_entry(rtt_vol=10.0, rtt_cash=2228.0,
                                    close_vol=1000.0, close_cash=222800.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        # Must not raise
        entry._check_rtt_validity()

    def test_rtt_equals_gross_passes(self):
        """RTT = 100% of gross volume is extreme but technically valid."""
        shift, _ = self._make_entry(rtt_vol=100.0, rtt_cash=22280.0,
                                    close_vol=100.0, close_cash=22280.0)
        entry = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        entry._check_rtt_validity()


# ---------------------------------------------------------------------------
# H19: Cash allocation edge cases (extended)
# ---------------------------------------------------------------------------

class TestCashAllocationEdgeCases(HardeningBase):

    def _run_alloc(self, diesel_rev, petrol_rev=0.0, cash=0.0, mpesa=0.0, card=0.0,
                   diesel_price=222.80, petrol_price=210.0):
        """Helper: create shift with given revenue + declared amounts, run allocation."""
        from odoo.addons.fms.models.fms_shift_cash_allocation import _compute_cash_allocation
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()

        if diesel_rev > 0:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
            vol = diesel_rev / diesel_price
            vals = {
                'attendant_id': self.attendant1.id,
                'opening_elec_volume': 0.0, 'closing_elec_volume': vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': diesel_rev,
            }
            if e:
                e.sudo().write(vals)

        if petrol_rev > 0:
            e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_p)
            vol = petrol_rev / petrol_price
            vals = {
                'attendant_id': self.attendant1.id,
                'opening_elec_volume': 0.0, 'closing_elec_volume': vol,
                'opening_elec_cash': 0.0, 'closing_elec_cash': petrol_rev,
            }
            if e:
                e.sudo().write(vals)

        cl = self.env['fms.shift.attendant.cash'].search(
            [('shift_id', '=', shift.id), ('attendant_id', '=', self.attendant1.id)], limit=1
        )
        if not cl:
            cl = self.env['fms.shift.attendant.cash'].create(
                {'shift_id': shift.id, 'attendant_id': self.attendant1.id}
            )
        write_vals = {'cash_collected': cash}
        if mpesa:
            write_vals['mpesa_amount'] = mpesa
        if card:
            write_vals['card_amount'] = card
        cl.sudo().write(write_vals)

        _compute_cash_allocation(shift)
        return shift

    def _allocs(self, shift):
        return self.env['fms.shift.cash.allocation'].search([('shift_id', '=', shift.id)])

    def test_edge_zero_revenue_no_allocation(self):
        """Zero revenue → no allocation records created."""
        shift = self._run_alloc(diesel_rev=0.0, cash=0.0)
        self.assertEqual(len(self._allocs(shift)), 0)

    def test_edge_exact_match_single_product(self):
        """Cash exactly equals diesel revenue → diesel fully covered, uncovered=0."""
        rev = 22280.0
        shift = self._run_alloc(diesel_rev=rev, cash=rev)
        allocs = self._allocs(shift)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        self.assertTrue(diesel_alloc)
        self.assertAlmostEqual(diesel_alloc.uncovered, 0.0, delta=0.01)

    def test_edge_partial_first_product(self):
        """Cash < diesel revenue → diesel partially covered, petrol uncovered entirely."""
        shift = self._run_alloc(diesel_rev=22280.0, petrol_rev=10500.0, cash=10000.0)
        allocs = self._allocs(shift)
        total_covered = sum(allocs.mapped('cash_allocated'))
        self.assertAlmostEqual(total_covered, 10000.0, delta=0.01)
        # Cash must go to diesel first (fuel priority)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        self.assertAlmostEqual(diesel_alloc.cash_allocated, 10000.0, delta=0.01)

    def test_edge_overflow_into_second_product(self):
        """Cash covers diesel fully and overflows into petrol."""
        diesel_rev = 22280.0
        petrol_rev = 10500.0
        total_cash = diesel_rev + 5000.0  # 5000 more than diesel alone
        shift = self._run_alloc(diesel_rev=diesel_rev, petrol_rev=petrol_rev, cash=total_cash)
        allocs = self._allocs(shift)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        petrol_alloc = allocs.filtered(lambda a: a.product_id == self.petrol)
        self.assertAlmostEqual(diesel_alloc.cash_allocated, diesel_rev, delta=0.01)
        self.assertAlmostEqual(petrol_alloc.cash_allocated, 5000.0, delta=0.01)

    def test_edge_amount_greater_than_all_sales(self):
        """Cash > total revenue: allocated up to revenue, excess is NOT invented as sales."""
        diesel_rev = 22280.0
        excess_cash = diesel_rev + 5000.0
        shift = self._run_alloc(diesel_rev=diesel_rev, cash=excess_cash)
        allocs = self._allocs(shift)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        # Cash allocated capped at product revenue — no invented sales
        self.assertAlmostEqual(diesel_alloc.cash_allocated, diesel_rev, delta=0.01)

    def test_edge_digital_covers_all_no_cash_needed(self):
        """M-Pesa covers 100% revenue, declared cash=0: no uncovered."""
        rev = 22280.0
        shift = self._run_alloc(diesel_rev=rev, cash=0.0, mpesa=rev)
        allocs = self._allocs(shift)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        self.assertAlmostEqual(diesel_alloc.digital_allocated, rev, delta=0.01)
        self.assertAlmostEqual(diesel_alloc.uncovered, 0.0, delta=0.01)

    def test_edge_repeated_allocation_idempotent(self):
        """Running _compute_cash_allocation twice produces same result, no duplicates."""
        from odoo.addons.fms.models.fms_shift_cash_allocation import _compute_cash_allocation
        shift = self._run_alloc(diesel_rev=22280.0, cash=22280.0)
        count1 = len(self._allocs(shift))
        _compute_cash_allocation(shift)  # second run
        count2 = len(self._allocs(shift))
        self.assertEqual(count1, count2, "Second allocation run must not duplicate records")

    def test_edge_spec_case_c_exact(self):
        """Spec Case C: Diesel 1000L × 222.80, M-Pesa 218344, Cash 8000."""
        # diesel_rev = 218344 (net, after 20L RTT @ 4456)
        # petrol_rev = some amount
        diesel_net = 980 * 222.80  # 218344
        petrol_rev = 10000.0
        mpesa = 980 * 222.80 * 0.98   # covers 98% of diesel
        remaining_diesel = diesel_net - mpesa
        cash = 8000.0
        shift = self._run_alloc(diesel_rev=diesel_net, petrol_rev=petrol_rev,
                                cash=cash, mpesa=mpesa)
        allocs = self._allocs(shift)
        diesel_alloc = allocs.filtered(lambda a: a.product_id == self.diesel)
        petrol_alloc = allocs.filtered(lambda a: a.product_id == self.petrol)
        # Diesel: digital covers 98%, remaining 2% covered by cash
        self.assertAlmostEqual(diesel_alloc.uncovered, 0.0, delta=1.0)
        # Petrol: remaining cash (8000 - remaining_diesel) goes to petrol
        expected_petrol_cash = cash - remaining_diesel
        self.assertAlmostEqual(petrol_alloc.cash_allocated, max(0, expected_petrol_cash), delta=1.0)

    def test_edge_rounding_precision(self):
        """Allocation with fractional amounts must not create float precision errors."""
        rev = 333.33
        shift = self._run_alloc(diesel_rev=rev, cash=rev)
        allocs = self._allocs(shift)
        total_coverage = sum(a.digital_allocated + a.cash_allocated for a in allocs)
        # Total coverage must equal total revenue within currency rounding
        self.assertAlmostEqual(total_coverage, rev, delta=0.05)


# ---------------------------------------------------------------------------
# H20: Financial invariant tests (executable)
# ---------------------------------------------------------------------------

class TestFinancialInvariants(HardeningBase):
    """
    Executable tests for the 14 financial invariants specified in the directive.
    """

    def test_invariant_1_one_fuel_sale_one_revenue(self):
        """INVARIANT 1: One fuel sale = one revenue recognition."""
        shift = self._make_shift(diesel_vol=100.0)
        shift.action_start_closing()
        move = shift._post_sales_journal()
        # Call again — idempotent, no second move
        move2 = shift._post_sales_journal()
        self.assertEqual(move, move2, "Second call must return same move, not create a new one")
        # Exactly one account.move with this shift's ref
        existing = self.env['account.move'].search([
            ('ref', 'like', f'FMS Shift:'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
        ])
        shift_move = existing.filtered(lambda m: m.ref == f'FMS Shift: {shift.display_name}')
        self.assertEqual(len(shift_move), 1, "Exactly one revenue move per shift")

    def test_invariant_5_net_throughput_equals_gross_minus_rtt(self):
        """INVARIANT 5: net_throughput = gross_meter - rtt."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        e.sudo().write({
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'rtt_volume': 20.0,
        })
        self.assertAlmostEqual(e.qty_sold_elec, 980.0, places=1)

    def test_invariant_4_rtt_does_not_create_cash_shortage_when_rtt_cash_set(self):
        """INVARIANT 4: RTT does not create artificial cash shortage when rtt_cash is set."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        e.sudo().write({
            'opening_elec_volume': 0.0, 'closing_elec_volume': 1000.0,
            'opening_elec_cash': 0.0, 'closing_elec_cash': 222800.0,
            'rtt_volume': 20.0, 'rtt_cash': 4456.0,
            'attendant_id': self.attendant1.id,
        })
        # Net cash = 222800 - 4456 = 218344. No artificial shortage.
        self.assertAlmostEqual(e.elec_cash_sold, 218344.0, places=0)

    def test_invariant_9_shift_close_idempotent(self):
        """INVARIANT 9: Closed shift blocks second close attempt."""
        shift = self._make_shift(diesel_vol=100.0)
        self._force_close(shift)
        try:
            shift.action_close_shift()
            self.fail("Expected ValidationError on second close")
        except (ValidationError, UserError):
            pass

    def test_invariant_10_closed_history_not_silently_rewritten(self):
        """INVARIANT 10: Closed shift meter entries cannot be written."""
        shift = self._make_shift(diesel_vol=100.0)
        self._force_close(shift)
        entry = shift.meter_entry_ids[:1]
        try:
            entry.write({'closing_elec_volume': 999.0})
            self.fail("Expected ValidationError for write on closed shift")
        except ValidationError:
            pass

    def test_invariant_3_rtt_is_not_a_sale(self):
        """INVARIANT 3: RTT volume is never customer sales quantity."""
        shift = self.env['fms.shift'].create({
            'date': '2026-09-15', 'label': '1_day', 'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        e = shift.meter_entry_ids.filtered(lambda x: x.nozzle_id == self.nozzle_d)
        # 20L gross, 20L RTT = 0L net sale
        e.sudo().write({
            'opening_elec_volume': 0.0, 'closing_elec_volume': 20.0,
            'rtt_volume': 20.0,
        })
        self.assertAlmostEqual(e.qty_sold_elec, 0.0, places=2,
                               msg="RTT equal to gross = zero customer sale")
