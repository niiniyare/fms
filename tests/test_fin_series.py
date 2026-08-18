"""
test_fin_series.py — Tests for FIN-001 through FIN-013 (Native Odoo Accounting Integration)

Covers:
- FIN-002: account.payment extension (fms_shift_id, fms_attendant_id, fms_payment_context)
- FIN-003/004/005: expense, vendor payment, float via payment context
- FIN-006: expanded cash reconciliation formula
- FIN-007: dry-stock aggregation in product sales
- FIN-008: attendant cash breakdown SQL view
- FIN-009: additional shift close gates G9-G14
- FIN-012: company isolation record rules on account.payment

Run: python -m pytest tests/test_fin_series.py -v
"""

from datetime import date
from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError


class TestFINBase(TransactionCase):
    """Shared fixtures for all FIN tests."""

    def setUp(self):
        super().setUp()
        company = self.env.company

        # Fuel product
        self.fuel = self.env['product.product'].create({
            'name': 'Diesel Test',
            'fms_is_fuel': True,
            'list_price': 180.0,
        })

        # Dry-stock product
        self.carwash = self.env['product.product'].create({
            'name': 'Carwash Test',
            'fms_is_fuel': False,
            'list_price': 500.0,
        })

        # Attendant employee
        self.attendant = self.env['hr.employee'].create({
            'name': 'Test Attendant',
            'fms_is_attendant': True,
            'company_id': company.id,
        })

        # Shift (draft state)
        self.shift = self.env['fms.shift'].create({
            'date': date.today(),
            'label': '1_day',
            'company_id': company.id,
        })


class TestFINPaymentExtension(TestFINBase):
    """FIN-002: account.payment FMS context fields."""

    def setUp(self):
        super().setUp()
        if 'fms_shift_id' not in self.env['account.payment']._fields:
            self.skipTest("fms_accounting not installed — payment FMS fields absent")

    def _make_payment(self, context, payment_type='inbound', amount=1000.0, state='draft'):
        pay = self.env['account.payment'].create({
            'payment_type': payment_type,
            'partner_type': 'customer',
            'partner_id': self.env['res.partner'].search([], limit=1).id,
            'amount': amount,
            'fms_shift_id': self.shift.id,
            'fms_attendant_id': self.attendant.id,
            'fms_payment_context': context,
            'journal_id': self.env['account.journal'].search(
                [('type', '=', 'cash'), ('company_id', '=', self.env.company.id)], limit=1
            ).id,
        })
        return pay

    def test_payment_has_fms_shift_field(self):
        self.assertIn('fms_shift_id', self.env['account.payment']._fields)
        self.assertIn('fms_payment_context', self.env['account.payment']._fields)
        self.assertIn('fms_attendant_id', self.env['account.payment']._fields)

    def test_payment_shift_link(self):
        pay = self._make_payment('customer_receipt')
        self.assertEqual(pay.fms_shift_id, self.shift)
        self.assertEqual(pay.fms_payment_context, 'customer_receipt')

    def test_payment_station_derived_from_shift(self):
        pay = self._make_payment('customer_receipt')
        self.assertEqual(pay.fms_station_id, self.shift.company_id)

    def test_payment_company_mismatch_blocked(self):
        """Cannot link payment from company A to shift from company B."""
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        with self.assertRaises(ValidationError):
            self.env['account.payment'].with_company(other_company).create({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': self.env['res.partner'].search([], limit=1).id,
                'amount': 500.0,
                'fms_shift_id': self.shift.id,  # shift belongs to self.env.company
                'fms_payment_context': 'customer_receipt',
                'journal_id': self.env['account.journal'].search(
                    [('type', '=', 'cash'), ('company_id', '=', other_company.id)], limit=1
                ).id or self.env['account.journal'].search(
                    [('type', '=', 'cash')], limit=1
                ).id,
            })

    def test_payment_context_selection_values(self):
        valid = [v for v, _ in self.env['account.payment']._fields['fms_payment_context'].selection]
        self.assertIn('customer_receipt', valid)
        self.assertIn('vendor_payment', valid)
        self.assertIn('cash_float', valid)
        self.assertIn('cash_drop', valid)
        self.assertIn('expense', valid)


