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

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade', index=True)

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
        'Opening Elec Cash', digits=(16, 2),
        help="Electronic cash totalizer reading at shift start (KES).",
    )
    closing_elec_cash = fields.Float(
        'Closing Elec Cash', digits=(16, 2),
        help="Electronic cash totalizer reading at shift end (KES).",
    )

    # ── Meter 3: Manual Mechanical (litres) ──────────────────────────────────
    opening_man_mech = fields.Float('Opening Manual (L)', digits=(16, 2))
    closing_man_mech = fields.Float('Closing Manual (L)', digits=(16, 2))

    # ── RTT (Return to Tank) ─────────────────────────────────────────────────
    rtt_volume = fields.Float(
        'RTT Volume (L)', digits=(16, 2),
        help="Litres returned to tank (test pumping, nozzle priming, calibration). "
             "Deducted from effective qty sold.",
    )

    # ── Computed quantities ───────────────────────────────────────────────────
    qty_sold_elec = fields.Float(
        'Qty Sold Elec (L)', compute='_compute_qty', store=True, digits=(16, 2),
        help="(Closing − Opening) elec volume − RTT volume.",
    )
    qty_sold_man = fields.Float(
        'Qty Sold Manual (L)', compute='_compute_qty', store=True, digits=(16, 2),
    )
    elec_cash_sold = fields.Float(
        'Cash Sold', compute='_compute_qty', store=True, digits=(16, 2),
        help="(Closing − Opening) elec cash − RTT cash. Amount the attendant must account for.",
    )
    amount_elec = fields.Float(
        'Volume × Price', compute='_compute_amount', store=True, digits=(16, 2),
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
        'rtt_volume',
    )
    def _compute_qty(self):
        for e in self:
            e.qty_sold_elec  = (e.closing_elec_volume - (e.opening_elec_volume or 0.0)) - (e.rtt_volume or 0.0)
            e.elec_cash_sold = e.closing_elec_cash   - (e.opening_elec_cash   or 0.0)
            e.qty_sold_man   = e.closing_man_mech    - (e.opening_man_mech    or 0.0)

    @api.depends('qty_sold_elec', 'product_id', 'product_id.list_price', 'shift_id.date')
    def _compute_amount(self):
        for e in self:
            price = e._get_shift_price()
            e.amount_elec = e.qty_sold_elec * price

    def _get_shift_price(self):
        """Return pump price from active price period for shift date, or product list_price."""
        if not self.product_id:
            return 0.0
        shift_date = self.shift_id.date if self.shift_id else None
        if shift_date:
            period = self.env['fms.price.period'].search([
                ('date_start', '<=', shift_date),
                ('date_end',   '>=', shift_date),
                ('active', '=', True),
            ], limit=1)
            if period:
                line = period.price_line_ids.filtered(
                    lambda l: l.product_id == self.product_id
                )
                if line:
                    return line[0].pump_price
        return self.product_id.list_price or 0.0

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

    @api.constrains('elec_cash_sold')
    def _check_elec_cash_non_negative(self):
        for entry in self:
            if entry.elec_cash_sold < 0:
                raise ValidationError(
                    f"Nozzle {entry.nozzle_id.name or entry.id}: "
                    f"Cash meter reading produces a negative cash sale "
                    f"({entry.shift_id.company_id.currency_id.name} {entry.elec_cash_sold:,.2f}). "
                    "Check closing vs opening cash meter readings."
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
            'rtt_volume':          self.rtt_volume,
        })


