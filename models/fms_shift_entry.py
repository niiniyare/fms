"""
fms_shift_entry.py — Editable child entry models for a shift

These are the working records attendants fill in during a shift.
On shift close they are snapshotted into immutable fms.meter_log / fms.dip_log.

Models:
  - fms.shift.meter.entry  — one pump nozzle's opening/closing meter reading
  - fms.shift.dip.entry    — one tank's opening/closing dip volume
  - fms.shift.attendant.cash — per-attendant cash + payment-mode breakdown

Reference: FMS_Complete_Specification_Technical_Guide.md, Section 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class FMSShiftMeterEntry(models.Model):
    """
    Editable meter reading for one nozzle during a shift.

    Locked (no write/unlink) once the parent shift reaches 'closed'.
    On close, a corresponding fms.meter_log record is written.
    """

    _name = 'fms.shift.meter.entry'
    _description = 'Shift Meter Entry'
    _order = 'pump_id, nozzle_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')

    pump_id = fields.Many2one('fms.pump', 'Pump', required=True)
    nozzle_id = fields.Many2one(
        'fms.pump.nozzle', 'Nozzle', required=True,
        domain="[('pump_id', '=', pump_id)]",
    )
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='nozzle_id.product_id', store=True, readonly=True,
    )
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant',
        domain=[('fms_is_attendant', '=', True)],
        help="Attendant responsible for money collected on this nozzle this shift.",
    )

    # ── Meter 1: Electronic Volume (litres) ──────────────────────────────────
    opening_elec_volume = fields.Float('Opening Elec Vol (L)', digits=(16, 2))
    closing_elec_volume = fields.Float('Closing Elec Vol (L)', digits=(16, 2))

    # ── Meter 2: Electronic Cash (KES totalizer) ─────────────────────────────
    opening_elec_cash = fields.Float(
        'Opening Elec Cash (KES)', digits=(16, 2),
        help="Electronic cash totalizer reading at shift start (KES).",
    )
    closing_elec_cash = fields.Float(
        'Closing Elec Cash (KES)', digits=(16, 2),
        help="Electronic cash totalizer reading at shift end (KES).",
    )
    elec_cash_sold = fields.Float(
        'Cash Sold (KES)', compute='_compute_qty', store=True, digits=(16, 2),
        help="Closing − Opening elec cash. This is the amount the attendant must account for.",
    )

    # ── Meter 3: Manual Mechanical (litres) ──────────────────────────────────
    opening_man_mech = fields.Float('Opening Manual (L)', digits=(16, 2))
    closing_man_mech = fields.Float('Closing Manual (L)', digits=(16, 2))

    # ── Computed quantities ───────────────────────────────────────────────────
    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    amount_elec = fields.Float(
        'Volume × Price (KES)', compute='_compute_amount', store=True, digits=(16, 2),
        help="Theoretical value: qty_sold_elec × product list price.",
    )

    notes = fields.Char('Notes')

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------

    @api.depends(
        'closing_elec_volume', 'opening_elec_volume',
        'closing_elec_cash', 'opening_elec_cash',
        'closing_man_mech', 'opening_man_mech',
    )
    def _compute_qty(self):
        for e in self:
            e.qty_sold_elec  = e.closing_elec_volume - (e.opening_elec_volume or 0.0)
            e.elec_cash_sold = e.closing_elec_cash   - (e.opening_elec_cash   or 0.0)
            e.qty_sold_man   = e.closing_man_mech    - (e.opening_man_mech    or 0.0)

    @api.depends('qty_sold_elec', 'product_id', 'product_id.list_price')
    def _compute_amount(self):
        for e in self:
            e.amount_elec = e.qty_sold_elec * (e.product_id.list_price or 0.0)

    # ------------------------------------------------------------------
    # Auto-fill pump from nozzle
    # ------------------------------------------------------------------

    @api.onchange('nozzle_id')
    def _onchange_nozzle_id(self):
        if self.nozzle_id and self.nozzle_id.pump_id:
            self.pump_id = self.nozzle_id.pump_id

    # ------------------------------------------------------------------
    # Locking: no edits once shift is closed
    # ------------------------------------------------------------------

    def _check_shift_open(self):
        for entry in self:
            if entry.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit meter entries on a closed shift. "
                    "The shift's meter logs are the immutable record."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()

    # ------------------------------------------------------------------
    # Snapshot to immutable log
    # ------------------------------------------------------------------

    def _create_meter_log(self):
        """Copy this entry to fms.meter_log (called by shift on close)."""
        self.ensure_one()
        return self.env['fms.meter_log'].sudo().create({
            'shift_id':            self.shift_id.id,
            'pump_id':             self.pump_id.id,
            'nozzle_id':           self.nozzle_id.id,
            'attendant_id':        self.attendant_id.id or False,
            'opening_elec_volume': self.opening_elec_volume,
            'closing_elec_volume': self.closing_elec_volume,
            'opening_elec_cash':   self.opening_elec_cash,
            'closing_elec_cash':   self.closing_elec_cash,
            'opening_man_mech':    self.opening_man_mech,
            'closing_man_mech':    self.closing_man_mech,
        })


class FMSShiftDipEntry(models.Model):
    """
    Editable tank dip volume for one shift.

    Locked once parent shift is closed.  On close, copied to fms.dip_log.
    """

    _name = 'fms.shift.dip.entry'
    _description = 'Shift Dip Entry'
    _order = 'location_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    location_id = fields.Many2one(
        'stock.location', 'Tank', required=True,
        domain=[('fms_is_fuel_tank', '=', True)],
    )
    product_id = fields.Many2one(
        'product.product', 'Product',
        related='location_id.fms_fuel_product_id', store=True, readonly=True,
    )

    opening_volume = fields.Float('Opening Volume (L)', digits=(16, 2))
    closing_volume = fields.Float('Closing Volume (L)', digits=(16, 2))

    qty_change = fields.Float(
        'Volume Change (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    variance_pct = fields.Float(
        'Variance %', compute='_compute_variance', store=True, digits=(16, 4),
    )

    notes = fields.Char('Notes')

    @api.depends('closing_volume', 'opening_volume')
    def _compute_qty(self):
        for e in self:
            e.qty_change = e.closing_volume - (e.opening_volume or 0.0)

    @api.depends('qty_change', 'closing_volume')
    def _compute_variance(self):
        for e in self:
            if e.closing_volume > 0:
                e.variance_pct = abs(e.qty_change) / e.closing_volume * 100.0
            else:
                e.variance_pct = 0.0

    def _check_shift_open(self):
        for entry in self:
            if entry.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit dip entries on a closed shift."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()

    def _create_dip_log(self):
        """Copy this entry to fms.dip_log (called by shift on close)."""
        self.ensure_one()
        return self.env['fms.dip_log'].sudo().create({
            'shift_id': self.shift_id.id,
            'location_id': self.location_id.id,
            'opening_volume': self.opening_volume,
            'closing_volume': self.closing_volume,
        })


class FMSShiftAttendantCash(models.Model):
    """
    Per-attendant cash reconciliation for one shift.

    ONLY cash_collected (physical cash dropped to safe) is entered manually.
    All other amounts are queried automatically:
      - reported_sales : POS orders where cashier = attendant's linked user
      - mpesa_amount   : POS payments via MPesa-type payment method
      - card_amount    : POS payments via Card-type payment method
      - ar_amount      : POS payments via AR/Account-type payment method
      - expense_amount : Vendor bills (account.move in_invoice) tagged to this shift+attendant

    Balance = (reported_sales) − (cash_collected + mpesa_amount + card_amount + ar_amount + expense_amount)
    Balance must = 0 for the shift to close (hard gate, FMS-006).

    Reference: Spec Section 3.3 Screen 3 / Section 7.2
    """

    _name = 'fms.shift.attendant.cash'
    _description = 'Shift Attendant Cash Reconciliation'
    _order = 'attendant_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade')
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True,
        domain=[('fms_is_attendant', '=', True)],
    )

    # ── ONLY EDITABLE FIELD ───────────────────────────────────────────────────
    cash_collected = fields.Float(
        'Cash Dropped to Safe (KES)', digits=(16, 2),
        help="Physical cash the attendant handed to the supervisor / dropped in the safe. "
             "This is the only field entered manually — all other amounts come from POS and GL.",
    )

    # ── INCOMING (from nozzle elec cash meters) ───────────────────────────────
    reported_sales = fields.Float(
        'Meter Sales (KES)', compute='_compute_from_meters', store=True, digits=(16, 2),
        help="Sum of elec_cash_sold across all meter entries where attendant = this attendant. "
             "This is the cash the pump electronics say this attendant collected.",
    )
    mpesa_amount = fields.Float(
        'MPesa (KES)', compute='_compute_from_pos', digits=(16, 2),
        help="POS payments via MPesa payment method (payment method name contains 'mpesa').",
    )
    card_amount = fields.Float(
        'Card (KES)', compute='_compute_from_pos', digits=(16, 2),
        help="POS payments via Card payment method (payment method name contains 'card').",
    )
    ar_amount = fields.Float(
        'AR / Credit Sales (KES)', compute='_compute_from_pos', digits=(16, 2),
        help="POS payments via Account/AR payment method, i.e. credit sales posted as receivables.",
    )

    # ── OUTGOING (queried from GL) ────────────────────────────────────────────
    expense_amount = fields.Float(
        'Expenses (KES)', compute='_compute_from_invoices', digits=(16, 2),
        help="Vendor bills (account.move with move_type=in_invoice) linked to this shift "
             "where the bill's attendant matches this record.",
    )

    # ── TOTALS ────────────────────────────────────────────────────────────────
    total_in = fields.Float(
        'Total In (KES)', compute='_compute_balance', digits=(16, 2),
        help="POS Sales — all money that should have come to this attendant.",
    )
    total_out = fields.Float(
        'Total Out (KES)', compute='_compute_balance', digits=(16, 2),
        help="Cash + MPesa + Card + AR + Expenses — how the money left the attendant.",
    )
    balance = fields.Float(
        'Balance (KES)', compute='_compute_balance', digits=(16, 2),
        help="Total In minus Total Out. Must be 0 for shift to close (hard gate).",
    )

    notes = fields.Char('Notes')

    # ── Compute: Meter-based reported sales ──────────────────────────────────

    @api.depends(
        'shift_id.meter_entry_ids.attendant_id',
        'shift_id.meter_entry_ids.elec_cash_sold',
        'attendant_id',
    )
    def _compute_from_meters(self):
        for rec in self:
            if not rec.shift_id or not rec.attendant_id:
                rec.reported_sales = 0.0
                continue
            nozzle_entries = rec.shift_id.meter_entry_ids.filtered(
                lambda e: e.attendant_id == rec.attendant_id
            )
            rec.reported_sales = sum(nozzle_entries.mapped('elec_cash_sold'))

    # ── Compute: POS payment breakdown (MPesa / Card / AR) ───────────────────

    @api.depends(
        'shift_id.pos_session_ids',
        'attendant_id',
        'attendant_id.user_id',
    )
    def _compute_from_pos(self):
        PayMethod = self.env['pos.payment.method']
        mpesa_methods = PayMethod.search([('name', 'ilike', 'mpesa')])
        card_methods  = PayMethod.search([('name', 'ilike', 'card')])
        ar_methods    = PayMethod.search([
            ('name', 'ilike', 'account'),
        ]) | PayMethod.search([('name', 'ilike', 'credit')])

        for rec in self:
            sessions = rec.shift_id.pos_session_ids
            user = rec.attendant_id.user_id

            if not sessions or not user:
                rec.reported_sales = 0.0
                rec.mpesa_amount   = 0.0
                rec.card_amount    = 0.0
                rec.ar_amount      = 0.0
                continue

            orders = self.env['pos.order'].search([
                ('session_id', 'in', sessions.ids),
                ('cashier_id', '=', user.id),
            ])
            rec.reported_sales = sum(orders.mapped('amount_total'))

            if orders:
                payments = self.env['pos.payment'].search([
                    ('pos_order_id', 'in', orders.ids),
                ])
                rec.mpesa_amount = sum(
                    p.amount for p in payments if p.payment_method_id in mpesa_methods
                )
                rec.card_amount = sum(
                    p.amount for p in payments if p.payment_method_id in card_methods
                )
                rec.ar_amount = sum(
                    p.amount for p in payments if p.payment_method_id in ar_methods
                )
            else:
                rec.mpesa_amount = 0.0
                rec.card_amount  = 0.0
                rec.ar_amount    = 0.0

    # ── Compute: Expenses from GL ─────────────────────────────────────────────

    @api.depends('shift_id', 'attendant_id')
    def _compute_from_invoices(self):
        for rec in self:
            if not rec.shift_id or not rec.attendant_id:
                rec.expense_amount = 0.0
                continue
            bills = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('invoice_date', '=', rec.shift_id.date),
                ('ref', 'ilike', rec.shift_id._origin.id or rec.shift_id.id),
            ])
            rec.expense_amount = sum(bills.mapped('amount_total'))

    # ── Compute: Balance ─────────────────────────────────────────────────────

    @api.depends(
        'reported_sales', 'cash_collected',
        'mpesa_amount', 'card_amount', 'ar_amount', 'expense_amount',
        'shift_id.meter_entry_ids.elec_cash_sold',
        'shift_id.meter_entry_ids.attendant_id',
    )
    def _compute_balance(self):
        for rec in self:
            rec.total_in  = rec.reported_sales
            rec.total_out = (
                rec.cash_collected
                + rec.mpesa_amount
                + rec.card_amount
                + rec.ar_amount
                + rec.expense_amount
            )
            rec.balance = rec.total_in - rec.total_out

    # ── Locking ───────────────────────────────────────────────────────────────

    def _check_shift_open(self):
        for rec in self:
            if rec.shift_id.state == 'closed':
                raise ValidationError(
                    "Cannot edit attendant cash records on a closed shift."
                )

    def write(self, vals):
        self._check_shift_open()
        return super().write(vals)

    def unlink(self):
        self._check_shift_open()
        return super().unlink()