class TestFINCashReconciliationFormula(TestFINBase):
    """FIN-006: expanded attendant cash reconciliation formula."""

    def setUp(self):
        super().setUp()
        # Create attendant cash line for the shift
        self.cash_line = self.env['fms.shift.attendant.cash'].create({
            'shift_id': self.shift.id,
            'attendant_id': self.attendant.id,
            'cash_collected': 0.0,
        })

    def test_balance_fields_exist(self):
        for field in ('reported_sales', 'customer_receipt_amount', 'float_amount',
                      'cash_drop_amount', 'vendor_payment_amount', 'expense_amount',
                      'total_in', 'total_out', 'balance'):
            self.assertIn(field, self.env['fms.shift.attendant.cash']._fields,
                          f"Missing field: {field}")

    def test_balance_zero_on_empty_shift(self):
        self.cash_line._compute_from_payments()
        self.cash_line._compute_balance()
        self.assertAlmostEqual(self.cash_line.balance, 0.0, places=2)

    def test_total_in_formula(self):
        """total_in = reported_sales + customer_receipts + float - drops"""
        # Directly set intermediate values to test formula
        self.cash_line.write({'cash_collected': 0.0})
        # Manually set computed intermediates for formula verification
        self.cash_line.reported_sales = 10000.0
        self.cash_line.customer_receipt_amount = 2000.0
        self.cash_line.float_amount = 500.0
        self.cash_line.cash_drop_amount = 1500.0
        self.cash_line.mpesa_amount = 3000.0
        self.cash_line.card_amount = 0.0
        self.cash_line.ar_amount = 0.0
        self.cash_line.vendor_payment_amount = 0.0
        self.cash_line.expense_amount = 0.0
        self.cash_line._compute_balance()
        # total_in = 10000 + 2000 + 500 - 1500 = 11000
        # total_out = 0 + 3000 + 0 + 0 + 0 + 0 = 3000
        # balance = 11000 - 3000 = 8000
        self.assertAlmostEqual(self.cash_line.total_in, 11000.0, places=2)
        self.assertAlmostEqual(self.cash_line.total_out, 3000.0, places=2)
        self.assertAlmostEqual(self.cash_line.balance, 8000.0, places=2)

    def test_balance_stored_in_db(self):
        """balance must be stored=True so SQL view can read it."""
        field = self.env['fms.shift.attendant.cash']._fields['balance']
        self.assertTrue(field.store, "balance must be stored for R27 SQL view")

    def test_mpesa_card_ar_stored(self):
        """mpesa_amount, card_amount, ar_amount must be stored."""
        for fname in ('mpesa_amount', 'card_amount', 'ar_amount'):
            field = self.env['fms.shift.attendant.cash']._fields[fname]
            self.assertTrue(field.store, f"{fname} must be stored for R27 SQL view")


class TestFINDryStockAggregation(TestFINBase):
    """FIN-007: dry-stock aggregation in product sales."""

    def test_is_fuel_field_exists(self):
        self.assertIn('is_fuel', self.env['fms.shift.product.sales']._fields)

    def test_is_fuel_derived_from_product(self):
        ps = self.env['fms.shift.product.sales'].create({
            'shift_id': self.shift.id,
            'product_id': self.fuel.id,
            'meter_volume': 100.0,
            'elec_cash_sold': 18000.0,
        })
        self.assertTrue(ps.is_fuel)

    def test_dry_stock_is_not_fuel(self):
        ps = self.env['fms.shift.product.sales'].create({
            'shift_id': self.shift.id,
            'product_id': self.carwash.id,
            'meter_volume': 0.0,
            'elec_cash_sold': 0.0,
        })
        self.assertFalse(ps.is_fuel)

    def test_shift_product_sales_unique_constraint(self):
        """UNIQUE(shift_id, product_id) prevents duplicate rows."""
        self.env['fms.shift.product.sales'].create({
            'shift_id': self.shift.id,
            'product_id': self.fuel.id,
        })
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            self.env['fms.shift.product.sales'].create({
                'shift_id': self.shift.id,
                'product_id': self.fuel.id,
            })