class FMSShiftDipEntry(models.Model):
    """
    Editable tank dip volume for one shift.

    Locked once parent shift is closed.  On close, copied to fms.dip_log.
    """

    _name = 'fms.shift.dip.entry'
    _description = 'Shift Dip Entry'
    _order = 'location_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade', index=True)
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

    @api.constrains('closing_volume')
    def _check_closing_volume_capacity(self):
        for e in self:
            if not e.location_id:
                continue
            capacity = e.location_id.fms_tank_capacity_l
            if capacity and e.closing_volume > capacity:
                raise ValidationError(
                    f"Tank '{e.location_id.name}': closing dip {e.closing_volume:.0f}L "
                    f"exceeds tank capacity {capacity:.0f}L. "
                    "Check the reading — a physical tank cannot exceed its rated capacity."
                )

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
    All other amounts are derived from source records:
      - reported_sales     : meter elec_cash_sold for this attendant's nozzles
      - mpesa_amount       : POS payments via MPesa payment method
      - card_amount        : POS payments via Card payment method
      - ar_amount          : POS payments via AR/Account payment method (credit sales)
      - customer_receipt_amount : account.payment inbound, fms_payment_context=customer_receipt
      - float_amount       : account.payment fms_payment_context=cash_float (not revenue)
      - cash_drop_amount   : account.payment fms_payment_context=cash_drop (reduces holding)
      - vendor_payment_amount : account.payment outbound, fms_payment_context=vendor_payment
      - expense_amount     : account.payment fms_payment_context=expense

    Formula:
      total_in  = reported_sales + customer_receipt_amount + float_amount - cash_drop_amount
      total_out = cash_collected + mpesa_amount + card_amount + ar_amount
                  + vendor_payment_amount + expense_amount
      balance   = total_in - total_out  → must = 0 to close

    Reference: FIN-006, Runbook 03-daily-shift.md
    """

    _name = 'fms.shift.attendant.cash'
    _description = 'Shift Attendant Cash Reconciliation'
    _order = 'attendant_id'

    shift_id = fields.Many2one('fms.shift', 'Shift', required=True, ondelete='cascade', index=True)
    attendant_id = fields.Many2one(
        'hr.employee', 'Attendant', required=True,
        domain=[('fms_is_attendant', '=', True)],
    )

    # ── ONLY EDITABLE FIELD ───────────────────────────────────────────────────
    cash_collected = fields.Float(
        'Cash Dropped to Safe', digits=(16, 2),
        help="Physical cash the attendant handed to the supervisor / dropped in the safe.",
    )

    # ── INCOMING (from meters) ────────────────────────────────────────────────
    reported_sales = fields.Float(
        'Meter Sales', compute='_compute_from_meters', store=True, digits=(16, 2),
        help="Sum of elec_cash_sold for this attendant's nozzles.",
    )

    # ── PAYMENT METHOD SPLITS (from POS) ─────────────────────────────────────
    mpesa_amount = fields.Float(
        'MPesa', compute='_compute_from_pos', store=True, digits=(16, 2),
        help="POS payments via MPesa payment method.",
    )
    card_amount = fields.Float(
        'Card', compute='_compute_from_pos', store=True, digits=(16, 2),
        help="POS payments via Card payment method.",
    )
    ar_amount = fields.Float(
        'AR / Credit Sales', compute='_compute_from_pos', store=True, digits=(16, 2),
        help="POS payments via Account/AR payment method (credit sales).",
    )

    # ── CASH MOVEMENTS (from account.payment with fms_shift_id) ──────────────
    customer_receipt_amount = fields.Float(
        'Customer Receipts', compute='_compute_from_payments', store=True, digits=(16, 2),
        help="Cash collected from customers paying outstanding invoices. "
             "Source: account.payment with fms_payment_context=customer_receipt, posted.",
    )
    float_amount = fields.Float(
        'Cash Float', compute='_compute_from_payments', store=True, digits=(16, 2),
        help="Opening/additional float issued to this attendant. Not revenue — increases expected holding.",
    )
    cash_drop_amount = fields.Float(
        'Cash Drops', compute='_compute_from_payments', store=True, digits=(16, 2),
        help="Mid-shift cash drops/pickups. Reduces expected holding (cash already in safe).",
    )
    vendor_payment_amount = fields.Float(
        'Vendor Payments', compute='_compute_from_payments', store=True, digits=(16, 2),
        help="Cash paid to vendors from shift cash. Reduces expected holding.",
    )
    expense_amount = fields.Float(
        'Expenses', compute='_compute_from_payments', store=True, digits=(16, 2),
        help="Small expenses paid directly from shift cash.",
    )

    # ── DIRECT SALES RECEIPTS (account.move out_receipt, cash journals) ─────────
    direct_sales_cash = fields.Float(
        'Direct Cash Sales', compute='_compute_from_receipts', store=True, digits=(16, 2),
        help="Posted Sales Receipts (non-fuel, cash journal) for this attendant/shift. "
             "Dry-stock cash sales (carwash, LPG, misc) not captured by POS or pump meter.",
    )
    direct_sales_digital = fields.Float(
        'Direct Digital Sales', compute='_compute_from_receipts', store=True, digits=(16, 2),
        help="Posted Sales Receipts via digital/bank journal (MPesa, card). "
             "Not physical cash — informational only.",
    )
    direct_sales_credit = fields.Float(
        'Direct Credit Sales', compute='_compute_from_receipts', store=True, digits=(16, 2),
        help="Posted Sales Receipts on credit (AR). "
             "Creates receivable, does not affect physical cash.",
    )

    # ── TOTALS ────────────────────────────────────────────────────────────────
    total_in = fields.Float(
        'Expected Cash', compute='_compute_balance', store=True, digits=(16, 2),
        help="All cash this attendant should have: sales + receipts + float - drops.",
    )
    total_out = fields.Float(
        'Accounted Cash', compute='_compute_balance', store=True, digits=(16, 2),
        help="Physical cash + digital payments + expenses + vendor payments.",
    )
    balance = fields.Float(
        'Balance', compute='_compute_balance', store=True, digits=(16, 2),
        help="Expected Cash − Accounted Cash. Must be 0 for shift to close.",
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

    # ── Compute: POS payment breakdown (MPesa / Card / AR) per attendant ───────
    # POS orders are matched by employee_id first (Odoo 18 POS carries this),
    # falling back to cashier_id→user when employee_id is not set.

    @api.depends(
        'shift_id.pos_session_ids',
        'attendant_id',
        'attendant_id.user_id',
    )
    def _compute_from_pos(self):
        PayMethod = self.env['pos.payment.method']
        mpesa_methods = PayMethod.search([('name', 'ilike', 'mpesa')])
        card_methods  = PayMethod.search([('name', 'ilike', 'card')])
        ar_methods    = (
            PayMethod.search([('name', 'ilike', 'account')])
            | PayMethod.search([('name', 'ilike', 'credit')])
        )

        PosOrder = self.env['pos.order']
        has_employee_field = 'employee_id' in PosOrder._fields

        for rec in self:
            sessions = rec.shift_id.pos_session_ids
            attendant = rec.attendant_id

            if not sessions or not attendant:
                rec.mpesa_amount = 0.0
                rec.card_amount  = 0.0
                rec.ar_amount    = 0.0
                continue

            # Build order domain — prefer employee_id, fall back to user
            if has_employee_field:
                orders = PosOrder.search([
                    ('session_id', 'in', sessions.ids),
                    ('employee_id', '=', attendant.id),
                ])
            else:
                orders = PosOrder.search([
                    ('session_id', 'in', sessions.ids),
                    ('cashier_id', '=', attendant.user_id.id),
                ]) if attendant.user_id else PosOrder

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

    # ── Compute: Direct Sales Receipts (C2.6) ────────────────────────────────────
    # account.move out_receipt linked to this shift+attendant, posted.
    # Cash classification derived from journal type (cash / bank / other).
    # Fuel products excluded — already captured in reported_sales from pump meters.

    @api.depends('shift_id', 'attendant_id')
    def _compute_from_receipts(self):
        AccountMove = self.env['account.move']
        # Skip computation if fms_accounting not installed
        has_fms = 'fms_shift_id' in AccountMove._fields and 'fms_payment_classification' in AccountMove._fields
        for rec in self:
            if not rec.shift_id or not rec.attendant_id or not has_fms:
                rec.direct_sales_cash = 0.0
                rec.direct_sales_digital = 0.0
                rec.direct_sales_credit = 0.0
                continue

            receipts = AccountMove.search([
                ('move_type', '=', 'out_receipt'),
                ('fms_shift_id', '=', rec.shift_id.id),
                ('fms_attendant_id', '=', rec.attendant_id.id),
                ('state', '=', 'posted'),
            ])

            cash_total = digital_total = credit_total = 0.0
            for r in receipts:
                # Exclude fuel lines from this attendant cash sum
                # (fuel revenue is already in reported_sales from pump meters)
                non_fuel_total = sum(
                    line.price_subtotal
                    for line in r.invoice_line_ids
                    if not line.product_id.fms_is_fuel
                )
                cls = r.fms_payment_classification
                if cls == 'cash':
                    cash_total += non_fuel_total
                elif cls == 'digital':
                    digital_total += non_fuel_total
                else:
                    credit_total += non_fuel_total

            rec.direct_sales_cash = cash_total
            rec.direct_sales_digital = digital_total
            rec.direct_sales_credit = credit_total

    # ── Compute: Cash movements from account.payment (FIN-002/FIN-006) ──────────
    # Uses SQL aggregation to avoid N+1 ORM queries across potentially large
    # payment tables. Groups by (shift_id, attendant_id, fms_payment_context).

    @api.depends('shift_id', 'attendant_id')
    def _compute_from_payments(self):
        records_with_shift = self.filtered(lambda r: r.shift_id and r.attendant_id)
        records_without = self - records_with_shift

        for rec in records_without:
            rec.customer_receipt_amount = 0.0
            rec.float_amount = 0.0
            rec.cash_drop_amount = 0.0
            rec.vendor_payment_amount = 0.0
            rec.expense_amount = 0.0

        if not records_with_shift:
            return

        shift_ids = records_with_shift.mapped('shift_id').ids
        attendant_ids = records_with_shift.mapped('attendant_id').ids

        # Single SQL query — aggregate by shift, attendant, context
        # Only 'posted' payments count (state='posted' in account.payment)
        self.env.cr.execute("""
            SELECT
                fms_shift_id,
                COALESCE(fms_attendant_id, 0) AS attendant_id,
                fms_payment_context,
                COALESCE(SUM(amount), 0) AS total
            FROM account_payment
            WHERE fms_shift_id = ANY(%s)
              AND state = 'posted'
              AND fms_payment_context IS NOT NULL
            GROUP BY fms_shift_id, fms_attendant_id, fms_payment_context
        """, (shift_ids,))
        rows = self.env.cr.fetchall()

        # Index: (shift_id, attendant_id, context) -> amount
        agg = {}
        for shift_id, att_id, ctx, total in rows:
            agg[(shift_id, att_id, ctx)] = total

        def _get(rec, ctx, attendant_scoped=True):
            att = rec.attendant_id.id if attendant_scoped else 0
            shift = rec.shift_id.id
            # Try attendant-scoped first, fall back to shift-level (attendant_id NULL)
            return agg.get((shift, att, ctx), 0.0) + agg.get((shift, 0, ctx), 0.0) if attendant_scoped \
                else agg.get((shift, 0, ctx), 0.0)

        for rec in records_with_shift:
            att = rec.attendant_id.id
            shift = rec.shift_id.id
            # customer_receipt: attendant-scoped inbound cash from customers
            rec.customer_receipt_amount = agg.get((shift, att, 'customer_receipt'), 0.0)
            # float: shift-level (issued to the shift, split by attendant_id if present)
            rec.float_amount = agg.get((shift, att, 'cash_float'), 0.0) + agg.get((shift, 0, 'cash_float'), 0.0)
            # cash_drop + cash_pickup: reduces attendant's expected holding
            rec.cash_drop_amount = (
                agg.get((shift, att, 'cash_drop'), 0.0)
                + agg.get((shift, 0, 'cash_drop'), 0.0)
            )
            # vendor_payment: outbound from shift cash
            rec.vendor_payment_amount = agg.get((shift, att, 'vendor_payment'), 0.0)
            # expense: small expenses from shift cash
            rec.expense_amount = agg.get((shift, att, 'expense'), 0.0)

    # ── Compute: Balance ─────────────────────────────────────────────────────

    @api.depends(
        'reported_sales', 'cash_collected',
        'mpesa_amount', 'card_amount', 'ar_amount',
        'customer_receipt_amount', 'float_amount', 'cash_drop_amount',
        'vendor_payment_amount', 'expense_amount',
        'direct_sales_cash', 'direct_sales_digital',
        'shift_id.meter_entry_ids.elec_cash_sold',
        'shift_id.meter_entry_ids.attendant_id',
    )
    def _compute_balance(self):
        for rec in self:
            # total_in: all cash this attendant should physically have
            # direct_sales_cash: dry-stock cash receipts (not captured by pump meters)
            rec.total_in = (
                rec.reported_sales
                + rec.customer_receipt_amount
                + rec.float_amount
                + rec.direct_sales_cash
                - rec.cash_drop_amount
            )
            # total_out: all ways cash left the attendant's hands
            # direct_sales_digital counted like mpesa — not physical cash
            rec.total_out = (
                rec.cash_collected
                + rec.mpesa_amount
                + rec.card_amount
                + rec.ar_amount
                + rec.vendor_payment_amount
                + rec.expense_amount
                + rec.direct_sales_digital
            )
            rec.balance = rec.total_in - rec.total_out

    # ── Validation ───────────────────────────────────────────────────────────

    @api.constrains('reported_sales')
    def _check_reported_sales_non_negative(self):
        for rec in self:
            if rec.reported_sales < 0:
                raise ValidationError(
                    f"Attendant {rec.attendant_id.name or rec.id}: "
                    f"Expected cash ({rec.shift_id.company_id.currency_id.name} {rec.reported_sales:,.2f}) is negative. "
                    "Meter readings may have been entered in reverse order."
                )

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
