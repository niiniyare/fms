"""
fms_emergency_override_wizard.py — Emergency shift close override

Restricted to fms.group_fms_accountant.
Requires explicit reason text. Creates an immutable audit record.
Closes the shift regardless of gate failures.
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError


class FMSEmergencyOverrideWizard(models.TransientModel):
    _name = 'fms.emergency.override.wizard'
    _description = 'Emergency Shift Close Override'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, readonly=True)
    reason = fields.Text(
        'Override Reason', required=True,
        help="Mandatory explanation of why normal gate closure was bypassed. "
             "This is permanently recorded in the audit trail.",
    )
    approver_id = fields.Many2one(
        'hr.employee', 'Approving Manager', required=True,
        help="The manager who authorised this override. Must be a supervisor or accountant.",
    )

    def action_confirm_override(self):
        self.ensure_one()
        if not self.env.user.has_group('fms.group_fms_accountant'):
            raise AccessError(
                "Emergency override requires the FMS Accountant role. "
                "Contact your system administrator."
            )
        if not self.reason or len(self.reason.strip()) < 10:
            raise ValidationError("Override reason must be at least 10 characters.")
        self.shift_id._apply_emergency_override(
            reason=self.reason,
            approver=self.approver_id,
        )
        return {'type': 'ir.actions.act_window_close'}


class FMSEmergencyOverrideLog(models.Model):
    _name = 'fms.shift.override.log'
    _description = 'Emergency Shift Close Override Audit Log'
    _order = 'create_date desc'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='restrict')
    user_id = fields.Many2one('res.users', 'Override By', required=True, readonly=True)
    approver_id = fields.Many2one('hr.employee', 'Approving Manager', readonly=True)
    reason = fields.Text('Override Reason', required=True, readonly=True)
    gate_failures = fields.Text('Gate Failures at Override Time', readonly=True)
    create_date = fields.Datetime('Timestamp', readonly=True)

    def write(self, vals):
        raise ValidationError("Override logs are immutable and cannot be edited.")

    def unlink(self):
        raise ValidationError("Override logs cannot be deleted.")