class TestFINAttendantCashBreakdownView(TestFINBase):
    """FIN-008: attendant cash breakdown SQL view (R27)."""

    def test_model_exists(self):
        self.assertIn('fms.report.attendant.cash.breakdown',
                      self.env.registry.models)

    def test_view_is_readonly(self):
        model = self.env['fms.report.attendant.cash.breakdown']
        self.assertFalse(model._auto, "R27 must be _auto=False SQL view")

    def test_view_fields_exist(self):
        model = self.env['fms.report.attendant.cash.breakdown']
        for field in ('shift_id', 'attendant_id', 'meter_sales', 'customer_receipts',
                      'float_received', 'cash_drops', 'mpesa', 'card', 'ar_credit',
                      'vendor_payments', 'expenses', 'cash_declared', 'expected_cash',
                      'variance', 'is_balanced'):
            self.assertIn(field, model._fields, f"Missing field: {field}")


class TestFINGatesG9G14(TestFINBase):
    """FIN-009: additional shift close gates G9-G14."""

    def test_gate_methods_exist(self):
        shift = self.shift
        for method in ('_gate_check_customer_receipts',
                       '_gate_check_float_reconciliation',
                       '_gate_check_expense_posting',
                       '_gate_check_vendor_payment_posting',
                       '_gate_check_digital_payment_reconciliation',
                       '_gate_check_no_unresolved_exceptions'):
            self.assertTrue(hasattr(shift, method),
                            f"Missing gate method: {method}")

    def test_g9_passes_when_no_receipts(self):
        """G9 trivially passes when no payments linked."""
        # Should not raise
        self.shift._gate_check_customer_receipts()

    def test_g10_passes_when_no_floats(self):
        """G10 trivially passes when no floats issued."""
        self.shift._gate_check_float_reconciliation()

    def test_g11_passes_when_no_expenses(self):
        """G11 trivially passes when no expense payments."""
        self.shift._gate_check_expense_posting()

    def test_g12_passes_when_no_vendor_payments(self):
        """G12 trivially passes when no vendor payments."""
        self.shift._gate_check_vendor_payment_posting()

    def test_g13_passes_when_no_pos_sessions(self):
        """G13 trivially passes when no POS sessions linked."""
        self.shift._gate_check_digital_payment_reconciliation()

    def test_g14_blocks_when_disputed(self):
        """G14 blocks if shift is in disputed state."""
        self.shift.write({'state': 'disputed'})
        with self.assertRaises(ValidationError) as cm:
            self.shift._gate_check_no_unresolved_exceptions()
        self.assertIn('Disputed', str(cm.exception))

    def test_g14_passes_when_not_disputed(self):
        """G14 passes for open/closing shifts."""
        self.shift.write({'state': 'open'})
        self.shift._gate_check_no_unresolved_exceptions()

    def test_g11_blocks_on_draft_expense(self):
        """G11 blocks when draft expense payment exists."""
        journal = self.env['account.journal'].search(
            [('type', '=', 'cash'), ('company_id', '=', self.env.company.id)], limit=1
        )
        if not journal:
            self.skipTest("No cash journal available")
        partner = self.env['res.partner'].search([], limit=1)
        self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': partner.id,
            'amount': 500.0,
            'fms_shift_id': self.shift.id,
            'fms_payment_context': 'expense',
            'journal_id': journal.id,
        })
        with self.assertRaises(ValidationError) as cm:
            self.shift._gate_check_expense_posting()
        self.assertIn('G11', str(cm.exception))


class TestFINCompanyIsolation(TestFINBase):
    """FIN-012: company isolation on account.payment FMS fields."""

    def setUp(self):
        super().setUp()
        if 'fms_station_id' not in self.env['account.payment']._fields:
            self.skipTest("fms_accounting not installed — payment company isolation fields absent")

    def test_record_rule_exists_for_supervisor(self):
        """Rule rule_fms_payment_supervisor must exist."""
        rule = self.env['ir.rule'].search([
            ('name', 'ilike', 'FMS Payment'),
            ('model_id.model', '=', 'account.payment'),
        ])
        self.assertTrue(rule, "No record rules found for account.payment FMS isolation")

    def test_fms_station_id_is_stored(self):
        """fms_station_id must be stored for record rule domain to work."""
        field = self.env['account.payment']._fields.get('fms_station_id')
        self.assertIsNotNone(field, "fms_station_id field missing")
        self.assertTrue(field.store, "fms_station_id must be stored")
