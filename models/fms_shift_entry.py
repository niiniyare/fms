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
        # Cache price period per shift date — one search per unique date, not per meter entry
        period_cache = {}  # date -> fms.price.period recordset (or False)
        price_cache = {}   # (date, product_id) -> pump_price

        for e in self:
            shift_date = e.shift_id.date if e.shift_id else None
            if not e.product_id:
                e.amount_elec = 0.0
                continue

            if shift_date and shift_date not in period_cache:
                period_cache[shift_date] = self.env['fms.price.period'].search([
                    ('date_start', '<=', shift_date),
                    ('date_end',   '>=', shift_date),
                    ('active', '=', True),
                ], limit=1)

            period = period_cache.get(shift_date)
            cache_key = (shift_date, e.product_id.id)
            if cache_key not in price_cache:
                if period:
                    line = period.price_line_ids.filtered(lambda l: l.product_id == e.product_id)
                    price_cache[cache_key] = line[0].pump_price if line else e.product_id.list_price or 0.0
                else:
                    price_cache[cache_key] = e.product_id.list_price or 0.0

            e.amount_elec = e.qty_sold_elec * price_cache[cache_key]

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
        result = super().write(vals)
        if 'attendant_id' in vals:
            for shift in self.mapped('shift_id'):
                prefs = self.env['fms.site.preferences'].get_for_company(shift.company_id)
                if prefs.auto_sync_attendants:
                    shift._sync_attendant_cash_lines()
        return result

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

    opening_volume = fields.Float('Opening (L)', digits=(16, 2), readonly=True,
        help="Closing dip from previous shift — auto-populated on shift open.")
    closing_volume = fields.Float('Closing Dip (L)', digits=(16, 2),
        help="Physical stick reading at end of shift.")
    book_stock_open = fields.Float('Book Stock (L)', digits=(16, 2), readonly=True,
        help="Odoo inventory stock for this tank at the moment the shift was opened.")

    notes = fields.Char('Notes')

    qty_change = fields.Float(
        'Stock Change (L)', digits=(16, 2),
        compute='_compute_dip_derived', store=False,
        help="closing_volume − opening_volume (negative = net sales).",
    )
    variance_pct = fields.Float(
        'Variance %', digits=(16, 4),
        compute='_compute_dip_derived', store=False,
        help="abs(qty_change) / closing_volume × 100. Zero when closing_volume is 0.",
    )

    @api.depends('opening_volume', 'closing_volume')
    def _compute_dip_derived(self):
        for entry in self:
            entry.qty_change = entry.closing_volume - entry.opening_volume
            if entry.closing_volume:
                entry.variance_pct = abs(entry.qty_change) / entry.closing_volume * 100.0
            else:
                entry.variance_pct = 0.0

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

    def _create_dip_log(self, variance_data=None):
        """Copy this entry to fms.dip_log (called by shift on close).

        variance_data: dict from fms.shift._compute_dip_variance_data().
        When provided, snapshot fields (meter_sales, shift_variance, etc.) are stored.
        """
        self.ensure_one()
        vals = {
            'shift_id':        self.shift_id.id,
            'location_id':     self.location_id.id,
            'opening_volume':  self.opening_volume,
            'closing_volume':  self.closing_volume,
            'book_stock_open': self.book_stock_open,
        }
        if variance_data:
            vals.update({
                'meter_sales_snapshot': variance_data.get('meter_sales', 0.0),
                'shift_variance':       variance_data.get('shift_variance', 0.0),
                'shift_var_amount':     variance_data.get('shift_var_amount', 0.0),
                'month_variance':       variance_data.get('month_variance', 0.0),
                'month_var_amount':     variance_data.get('month_var_amount', 0.0),
                'var_rate':             variance_data.get('var_rate', 0.0),
            })
        return self.env['fms.dip_log'].sudo().create(vals)


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

    # ── FC Cash fields (new reconciliation system) ───────────────────────────
    # These replace the old balance field as the shift-close gate.
    # fc_captured = all captured sales (meter + fc_lines + floats + customer receipts)
    # fc_collected = all postings that drain FC Cash (invoices + receipts + drops + expenses)
    # fc_variance  = fc_captured - fc_collected → must be 0 to close

    fc_captured = fields.Float(
        'FC Captured', digits=(16, 2), store=False, compute='_compute_fc_variance',
    )
    fc_collected = fields.Float(
        'FC Collected', digits=(16, 2), store=False, compute='_compute_fc_variance',
    )
    fc_variance = fields.Float(
        'FC Variance', digits=(16, 2), store=False, compute='_compute_fc_variance',
        help="fc_captured - fc_collected. Must be 0.00 before shift can close.",
    )
    # Breakdown — DR side
    fc_meter_sales = fields.Float('Fuel (Meter)', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_nonfuel_sales = fields.Float('Non Fuel Sales', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_float_amount = fields.Float('Floats Issued', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_cust_receipt = fields.Float('FC Cust Receipts', digits=(16, 2), store=False, compute='_compute_fc_variance')
    # Breakdown — CR side
    fc_invoice_amount = fields.Float('FC Invoices', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_receipt_amount = fields.Float('FC Sales Receipts', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_drop_amount = fields.Float('FC Cash Drops', digits=(16, 2), store=False, compute='_compute_fc_variance')
    fc_expense_amount = fields.Float('FC Expenses', digits=(16, 2), store=False, compute='_compute_fc_variance')

    # ── Compute: FC Cash variance (new reconciliation system) ────────────────

    @api.depends(
        'shift_id', 'attendant_id',
        'shift_id.meter_entry_ids.attendant_id',
        'shift_id.meter_entry_ids.elec_cash_sold',
        'shift_id.fc_line_ids.attendant_id',
        'shift_id.fc_line_ids.sales_amount',
        'shift_id.fc_line_ids.line_type',
    )
    def _compute_fc_variance(self):
        # Column-existence checks run once per compute call, not per record
        self.env.cr.execute("""
            SELECT
                MAX(CASE WHEN table_name = 'account_payment' AND column_name = 'fms_shift_id' THEN 1 ELSE 0 END),
                MAX(CASE WHEN table_name = 'account_move'    AND column_name = 'fms_shift_id' THEN 1 ELSE 0 END),
                MAX(CASE WHEN table_name = 'hr_expense'      AND column_name = 'fms_shift_id' THEN 1 ELSE 0 END)
            FROM information_schema.columns
            WHERE table_name IN ('account_payment', 'account_move', 'hr_expense')
              AND column_name = 'fms_shift_id'
        """)
        row = self.env.cr.fetchone() or (0, 0, 0)
        has_payment_fms, has_move_fms, has_hr_expense_fms = bool(row[0]), bool(row[1]), bool(row[2])

        valid = self.filtered(lambda r: r.shift_id and r.attendant_id and isinstance(r.shift_id.id, int))
        for rec in self - valid:
            for f in ('fc_captured', 'fc_collected', 'fc_variance', 'fc_meter_sales',
                      'fc_nonfuel_sales', 'fc_float_amount', 'fc_cust_receipt',
                      'fc_invoice_amount', 'fc_receipt_amount', 'fc_drop_amount', 'fc_expense_amount'):
                rec[f] = 0.0

        if not valid:
            return

        shift_ids = list({r.shift_id.id for r in valid})

        # Batch account_payment: (shift_id, attendant_id, context) -> amount
        pay_agg = {}
        if has_payment_fms:
            self.env.cr.execute("""
                SELECT fms_shift_id, COALESCE(fms_attendant_id, 0), fms_payment_context,
                       COALESCE(SUM(amount), 0)
                FROM account_payment
                WHERE fms_shift_id = ANY(%s)
                  AND state IN ('in_process', 'paid')
                  AND fms_payment_context IN ('cash_float', 'customer_receipt', 'cash_drop', 'expense')
                GROUP BY fms_shift_id, fms_attendant_id, fms_payment_context
            """, (shift_ids,))
            for sid, aid, ctx, amt in self.env.cr.fetchall():
                pay_agg[(sid, aid, ctx)] = float(amt)

        # Batch account_move: (shift_id, attendant_id, move_type) -> amount
        move_agg = {}
        if has_move_fms:
            self.env.cr.execute("""
                SELECT fms_shift_id, COALESCE(fms_attendant_id, 0), move_type,
                       COALESCE(SUM(amount_total), 0)
                FROM account_move
                WHERE fms_shift_id = ANY(%s)
                  AND move_type IN ('out_invoice', 'out_receipt')
                  AND state = 'posted'
                GROUP BY fms_shift_id, fms_attendant_id, move_type
            """, (shift_ids,))
            for sid, aid, mtype, amt in self.env.cr.fetchall():
                move_agg[(sid, aid, mtype)] = float(amt)

        # Batch hr_expense: (shift_id, attendant_id) -> amount
        exp_agg = {}
        if has_hr_expense_fms:
            self.env.cr.execute("""
                SELECT e.fms_shift_id, COALESCE(e.fms_attendant_id, 0),
                       COALESCE(SUM(e.total_amount), 0)
                FROM hr_expense e
                JOIN hr_expense_sheet s ON s.id = e.sheet_id
                WHERE e.fms_shift_id = ANY(%s)
                  AND s.state IN ('post', 'done')
                GROUP BY e.fms_shift_id, e.fms_attendant_id
            """, (shift_ids,))
            for sid, aid, amt in self.env.cr.fetchall():
                exp_agg[(sid, aid)] = float(amt)

        for rec in valid:
            shift = rec.shift_id
            att_id = rec.attendant_id.id
            sid = shift.id

            meter_sales = sum(
                e.elec_cash_sold for e in shift.meter_entry_ids if e.attendant_id.id == att_id
            )
            fc_sales = sum(
                l.sales_amount for l in shift.fc_line_ids if l.attendant_id.id == att_id
            )

            float_amt = pay_agg.get((sid, att_id, 'cash_float'), 0.0)
            cust_receipt = pay_agg.get((sid, att_id, 'customer_receipt'), 0.0)
            captured = meter_sales + fc_sales + float_amt + cust_receipt

            invoice_amt = move_agg.get((sid, att_id, 'out_invoice'), 0.0)
            receipt_amt = move_agg.get((sid, att_id, 'out_receipt'), 0.0)
            drop_amt = pay_agg.get((sid, att_id, 'cash_drop'), 0.0)
            expense_amt = (
                pay_agg.get((sid, att_id, 'expense'), 0.0)
                + exp_agg.get((sid, att_id), 0.0)
            )

            # When no GL drop payments exist, fall back to cash_collected (manual entry)
            # so the gate sees the variance even without fms_accounting installed.
            if drop_amt == 0.0:
                drop_amt = rec.cash_collected or 0.0

            collected = invoice_amt + receipt_amt + drop_amt + expense_amt

            rec.fc_meter_sales    = meter_sales
            rec.fc_nonfuel_sales  = fc_sales
            rec.fc_float_amount   = float_amt
            rec.fc_cust_receipt   = cust_receipt
            rec.fc_invoice_amount = invoice_amt
            rec.fc_receipt_amount = receipt_amt
            rec.fc_drop_amount    = drop_amt
            rec.fc_expense_amount = expense_amt
            rec.fc_captured       = captured
            rec.fc_collected      = collected
            rec.fc_variance       = captured - collected

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
        mpesa_ids = set(mpesa_methods.ids)
        card_ids  = set(card_methods.ids)
        ar_ids    = set(ar_methods.ids)

        PosOrder = self.env['pos.order']
        has_employee_field = 'employee_id' in PosOrder._fields

        # Group records by shift to batch POS queries per shift, not per attendant
        shifts_map = {}
        for rec in self:
            if rec.shift_id and rec.attendant_id and rec.shift_id.pos_session_ids:
                shifts_map.setdefault(rec.shift_id.id, []).append(rec)

        # Build per-shift payment breakdown: (shift_id, attendant_id) -> (mpesa, card, ar)
        agg = {}   # (shift_id, attendant_key) -> [mpesa, card, ar]

        for shift_id, recs in shifts_map.items():
            shift = recs[0].shift_id
            session_ids = shift.pos_session_ids.ids

            # One order search per shift (not per attendant)
            all_orders = PosOrder.search([('session_id', 'in', session_ids)])
            if not all_orders:
                continue

            # One payment search per shift
            all_payments = self.env['pos.payment'].search([
                ('pos_order_id', 'in', all_orders.ids)
            ])

            # Index payments by order_id
            pay_by_order = {}
            for p in all_payments:
                pay_by_order.setdefault(p.pos_order_id.id, []).append(p)

            # Distribute orders to attendants
            for order in all_orders:
                if has_employee_field:
                    att_key = order.employee_id.id if order.employee_id else 0
                else:
                    att_key = order.cashier_id.id if order.cashier_id else 0

                if not att_key:
                    continue
                bucket = agg.setdefault((shift_id, att_key), [0.0, 0.0, 0.0])
                for p in pay_by_order.get(order.id, []):
                    mid = p.payment_method_id.id
                    if mid in mpesa_ids:
                        bucket[0] += p.amount
                    elif mid in card_ids:
                        bucket[1] += p.amount
                    elif mid in ar_ids:
                        bucket[2] += p.amount

        for rec in self:
            sessions = rec.shift_id.pos_session_ids if rec.shift_id else False
            attendant = rec.attendant_id
            if not sessions or not attendant:
                rec.mpesa_amount = 0.0
                rec.card_amount  = 0.0
                rec.ar_amount    = 0.0
                continue

            if has_employee_field:
                att_key = attendant.id
            else:
                att_key = attendant.user_id.id if attendant.user_id else 0

            bucket = agg.get((rec.shift_id.id, att_key), [0.0, 0.0, 0.0])
            rec.mpesa_amount = bucket[0]
            rec.card_amount  = bucket[1]
            rec.ar_amount    = bucket[2]

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
        records_with_shift = self.filtered(lambda r: r.shift_id and r.attendant_id and isinstance(r.shift_id.id, int))
        records_without = self - records_with_shift

        for rec in records_without:
            rec.customer_receipt_amount = 0.0
            rec.float_amount = 0.0
            rec.cash_drop_amount = 0.0
            rec.vendor_payment_amount = 0.0
            rec.expense_amount = 0.0

        if not records_with_shift:
            return

        # Graceful degradation: fms_shift_id on account_payment added by fms_accounting.
        # If fms_accounting not installed, skip payment aggregation — zero all fields.
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'account_payment' AND column_name = 'fms_shift_id' LIMIT 1
        """)
        if not self.env.cr.fetchone():
            for rec in records_with_shift:
                rec.customer_receipt_amount = 0.0
                rec.float_amount = 0.0
                rec.cash_drop_amount = 0.0
                rec.vendor_payment_amount = 0.0
                rec.expense_amount = 0.0
            return

        shift_ids = records_with_shift.mapped('shift_id').ids

        # Single SQL query — aggregate by shift, attendant, context
        # Only confirmed payments count (Odoo 18: state IN ('in_process','paid'))
        self.env.cr.execute("""
            SELECT
                fms_shift_id,
                COALESCE(fms_attendant_id, 0) AS attendant_id,
                fms_payment_context,
                COALESCE(SUM(amount), 0) AS total
            FROM account_payment
            WHERE fms_shift_id = ANY(%s)
              AND state IN ('in_process', 'paid')
              AND fms_payment_context IS NOT NULL
            GROUP BY fms_shift_id, fms_attendant_id, fms_payment_context
        """, (shift_ids,))
        rows = self.env.cr.fetchall()

        # Index: (shift_id, attendant_id, context) -> amount
        agg = {}
        for shift_id, att_id, ctx, total in rows:
            agg[(shift_id, att_id, ctx)] = total

        # Also aggregate hr.expense records posted via forecourt expense form
        # (fms_accounting adds fms_shift_id + fms_attendant_id to hr.expense)
        hr_exp_agg = {}
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'hr_expense' AND column_name = 'fms_shift_id' LIMIT 1
        """)
        if self.env.cr.fetchone():
            self.env.cr.execute("""
                SELECT e.fms_shift_id,
                       COALESCE(e.fms_attendant_id, 0) AS attendant_id,
                       COALESCE(SUM(e.total_amount), 0) AS total
                FROM hr_expense e
                JOIN hr_expense_sheet s ON s.id = e.sheet_id
                WHERE e.fms_shift_id = ANY(%s)
                  AND s.state IN ('post', 'done')
                GROUP BY e.fms_shift_id, e.fms_attendant_id
            """, (shift_ids,))
            for shift_id, att_id, total in self.env.cr.fetchall():
                hr_exp_agg[(shift_id, att_id)] = float(total)

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
            # expense: account.payment context='expense' + posted hr.expense (if fms_accounting installed)
            rec.expense_amount = agg.get((shift, att, 'expense'), 0.0) + hr_exp_agg.get((shift, att), 0.0)

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
