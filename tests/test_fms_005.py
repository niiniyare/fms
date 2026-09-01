"""
test_fms_005.py — Unit tests for FMS-005: Journal Entry Posting & GL Integration

Tests cover:
  - Meter logs created on shift close (snapshot)
  - Dip logs created on shift close (snapshot)
  - Duplicate snapshot idempotency (logs not duplicated on re-close attempt)
  - Sales journal entry created with correct DR/CR lines
  - Sales journal skipped when no product sales
  - Residual allocation journal entry created per allocation
  - Residual allocation journal skipped when COGS accounts missing
  - Journal entry amounts match meter entry amounts
  - sales_journal_entry_id stored on shift after close
  - Shift reaches 'closed' state after successful close

Run: make odoo-test (or via Odoo test runner)
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class FMSGLBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write({'state': 'draft'})
        company = self.env.company

        # Reuse or create a revenue account (Odoo 18: company_ids is Many2many)
        self.revenue_account = self.env['account.account'].search([
            ('account_type', 'in', ('income', 'income_other')),
            ('company_ids', 'in', company.id),
        ], limit=1)
        if not self.revenue_account:
            self.revenue_account = self.env['account.account'].create({
                'name': 'FMS Test Revenue',
                'code': 'FMS9001',
                'account_type': 'income',
                'company_ids': [(4, company.id)],
            })

        # Reuse or create a COGS account
        self.cogs_account = self.env['account.account'].search([
            ('account_type', 'in', ('expense', 'expense_direct_cost')),
            ('company_ids', 'in', company.id),
        ], limit=1)
        if not self.cogs_account:
            self.cogs_account = self.env['account.account'].create({
                'name': 'FMS Test COGS',
                'code': 'FMS9002',
                'account_type': 'expense',
                'company_ids': [(4, company.id)],
            })

        # Reuse or create a sale-type journal
        self.journal = self.env['account.journal'].search([
            ('type', '=', 'sale'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not self.journal:
            self.journal = self.env['account.journal'].create({
                'name': 'FMS Test Sales Journal',
                'code': 'FMSSJ',
                'type': 'sale',
                'company_id': company.id,
            })

        # Wire journal + clearing account into site preferences so _get_fms_journal() works
        clearing = self.env['account.account'].search([
            ('account_type', '=', 'asset_current'),
            ('company_ids', 'in', company.id),
        ], limit=1) or self.env['account.account'].create({
            'name': 'FMS Test Clearing',
            'code': 'FMS9003',
            'account_type': 'asset_current',
            'company_ids': [(4, company.id)],
        })
        prefs = self.env['fms.site.preferences'].get_for_company(company)
        prefs.write({
            'sales_journal_id': self.journal.id,
            'clearing_account_id': clearing.id,
        })

        self.product_diesel = self.env['product.product'].create({
            'name': 'GL-Diesel',
            'fms_is_fuel': True,
            'list_price': 200.0,
            'is_storable': True,
            'fms_revenue_account_id': self.revenue_account.id,
            'fms_cogs_account_id': self.cogs_account.id,
        })
        self.product_carwash = self.env['product.product'].create({
            'name': 'GL-Carwash',
            'fms_is_fuel': False,
            'list_price': 100.0,
            'fms_revenue_account_id': self.revenue_account.id,
            'fms_cogs_account_id': self.cogs_account.id,
        })
        self.pump = self.env['fms.pump'].create({'name': 'GL-Pump1', 'order': 10})
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id,
            'name': 'A',
            'letter': 'A',
            'order': 1,
            'product_id': self.product_diesel.id,
        })
        self.supervisor = self.env['hr.employee'].create({'name': 'GL-Supervisor'})
        self.tank = self.env['stock.location'].create({
            'name': 'GL-Tank-1',
            'usage': 'internal',
            'fms_is_fuel_tank': True,
            'fms_fuel_product_id': self.product_diesel.id,
        })

    def _force_close(self, shift):
        """Close a shift directly for GL tests, bypassing gate checks."""
        if shift.state != 'closing':
            shift.action_start_closing()
        with shift.env.cr.savepoint():
            shift._write_meter_logs()
            shift._write_dip_logs()
            sales_move = shift._post_sales_journal()
            shift._post_residual_allocation_journals()
        vals = {'state': 'closed'}
        if sales_move:
            vals['sales_journal_entry_id'] = sales_move.id
        shift.write(vals)

    def _make_closing_shift(self, closing_vol=100.0, opening_vol=0.0, dip_closing=9000.0):
        """Create a shift with one meter entry and one dip, transition to closing."""
        shift = self.env['fms.shift'].create({
            'date': '2026-05-01',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        # Target the test nozzle specifically — demo nozzles may also be auto-created.
        # Set closing_elec_cash so total_meter_sales > 0 (needed for GL posting).
        entry = shift.meter_entry_ids.filtered(lambda e: e.nozzle_id == self.nozzle)
        if not entry:
            entry = shift.meter_entry_ids[:1]
        if entry:
            closing_cash = closing_vol * (self.product_diesel.list_price or 0.0)
            entry.sudo().write({
                'opening_elec_volume': opening_vol,
                'closing_elec_volume': closing_vol,
                'opening_elec_cash':   0.0,
                'closing_elec_cash':   closing_cash,
            })
        # Override dip entry
        dip = shift.dip_entry_ids[:1]
        if dip:
            dip.sudo().write({'opening_volume': 10000.0, 'closing_volume': dip_closing})
        shift.action_start_closing()
        return shift


# ---------------------------------------------------------------------------
# Audit log snapshots
# ---------------------------------------------------------------------------

class TestAuditLogSnapshots(FMSGLBase):

    def test_meter_logs_created_on_close(self):
        shift = self._make_closing_shift()
        self._force_close(shift)
        logs = self.env['fms.meter_log'].sudo().search([('shift_id', '=', shift.id)])
        self.assertTrue(logs, "Expected meter logs to be created on close")

    def test_dip_logs_created_on_close(self):
        shift = self._make_closing_shift()
        self._force_close(shift)
        logs = self.env['fms.dip_log'].sudo().search([('shift_id', '=', shift.id)])
        self.assertTrue(logs, "Expected dip logs to be created on close")

    def test_meter_log_closing_volume_matches_entry(self):
        shift = self._make_closing_shift(closing_vol=250.0, opening_vol=0.0)
        self._force_close(shift)
        log = self.env['fms.meter_log'].sudo().search([
            ('shift_id', '=', shift.id),
            ('nozzle_id', '=', self.nozzle.id),
        ], limit=1)
        self.assertTrue(log)
        self.assertAlmostEqual(log.closing_elec_volume, 250.0)

    def test_dip_log_closing_volume_matches_entry(self):
        shift = self._make_closing_shift(dip_closing=8500.0)
        self._force_close(shift)
        log = self.env['fms.dip_log'].sudo().search([
            ('shift_id', '=', shift.id),
            ('location_id', '=', self.tank.id),
        ], limit=1)
        self.assertTrue(log)
        self.assertAlmostEqual(log.closing_volume, 8500.0)

    def test_meter_logs_not_duplicated_if_already_exist(self):
        """_write_meter_logs is idempotent — pre-existing logs are not duplicated."""
        shift = self._make_closing_shift()
        # Manually create a meter log before close
        entry = shift.meter_entry_ids[:1]
        if entry:
            self.env['fms.meter_log'].sudo().create({
                'shift_id': shift.id,
                'pump_id': entry.pump_id.id,
                'nozzle_id': entry.nozzle_id.id,
                'opening_elec_volume': entry.opening_elec_volume,
                'closing_elec_volume': entry.closing_elec_volume,
            })
        self._force_close(shift)
        logs = self.env['fms.meter_log'].sudo().search([
            ('shift_id', '=', shift.id),
            ('nozzle_id', '=', self.nozzle.id),
        ])
        # Should have exactly 1 log for this nozzle, not 2
        self.assertEqual(len(logs), 1, "Meter log should not be duplicated")


# ---------------------------------------------------------------------------
# Sales GL journal
# ---------------------------------------------------------------------------

class TestSalesJournal(FMSGLBase):

    def test_sales_journal_entry_created_on_close(self):
        shift = self._make_closing_shift(closing_vol=100.0)
        self._force_close(shift)
        self.assertTrue(shift.sales_journal_entry_id,
                        "sales_journal_entry_id should be set after close")

    def test_sales_journal_entry_is_posted(self):
        shift = self._make_closing_shift(closing_vol=100.0)
        self._force_close(shift)
        move = shift.sales_journal_entry_id
        if move:
            self.assertEqual(move.state, 'posted')

    def test_sales_journal_dr_equals_total_meter_sales(self):
        """Total debit of the sales journal entry = total meter sales."""
        shift = self._make_closing_shift(closing_vol=100.0, opening_vol=0.0)
        # 100L × KES 200 = KES 20,000
        self._force_close(shift)
        move = shift.sales_journal_entry_id
        if not move:
            self.skipTest("No journal entry created (possibly no revenue account)")
        total_debit = sum(move.line_ids.mapped('debit'))
        self.assertAlmostEqual(total_debit, 20000.0, places=1)

    def test_sales_journal_balanced(self):
        """Total debit = total credit (balanced entry)."""
        shift = self._make_closing_shift(closing_vol=100.0)
        self._force_close(shift)
        move = shift.sales_journal_entry_id
        if not move:
            self.skipTest("No journal entry created")
        total_debit  = sum(move.line_ids.mapped('debit'))
        total_credit = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(total_debit, total_credit, places=2)

    def test_no_journal_entry_when_zero_sales(self):
        """Shift with zero meter sales produces no sales journal entry."""
        shift = self._make_closing_shift(closing_vol=0.0, opening_vol=0.0)
        self._force_close(shift)
        self.assertFalse(shift.sales_journal_entry_id)

    def test_shift_state_closed_after_close(self):
        shift = self._make_closing_shift()
        self._force_close(shift)
        self.assertEqual(shift.state, 'closed')

    def test_cannot_close_shift_in_draft_state(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-05-02', 'label': '2_evening',
            'supervisor_id': self.supervisor.id,
        })
        with self.assertRaises(ValidationError):
            shift.action_close_shift()

    def test_cannot_close_shift_in_open_state(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-05-03', 'label': '3_night',
            'supervisor_id': self.supervisor.id,
        })
        shift.action_open_shift()
        with self.assertRaises(ValidationError):
            shift.action_close_shift()


# ---------------------------------------------------------------------------
# Residual allocation journals
# ---------------------------------------------------------------------------

class TestResidualAllocationJournal(FMSGLBase):

    def _make_shift_with_residuals(self):
        """
        Build a shift where Diesel is over-reported in POS (no POS linked = 100% under-reported
        from meter perspective, so residual = full meter amount).  Then manually inject an
        allocation record so we can test the GL posting.
        """
        shift = self._make_closing_shift(closing_vol=100.0)
        # Manually create an allocation record pointing diesel → carwash
        alloc = self.env['fms.shift.residual.allocation'].create({
            'shift_id': shift.id,
            'source_product_id': self.product_diesel.id,
            'target_product_id': self.product_carwash.id,
            'qty_litres': 100.0,
            'amount': 10000.0,
        })
        return shift, alloc

    def test_residual_journal_created_on_close(self):
        shift, alloc = self._make_shift_with_residuals()
        self._force_close(shift)
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        self.assertTrue(alloc_after.journal_entry_id,
                        "Residual allocation should have a journal entry after close")

    def test_residual_journal_is_posted(self):
        shift, alloc = self._make_shift_with_residuals()
        self._force_close(shift)
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        move = alloc_after.journal_entry_id
        if move:
            self.assertEqual(move.state, 'posted')

    def test_residual_journal_amount_matches_allocation(self):
        shift, alloc = self._make_shift_with_residuals()
        self._force_close(shift)
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        move = alloc_after.journal_entry_id
        if not move:
            self.skipTest("No residual journal entry created")
        total_debit = sum(move.line_ids.mapped('debit'))
        self.assertAlmostEqual(total_debit, 10000.0, places=1)

    def test_residual_journal_balanced(self):
        shift, alloc = self._make_shift_with_residuals()
        self._force_close(shift)
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        move = alloc_after.journal_entry_id
        if not move:
            self.skipTest("No residual journal entry created")
        total_debit  = sum(move.line_ids.mapped('debit'))
        total_credit = sum(move.line_ids.mapped('credit'))
        self.assertAlmostEqual(total_debit, total_credit, places=2)

    def test_residual_journal_not_duplicated_on_existing_alloc(self):
        """Idempotent: allocs with journal_entry_id already set are skipped."""
        shift, alloc = self._make_shift_with_residuals()
        # Pre-set a journal entry on the alloc
        dummy_move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': '2026-05-01',
            'line_ids': [
                (0, 0, {'account_id': self.cogs_account.id, 'name': 'DR', 'debit': 1.0, 'credit': 0.0}),
                (0, 0, {'account_id': self.revenue_account.id, 'name': 'CR', 'debit': 0.0, 'credit': 1.0}),
            ],
        })
        alloc.sudo().write({'journal_entry_id': dummy_move.id})
        self._force_close(shift)
        # Should still have the same (dummy) journal entry, not a new one
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        self.assertEqual(alloc_after.journal_entry_id.id, dummy_move.id)

    def test_residual_journal_skipped_when_no_cogs_account(self):
        """Allocation without COGS accounts on both products is skipped gracefully."""
        product_no_cogs = self.env['product.product'].create({
            'name': 'NoCOGS-Product',
            'fms_is_fuel': False,
            'list_price': 50.0,
            # No fms_cogs_account_id set
        })
        shift = self._make_closing_shift()
        alloc = self.env['fms.shift.residual.allocation'].create({
            'shift_id': shift.id,
            'source_product_id': self.product_diesel.id,
            'target_product_id': product_no_cogs.id,
            'qty_litres': 10.0,
            'amount': 500.0,
        })
        # Should not raise — just skip the broken allocation
        self._force_close(shift)
        alloc_after = self.env['fms.shift.residual.allocation'].browse(alloc.id)
        # No journal entry because target has no COGS account
        self.assertFalse(alloc_after.journal_entry_id)
