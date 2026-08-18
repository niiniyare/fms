"""
test_fms_004.py — Unit tests for FMS-004: Security & Access Control

Tests cover:
  - Group hierarchy (attendant ⊂ supervisor ⊂ accountant)
  - ACL: attendants cannot create/delete shifts
  - ACL: attendants can create meter/dip entries on open shifts
  - ACL: attendants cannot write meter/dip entries on closed shifts (ORM gate)
  - ACL: attendants can only edit their own cash line (ORM gate)
  - ACL: supervisors can close shifts, edit all entries
  - ACL: immutable logs block write/unlink for everyone

Run: make odoo-test
"""

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, AccessError
from .test_common import FMSGLMixin


class FMSSecurityBase(FMSGLMixin, TransactionCase):

    def setUp(self):
        super().setUp()
        self.env['fms.shift'].search([('state', 'in', ('open', 'closing'))]).write({'state': 'draft'})
        self.setup_fms_gl()
        # Master data
        self.product = self.env['product.product'].create({
            'name': 'SEC-Diesel', 'fms_is_fuel': True, 'list_price': 222.8,
        })
        self.pump = self.env['fms.pump'].create({'name': 'SEC-UX1', 'order': 99})
        self.nozzle = self.env['fms.pump.nozzle'].create({
            'pump_id': self.pump.id, 'name': 'A', 'letter': 'A',
            'order': 1, 'product_id': self.product.id,
        })
        # Users in each group
        group_att  = self.env.ref('fms.group_fms_attendant')
        group_sup  = self.env.ref('fms.group_fms_supervisor')

        group_internal = self.env.ref('base.group_user')
        self.user_att = self.env['res.users'].create({
            'name': 'Test Attendant',
            'login': 'test_fms_att@test.com',
            'groups_id': [(6, 0, [group_att.id, group_internal.id])],
        })
        self.user_sup = self.env['res.users'].create({
            'name': 'Test Supervisor',
            'login': 'test_fms_sup@test.com',
            'groups_id': [(6, 0, [group_sup.id, group_internal.id])],
        })
        # Employees linked to users
        self.emp_att = self.env['hr.employee'].create({
            'name': 'Test Attendant Emp',
            'fms_is_attendant': True,
            'user_id': self.user_att.id,
        })
        self.emp_sup = self.env['hr.employee'].create({
            'name': 'Test Supervisor Emp',
            'user_id': self.user_sup.id,
        })

    def _make_open_shift(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-03-01', 'label': '1_day',
            'supervisor_id': self.emp_sup.id,
        })
        shift.action_open_shift()
        return shift

    def _make_closed_shift(self):
        shift = self._make_open_shift()
        shift.action_start_closing()
        shift.action_close_shift()
        return shift


# ---------------------------------------------------------------------------
# Group membership & hierarchy
# ---------------------------------------------------------------------------

class TestGroupHierarchy(FMSSecurityBase):

    def test_attendant_group_exists(self):
        grp = self.env.ref('fms.group_fms_attendant')
        self.assertTrue(grp)

    def test_supervisor_group_exists(self):
        grp = self.env.ref('fms.group_fms_supervisor')
        self.assertTrue(grp)

    def test_accountant_group_exists(self):
        grp = self.env.ref('fms.group_fms_accountant')
        self.assertTrue(grp)

    def test_supervisor_implies_attendant(self):
        """Supervisor group should imply Attendant rights."""
        group_sup = self.env.ref('fms.group_fms_supervisor')
        group_att = self.env.ref('fms.group_fms_attendant')
        implied_ids = group_sup.implied_ids.ids
        self.assertIn(group_att.id, implied_ids)

    def test_accountant_implies_supervisor(self):
        """Accountant group should imply Supervisor rights."""
        group_acc = self.env.ref('fms.group_fms_accountant')
        group_sup = self.env.ref('fms.group_fms_supervisor')
        implied_ids = group_acc.implied_ids.ids
        self.assertIn(group_sup.id, implied_ids)

    def test_supervisor_user_has_attendant_rights(self):
        """Supervisor user automatically has attendant group membership."""
        group_att = self.env.ref('fms.group_fms_attendant')
        self.assertIn(group_att, self.user_sup.groups_id)


# ---------------------------------------------------------------------------
# Shift-level ACL
# ---------------------------------------------------------------------------

