"""
test_fms_007.py — Unit tests for FMS-007: UI/UX Forms & Reports

Tests cover:
  - PDF report action is registered and bound to fms.shift
  - Report template renders without error for draft/open/closed shifts
  - sales_journal_entry_id field accessible on shift model
  - Report generates valid HTML (no render exception)

Run: make odoo-test
"""

from odoo.tests import TransactionCase


class TestFMSReport(TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write({'state': 'draft'})
        self.supervisor = self.env['hr.employee'].create({'name': 'RPT-Supervisor'})
        self.product = self.env['product.product'].create({
            'name': 'RPT-Diesel', 'fms_is_fuel': True, 'list_price': 200.0,
        })
        self.pump = self.env['fms.pump'].create({'name': 'RPT-Pump1', 'order': 30})
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id,
            'name': 'A', 'letter': 'A', 'order': 1,
            'product_id': self.product.id,
        })
        self.tank = self.env['stock.location'].create({
            'name': 'RPT-Tank-1',
            'usage': 'internal',
            'fms_is_fuel_tank': True,
            'fms_fuel_product_id': self.product.id,
        })
        self.attendant = self.env['hr.employee'].create({
            'name': 'RPT-Attendant', 'fms_is_attendant': True,
        })

    def _make_draft_shift(self):
        return self.env['fms.shift'].create({
            'date': '2026-07-01',
            'label': '1_day',
            'supervisor_id': self.supervisor.id,
        })

    def _make_closing_shift(self):
        shift = self._make_draft_shift()
        shift.action_open_shift()
        # Set dip within meniscus to allow close
        dip = shift.dip_entry_ids[:1]
        if dip:
            dip.write({'opening_volume': 9995.0, 'closing_volume': 10000.0})
        shift.action_start_closing()
        return shift

    # ------------------------------------------------------------------
    # Report action registration
    # ------------------------------------------------------------------

    def test_report_action_exists(self):
        """Report action must be registered in ir.actions.report."""
        action = self.env.ref('fms.action_report_fms_shift', raise_if_not_found=False)
        self.assertTrue(action, "Report action 'fms.action_report_fms_shift' not found")

    def test_report_action_bound_to_fms_shift(self):
        action = self.env.ref('fms.action_report_fms_shift')
        self.assertEqual(action.model, 'fms.shift')

    def test_report_action_is_pdf(self):
        action = self.env.ref('fms.action_report_fms_shift')
        self.assertEqual(action.report_type, 'qweb-pdf')

    # ------------------------------------------------------------------
    # Template rendering (HTML, not PDF — avoids wkhtmltopdf dependency)
    # ------------------------------------------------------------------

    def test_report_renders_for_draft_shift(self):
        """QWeb template should render without exception on a draft shift."""
        shift = self._make_draft_shift()
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Shift Reconciliation Report', html)

    def test_report_renders_for_closing_shift(self):
        """QWeb template renders for a shift in closing state."""
        shift = self._make_closing_shift()
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Shift Reconciliation Report', html)
        self.assertIn(b'CLOSING', html)

    def test_report_shows_meter_readings(self):
        """Report includes pump meter data."""
        shift = self._make_closing_shift()
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Pump Meter Readings', html)

    def test_report_shows_tank_dips(self):
        """Report includes tank dip data."""
        shift = self._make_closing_shift()
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Tank Dip Readings', html)

    def test_report_shows_gate_summary(self):
        """Report includes hard gate summary section."""
        shift = self._make_closing_shift()
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Hard Gate Summary', html)

    def test_report_shows_attendant_cash_when_present(self):
        """Attendant cash section appears when cash records exist."""
        shift = self._make_closing_shift()
        self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.attendant.id,
            'cash_collected': 0.0,
        })
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', shift.ids
        )
        self.assertIn(b'Attendant Cash Reconciliation', html)
        self.assertIn(b'RPT-Attendant', html)

    def test_report_multi_shift(self):
        """Report renders for multiple shifts at once."""
        shift1 = self._make_draft_shift()
        shift2 = self.env['fms.shift'].create({
            'date': '2026-07-02',
            'label': '2_evening',
            'supervisor_id': self.supervisor.id,
        })
        html, _ = self.env['ir.actions.report'].sudo()._render_qweb_html(
            'fms.report_fms_shift_reconciliation', (shift1 | shift2).ids
        )
        self.assertIn(b'Shift Reconciliation Report', html)

    # ------------------------------------------------------------------
    # Model field
    # ------------------------------------------------------------------

    def test_sales_journal_entry_id_field_exists(self):
        """sales_journal_entry_id must be a field on fms.shift."""
        shift = self._make_draft_shift()
        self.assertIn('sales_journal_entry_id', shift._fields)

    def test_sales_journal_entry_id_empty_on_draft(self):
        shift = self._make_draft_shift()
        self.assertFalse(shift.sales_journal_entry_id)