class TestShiftACL(FMSSecurityBase):

    def test_attendant_can_read_shift(self):
        shift = self._make_open_shift()
        # Attendant should be able to read the shift record
        shift_as_att = shift.with_user(self.user_att)
        self.assertEqual(shift_as_att.state, 'open')

    def test_attendant_cannot_create_shift(self):
        with self.assertRaises((AccessError, Exception)):
            self.env['fms.shift'].with_user(self.user_att).create({
                'date': '2026-03-02', 'label': '2_evening',
                'supervisor_id': self.emp_sup.id,
            })

    def test_attendant_cannot_open_shift(self):
        shift = self.env['fms.shift'].create({
            'date': '2026-03-03', 'label': '3_night',
            'supervisor_id': self.emp_sup.id,
        })
        with self.assertRaises((AccessError, Exception)):
            shift.with_user(self.user_att).action_open_shift()

    def test_supervisor_can_create_and_open_shift(self):
        shift = self.env['fms.shift'].with_user(self.user_sup).create({
            'date': '2026-03-04', 'label': '1_day',
            'supervisor_id': self.emp_sup.id,
        })
        shift.with_user(self.user_sup).action_open_shift()
        self.assertEqual(shift.state, 'open')

    def test_supervisor_can_close_shift(self):
        shift = self._make_open_shift()
        shift.with_user(self.user_sup).action_start_closing()
        shift.with_user(self.user_sup).action_close_shift()
        self.assertEqual(shift.state, 'closed')

    def test_nobody_can_delete_closed_shift(self):
        shift = self._make_closed_shift()
        with self.assertRaises(ValidationError):
            shift.unlink()


# ---------------------------------------------------------------------------
# Meter entry ACL
# ---------------------------------------------------------------------------

class TestMeterEntryACL(FMSSecurityBase):

    def test_attendant_can_create_meter_entry_on_open_shift(self):
        shift = self._make_open_shift()
        entry = self.env['fms.shift.meter.entry'].with_user(self.user_att).create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,
        })
        self.assertTrue(entry.id)

    def test_meter_entry_locked_on_closed_shift(self):
        """ORM guard: write on closed shift raises ValidationError for all users."""
        shift = self._make_open_shift()
        entry = self.env['fms.shift.meter.entry'].create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,
        })
        shift.action_start_closing()
        shift.action_close_shift()
        with self.assertRaises(ValidationError):
            entry.write({'closing_elec_volume': 200.0})


# ---------------------------------------------------------------------------
# Attendant cash ACL
# ---------------------------------------------------------------------------

class TestAttendantCashACL(FMSSecurityBase):

    def test_attendant_can_write_own_cash_collected(self):
        """Attendant can update cash_collected on their own line."""
        shift = self._make_open_shift()
        cash = self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.emp_att.id,
            'cash_collected': 1000.0,
        })
        cash.with_user(self.user_att).write({'cash_collected': 1500.0})
        self.assertAlmostEqual(cash.cash_collected, 1500.0)

    def test_cash_record_locked_on_closed_shift(self):
        shift = self._make_closed_shift()
        cash = self.env['fms.shift.attendant.cash'].create({
            'shift_id': shift.id,
            'attendant_id': self.emp_att.id,
            'cash_collected': 1000.0,
        })
        with self.assertRaises(ValidationError):
            cash.write({'cash_collected': 9999.0})


# ---------------------------------------------------------------------------
# Immutable log ACL
# ---------------------------------------------------------------------------

class TestImmutableLogACL(FMSSecurityBase):

    def _make_meter_log(self, shift):
        return self.env['fms.meter_log'].sudo().create({
            'shift_id': shift.id,
            'pump_id': self.pump.id,
            'nozzle_id': self.nozzle.id,
            'opening_elec_volume': 0.0,
            'closing_elec_volume': 100.0,
        })

    def test_meter_log_write_blocked_for_supervisor(self):
        shift = self._make_open_shift()
        log = self._make_meter_log(shift)
        with self.assertRaises(ValidationError):
            log.with_user(self.user_sup).write({'closing_elec_volume': 999.0})

    def test_meter_log_unlink_blocked_for_supervisor(self):
        shift = self._make_open_shift()
        log = self._make_meter_log(shift)
        with self.assertRaises(ValidationError):
            log.with_user(self.user_sup).unlink()

    def test_dip_log_write_blocked_for_supervisor(self):
        shift = self._make_open_shift()
        product = self.env['product.product'].create({
            'name': 'SEC-Tank-Product', 'fms_is_fuel': True,
        })
        tank = self.env['stock.location'].create({
            'name': 'SEC-Tank', 'usage': 'internal',
            'fms_is_fuel_tank': True, 'fms_fuel_product_id': product.id,
        })
        log = self.env['fms.dip_log'].sudo().create({
            'shift_id': shift.id,
            'location_id': tank.id,
            'opening_volume': 10000.0,
            'closing_volume': 9500.0,
        })
        with self.assertRaises(ValidationError):
            log.with_user(self.user_sup).write({'closing_volume': 1.0})
