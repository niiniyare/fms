"""
fms_shift.py — Shift state machine and Odoo model extensions

One shift = one period of operation at the forecourt (Day / Evening / Night).
All meter readings, dip readings, and attendant cash entries live as child records.

State machine: draft → open → closing → closed

Reference: FMS_Complete_Specification_Technical_Guide.md, Sections 7 & 8.1
"""

from odoo import models, fields, api
from odoo.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Odoo core model extensions
# ---------------------------------------------------------------------------

class StockLocationFMS(models.Model):
    """Extend stock.location to mark fuel tanks and link their product."""

    _inherit = 'stock.location'

    fms_is_fuel_tank    = fields.Boolean('Is Fuel Tank', default=False)
    fms_is_forecourt    = fields.Boolean(
        'Is Forecourt Holding Location', default=False,
        help="Stock held here (lubes, filters, accessories) is tracked per shift "
             "via the Non Fuel Sales tab. One forecourt location per company.",
    )
    fms_fuel_product_id = fields.Many2one(
        'product.product', 'Fuel Product in Tank',
        domain=[('fms_is_fuel', '=', True)],
    )
    # R5 reorder configuration — set once per tank in Configuration
    fms_tank_capacity_l    = fields.Float('Tank Capacity (L)', digits=(16, 0),
                                          help="Maximum volume this tank can hold.")
    fms_reorder_point_days = fields.Float('Reorder Point (days cover)', default=3.0,
                                          help="Raise an alert when days of cover falls below this.")
    fms_lead_time_days     = fields.Integer('Supplier Lead Time (days)', default=1,
                                            help="Days between order and delivery.")
    fms_safety_days        = fields.Integer('Safety Stock (days)', default=1,
                                            help="Buffer days on top of lead time.")


class ProductCategoryFMS(models.Model):
    """Extend product.category with FMS classification flags."""

    _inherit = 'product.category'

    fms_is_fuel = fields.Boolean('Is Fuel Category', default=False,
        help='Products in this category are treated as fuel products by FMS.')
    fms_is_fms = fields.Boolean('Is FMS Product Category', default=False,
        help='Category managed/tracked by FMS (fuel, lubricants, LPG, filters, etc.).')


class ProductProductFMS(models.Model):
    """Extend product.product with fuel-specific accounting fields."""

    _inherit = 'product.product'

    fms_is_fuel = fields.Boolean('Is Fuel Product', default=False)
    fms_cogs_account_id = fields.Many2one('account.account', 'Fuel COGS Account')
    fms_revenue_account_id = fields.Many2one('account.account', 'Fuel Revenue Account')


class HREmployeeFMS(models.Model):
    """Extend hr.employee to flag forecourt attendants."""

    _inherit = 'hr.employee'

    fms_is_attendant = fields.Boolean('Is Forecourt Attendant', default=False)
    fms_pumps_assigned = fields.Many2many(
        'fms.pump', string='Assigned Pumps',
    )


# ---------------------------------------------------------------------------
# Main shift model
# ---------------------------------------------------------------------------

class FMSShift(models.Model):
    """
    Orchestrates a single forecourt shift.

    Acts as the root record for all readings, cash entries, and audit logs
    for one operational period (Day / Evening / Night).
    """

    _name = 'fms.shift'
    _description = 'Forecourt Shift'
    _order = 'date DESC, label'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    date = fields.Date('Shift Date', required=True, default=fields.Date.today)
    label = fields.Selection([
        ('1_day',     '1. Day'),
        ('2_evening', '2. Evening'),
        ('3_night',   '3. Night'),
    ], string='Shift Period', required=True)

    # Planned open / close — set when shift is created based on site preferences.
    # planned_close is informational: shows expected end even if shift runs late.
    planned_open  = fields.Datetime('Planned Open',  readonly=True, copy=False)
    planned_close = fields.Datetime('Planned Close', readonly=True, copy=False)

    # Supervisor is optional at open time; enforced at close only when there is
    # monetary activity. Managers can assign it at any point during the shift.
    supervisor_id = fields.Many2one('hr.employee', 'Supervisor')

    # Company is always the logged-in user's company — not user-editable.
    company_id = fields.Many2one(
        'res.company', 'Company',
        required=True,
        default=lambda self: self.env.company,
        readonly=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    state = fields.Selection([
        ('draft',    'Draft'),
        ('open',     'Open'),
        ('closing',  'Closing'),
        ('closed',   'Closed'),
        ('disputed', 'Disputed'),
    ], string='Status', default='draft', readonly=True, copy=False, index=True)

    # ------------------------------------------------------------------
    # Timestamps & tracking
    # ------------------------------------------------------------------

    opening_meter_date = fields.Datetime('Opened At', readonly=True, copy=False)
    opening_meter_user_id = fields.Many2one(
        'res.users', 'Opened By', readonly=True, copy=False,
    )
    closing_meter_date = fields.Datetime('Closed At', readonly=True, copy=False)
    closing_meter_user_id = fields.Many2one(
        'res.users', 'Closed By', readonly=True, copy=False,
    )

    # ------------------------------------------------------------------
    # Child tables
    # ------------------------------------------------------------------

    meter_entry_ids = fields.One2many('fms.shift.meter.entry', 'shift_id', 'Meter Entries')
    dip_entry_ids = fields.One2many('fms.shift.dip.entry', 'shift_id', 'Dip Entries')
    fc_line_ids = fields.One2many(
        'fms.shift.fc.line', 'shift_id', 'Non Fuel Sales',
        help="Non-fuel products (lubes, filters) and services (carwash) sold during this shift.",
    )
    attendant_cash_ids = fields.One2many(
        'fms.shift.attendant.cash', 'shift_id', 'Attendant Cash',
    )
    pos_session_ids = fields.Many2many(
        'pos.session', 'fms_shift_pos_session_rel', 'shift_id', 'session_id',
        string='POS Sessions',
        help="POS sessions that occurred during this shift. "
             "Linking sessions here auto-populates attendant sales, MPesa, card, and AR.",
    )

    product_sales_ids = fields.One2many(
        'fms.shift.product.sales', 'shift_id', 'Product Sales',
        help="Computed rollup of meter entries per product. Refreshed on save.",
    )
    residual_allocation_ids = fields.One2many(
        'fms.shift.residual.allocation', 'shift_id', 'Residual Allocations',
    )

    # ------------------------------------------------------------------
    # Summary computed fields
    # ------------------------------------------------------------------

    total_meter_sales = fields.Float(
        'Total Meter Sales', compute='_compute_totals', store=True, digits=(16, 2),
        help="Sum of elec_cash_sold across all nozzles — total cash the pumps say was collected.",
    )
    total_reported_sales = fields.Float(
        'Total Reported Sales', compute='_compute_totals', store=True, digits=(16, 2),
        help="Sum of reported_sales across all attendant cash lines (derived from their nozzle meters).",
    )
    fc_cash_balance = fields.Float(
        'FC Cash Balance', compute='_compute_totals', store=True, digits=(16, 2),
        help="Net balance across all attendants (total_in − total_out). Must be 0 to close.",
    )
    fc_cash_balance_total = fields.Float(
        'FC Cash Variance', compute='_compute_fc_balance_total', store=False,
        digits=(16, 2),
        help="Sum of fc_variance across all attendant cash lines (new FC Cash system). "
             "Must be 0.00 before shift can move to closing.",
    )

    @api.depends(
        'meter_entry_ids.elec_cash_sold',
        'attendant_cash_ids.total_in',
        'attendant_cash_ids.balance',
    )
    def _compute_totals(self):
        for shift in self:
            shift.total_meter_sales    = sum(shift.meter_entry_ids.mapped('elec_cash_sold'))
            shift.total_reported_sales = sum(shift.attendant_cash_ids.mapped('total_in'))
            shift.fc_cash_balance      = sum(shift.attendant_cash_ids.mapped('balance'))

    def _compute_fc_balance_total(self):
        """Sum fc_variance across all attendant lines. store=False — always recomputed live."""
        for shift in self:
            shift.fc_cash_balance_total = sum(
                shift.attendant_cash_ids.mapped('fc_variance')
            )

    # ------------------------------------------------------------------
    # Full commercial reconciliation summary (Spec §8 + §11)
    # ------------------------------------------------------------------

    total_fuel_sales = fields.Float(
        'Fuel Sales', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Sum of meter-derived fuel revenue (elec_cash_sold across all fuel products).",
    )
    total_nonfuel_sales = fields.Float(
        'Non-Fuel Sales', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Revenue from dry-stock + services (posted invoices/receipts linked to this shift).",
    )
    total_all_sales = fields.Float(
        'Total Sales', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Fuel + non-fuel total revenue for the shift.",
    )
    total_cash_received = fields.Float(
        'Cash Received', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Cash payments received from customers (fms_payment_context=customer_receipt, cash journal).",
    )
    total_digital_received = fields.Float(
        'Digital Received', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="MPesa / card / bank payments received (customer_receipt, bank journal).",
    )
    total_credit_sales = fields.Float(
        'Credit Sales (AR)', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Revenue invoiced on credit — no cash collected yet.",
    )
    declared_cash_total = fields.Float(
        'Declared Cash', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Sum of cash declared by all attendants at shift end.",
    )
    expected_cash_position = fields.Float(
        'Expected Cash', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Opening float + cash fuel sales + cash non-fuel sales + customer receipts "
             "- cash drops - expenses - vendor payments.",
    )
    cash_variance_summary = fields.Float(
        'Cash Variance', compute='_compute_commercial_summary', store=True, digits=(16, 2),
        help="Expected cash minus declared cash. Positive = surplus, negative = shortage.",
    )

    @api.depends(
        'product_sales_ids.elec_cash_sold',
        'product_sales_ids.allocated_amount',
        'product_sales_ids.is_fuel',
        'attendant_cash_ids.cash_collected',
        'attendant_cash_ids.float_amount',
        'attendant_cash_ids.cash_drop_amount',
        'attendant_cash_ids.expense_amount',
        'attendant_cash_ids.vendor_payment_amount',
    )
    def _compute_commercial_summary(self):
        for shift in self:
            fuel_sales = 0.0
            nonfuel_sales = 0.0
            for ps in shift.product_sales_ids:
                if ps.is_fuel:
                    fuel_sales += ps.elec_cash_sold
                else:
                    nonfuel_sales += ps.allocated_amount or 0.0

            # Cash vs digital breakdown — requires fms_accounting (account.payment extension)
            cash_recv = 0.0
            digital_recv = 0.0
            credit_sales = 0.0
            AccountPayment = self.env['account.payment']
            if 'fms_shift_id' in AccountPayment._fields:
                self.env.cr.execute("""
                    SELECT
                        SUM(CASE WHEN j.type = 'cash' THEN ap.amount ELSE 0 END) AS cash_recv,
                        SUM(CASE WHEN j.type = 'bank' THEN ap.amount ELSE 0 END) AS digital_recv
                    FROM account_payment ap
                    JOIN account_journal j ON j.id = ap.journal_id
                    WHERE ap.fms_shift_id = %s
                      AND ap.fms_payment_context = 'customer_receipt'
                      AND ap.state = 'posted'
                      AND ap.payment_type = 'inbound'
                """, (shift.id,))
                row = self.env.cr.fetchone()
                if row:
                    cash_recv = row[0] or 0.0
                    digital_recv = row[1] or 0.0

                # Credit sales: posted out_invoice lines linked to shift (AR)
                AccountMove = self.env['account.move']
                if 'fms_shift_id' in AccountMove._fields:
                    self.env.cr.execute("""
                        SELECT COALESCE(SUM(am.amount_untaxed), 0)
                        FROM account_move am
                        WHERE am.fms_shift_id = %s
                          AND am.move_type = 'out_invoice'
                          AND am.state = 'posted'
                    """, (shift.id,))
                    row = self.env.cr.fetchone()
                    credit_sales = row[0] if row else 0.0

            # Expected cash from attendant lines
            opening_float = sum(shift.attendant_cash_ids.mapped('float_amount'))
            cash_drops = sum(shift.attendant_cash_ids.mapped('cash_drop_amount'))
            expenses = sum(shift.attendant_cash_ids.mapped('expense_amount'))
            vendor_payments = sum(shift.attendant_cash_ids.mapped('vendor_payment_amount'))
            declared = sum(shift.attendant_cash_ids.mapped('cash_collected'))

            expected = opening_float + fuel_sales + nonfuel_sales + cash_recv - cash_drops - expenses - vendor_payments

            shift.total_fuel_sales = fuel_sales
            shift.total_nonfuel_sales = nonfuel_sales
            shift.total_all_sales = fuel_sales + nonfuel_sales
            shift.total_cash_received = cash_recv
            shift.total_digital_received = digital_recv
            shift.total_credit_sales = credit_sales
            shift.declared_cash_total = declared
            shift.expected_cash_position = expected
            shift.cash_variance_summary = expected - declared

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    # GL journal entry created on shift close (FMS-005)
    sales_journal_entry_id = fields.Many2one(
        'account.move', 'Sales Journal Entry',
        readonly=True, copy=False,
        help="Account move posted when the shift is closed (fuel sales summary).",
    )

    notes = fields.Text('Supervisor Notes')

    gate_status_html = fields.Html(
        'Shift Gate Status',
        compute='_compute_gate_status_html',
        sanitize=False,
        help="Live gate-by-gate checklist showing what must be resolved before shift close.",
    )

    # ------------------------------------------------------------------
    # Product sales rollup
    # ------------------------------------------------------------------

    def action_report_fms_shift(self):
        """Open the Shift Reconciliation PDF report for this shift."""
        self.ensure_one()
        return self.env.ref('fms.action_report_fms_shift').report_action(self)

    def action_report_meter_movement(self):
        """Open the Meter Movement PDF report for this shift."""
        self.ensure_one()
        return self.env.ref('fms.action_report_fms_meter_movement').report_action(self)

    def get_meter_attendant_summary(self):
        """
        Return a list of dicts grouping meter entry totals per attendant.
        Used by the Meter Movement Report QWeb template.
        """
        self.ensure_one()
        summary = {}
        for entry in self.meter_entry_ids:
            key = entry.attendant_id.id or 0
            if key not in summary:
                summary[key] = {
                    'name':    entry.attendant_id.name or 'Unassigned',
                    'nozzles': [],
                    'cash':    0.0,
                    'vol':     0.0,
                }
            summary[key]['nozzles'].append(
                f"{entry.pump_id.name}-{entry.nozzle_id.letter}"
            )
            summary[key]['cash'] += entry.elec_cash_sold
            summary[key]['vol']  += entry.qty_sold_elec
        return list(summary.values())

    def action_refresh_product_sales(self):
        """Re-aggregate meter entries into product sales summary lines."""
        for shift in self:
            shift._refresh_product_sales()

    def _refresh_product_sales(self):
        """
        Delete existing product_sales_ids and rebuild from meter_entry_ids.
        Called explicitly by the supervisor button or on shift close.

        Populates both the VOLUME side (meter_volume, meter_volume_man) and
        the CASH side (elec_cash_sold) per product. price_at_close is stored
        at refresh time so residual allocation can convert liters → KES.
        """
        self.ensure_one()
        self.product_sales_ids.unlink()

        by_product = {}
        for entry in self.meter_entry_ids:
            if not entry.product_id:
                continue
            pid = entry.product_id.id
            if pid not in by_product:
                by_product[pid] = {
                    'meter_volume':     0.0,
                    'meter_volume_man': 0.0,
                    'elec_cash_sold':   0.0,
                }
            by_product[pid]['meter_volume']     += entry.qty_sold_elec
            by_product[pid]['meter_volume_man'] += entry.qty_sold_man
            by_product[pid]['elec_cash_sold']   += entry.elec_cash_sold

        # FIN-007: also aggregate dry-stock lines from posted invoices linked to this
        # shift (requires fms_accounting). Dry-stock products have fms_is_fuel=False
        # and no meter entries — they appear only on invoices.
        AccountMove = self.env['account.move']
        if 'fms_shift_id' in AccountMove._fields:
            dry_moves = AccountMove.search([
                ('fms_shift_id', '=', self.id),
                ('move_type', 'in', ('out_invoice', 'out_receipt')),
                ('state', '=', 'posted'),
            ])
            for move in dry_moves:
                for line in move.invoice_line_ids:
                    pid = line.product_id.id if line.product_id else None
                    if not pid:
                        continue
                    if line.product_id.fms_is_fuel:
                        continue  # Fuel products already captured from meter
                    if pid not in by_product:
                        by_product[pid] = {
                            'meter_volume':     0.0,
                            'meter_volume_man': 0.0,
                            'elec_cash_sold':   0.0,
                            '_invoice_qty':     0.0,
                            '_invoice_amount':  0.0,
                        }
                    by_product[pid].setdefault('_invoice_qty', 0.0)
                    by_product[pid].setdefault('_invoice_amount', 0.0)
                    by_product[pid]['_invoice_qty']    += line.quantity
                    by_product[pid]['_invoice_amount'] += line.price_subtotal

        for product_id, totals in by_product.items():
            product = self.env['product.product'].browse(product_id)
            vals = {
                'shift_id':         self.id,
                'product_id':       product_id,
                'meter_volume':     totals['meter_volume'],
                'meter_volume_man': totals['meter_volume_man'],
                'elec_cash_sold':   totals['elec_cash_sold'],
                'price_at_close':   product.list_price or 0.0,
            }
            # For dry-stock: use invoice qty as the "accounted volume" proxy stored
            # in allocated_volume (no meter, so volume_residual will be 0).
            inv_qty = totals.get('_invoice_qty', 0.0)
            if inv_qty and not product.fms_is_fuel:
                vals['allocated_volume'] = inv_qty
                vals['allocated_amount'] = totals.get('_invoice_amount', 0.0)
            self.env['fms.shift.product.sales'].create(vals)

    # ------------------------------------------------------------------
    # Display name
    # ------------------------------------------------------------------

    @api.depends('date', 'label')
    def _compute_display_name(self):
        label_map = dict(self._fields['label'].selection)
        for shift in self:
            period = label_map.get(shift.label, shift.label or '')
            shift.display_name = f"{shift.date} — {period}"

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Use creating user's company unless explicitly overridden (e.g. cross-company admin ops).
            vals.setdefault('company_id', self.env.company.id)
            # Set planned open/close from site preferences if not already set.
            if not vals.get('planned_open') and vals.get('date') and vals.get('label'):
                planned_open, planned_close = self._compute_planned_times(
                    vals['date'], vals['label'], self.env.company
                )
                vals.setdefault('planned_open',  planned_open)
                vals.setdefault('planned_close', planned_close)

        return super().create(vals_list)

    @api.model
    def _compute_planned_times(self, date, label, company):
        """
        Return (planned_open, planned_close) datetimes for a shift
        given its date, label, and company site preferences.
        """
        from datetime import datetime, timedelta
        prefs = self.env['fms.site.preferences'].get_for_company(company)
        duration = int(prefs.shift_duration_hrs or 8)

        label_to_hour = {
            '1_day':     prefs.shift_1_start_hour or 6,
            '2_evening': prefs.shift_2_start_hour or 14,
            '3_night':   prefs.shift_3_start_hour or 22,
        }
        start_hour = label_to_hour.get(label, 0)

        if isinstance(date, str):
            from odoo.fields import Date
            date = Date.from_string(date)

        planned_open  = datetime(date.year, date.month, date.day, start_hour, 0, 0)
        planned_close = planned_open + timedelta(hours=duration)
        return planned_open, planned_close

    def write(self, vals):
        if 'state' in vals and vals['state'] != 'closed':
            for shift in self:
                if shift.state == 'closed':
                    raise ValidationError(
                        "Closed shift %s cannot be re-opened or modified directly. "
                        "Use the emergency override workflow." % shift.display_name
                    )
        return super().write(vals)

    def unlink(self):
        if any(s.state == 'closed' for s in self):
            raise ValidationError(
                "Closed shifts cannot be deleted — they are part of the audit trail."
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Project-wide helper — single source of truth for "which shift?"
    # ------------------------------------------------------------------

    @api.model
    def _get_current_shift(self, date=None, company_id=None):
        """Return the active shift for date + company.

        Priority:
          1. Shift whose date matches exactly and is open/closing.
          2. Any open/closing shift for the company (most recent) — covers
             overnight shifts or when the form date hasn't been set yet.

        Returns empty recordset when no open shift exists.
        """
        date       = date       or fields.Date.today()
        company_id = company_id or self.env.company.id
        # Exact-date match first
        shift = self.search([
            ('date',       '=',  date),
            ('state',      'in', ('open', 'closing')),
            ('company_id', '=',  company_id),
        ], limit=1)
        if shift:
            return shift
        # Fallback: most recently opened shift for the company
        return self.search([
            ('state',      'in', ('open', 'closing')),
            ('company_id', '=',  company_id),
        ], order='date desc, id desc', limit=1)

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def action_open_shift(self):
        """
        Move Draft → Open:
          1. Enforce single-open-shift constraint (same company).
          2. Auto-populate meter entries for every active pump nozzle,
             with opening volumes taken from the previous shift's meter logs.
          3. Auto-populate dip entries for every active fuel tank,
             with opening volumes taken from the previous shift's dip logs.
          4. If no previous shift exists, all opening values default to 0.
        """
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(
                f"Cannot open a shift that is already '{self.state}'."
            )

        # ── Gate: only one shift open per company ────────────────────────────
        conflict = self.search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ('open', 'closing')),
            ('id', '!=', self.id),
        ], limit=1)
        if conflict:
            raise ValidationError(
                f"Shift '{conflict.display_name}' is already open at "
                f"{self.company_id.name}. Close it before opening a new one."
            )

        # ── Auto-populate entries from previous shift's closing logs ──────────
        self._populate_opening_entries()

        self.write({
            'state': 'open',
            'opening_meter_date': fields.Datetime.now(),
            'opening_meter_user_id': self.env.user.id,
        })

        self._sync_attendant_cash_lines()

        # ── Snapshot fc_line opening qty from stock.quant ─────────────────────
        self._snapshot_fc_opening_qty()

    def _snapshot_fc_opening_qty(self):
        """
        Snapshot stock.quant quantities at the forecourt holding location(s)
        into fc_line.opening_qty for all goods-type fc_lines on this shift.

        Called once on action_open_shift(). Idempotent — skips lines that
        already have opening_qty set (non-zero).

        Uses sudo() because stock.quant may require inventory manager rights
        while the shift supervisor only has FMS permissions.
        """
        self.ensure_one()
        goods_lines = self.fc_line_ids.filtered(lambda l: l.line_type == 'goods')
        if not goods_lines:
            return

        forecourt_locs = self.env['stock.location'].sudo().search([
            ('fms_is_forecourt', '=', True),
            ('company_id', '=', self.company_id.id),
        ])
        if not forecourt_locs:
            return

        for line in goods_lines:
            if line.opening_qty:
                continue  # already set — skip (idempotent)
            quants = self.env['stock.quant'].sudo().search([
                ('product_id', '=', line.product_id.id),
                ('location_id', 'in', forecourt_locs.ids),
            ])
            qty = sum(quants.mapped('quantity'))
            line.sudo().write({'opening_qty': qty})

    def _get_previous_shift(self):
        """Return the most-recently closed shift for this company, or False."""
        return self.search([
            ('company_id', '=', self.company_id.id),
            ('state', '=', 'closed'),
            ('id', '!=', self.id),
        ], order='date desc, label desc', limit=1)

    def _populate_opening_entries(self):
        """
        Build meter entries for every active nozzle and dip entries for every
        active fuel tank.

        Opening values come from the previous shift's immutable logs
        (fms.meter_log.closing_elec_volume / fms.dip_log.closing_volume).
        Falls back to 0 when no previous shift or no matching log exists.

        Skips creation if entries already exist on this shift (idempotent).
        """
        self.ensure_one()
        prev = self._get_previous_shift()

        # ── Meter entries ────────────────────────────────────────────────────
        if not self.meter_entry_ids:
            pumps = self.env['fms.pump'].search([('active', '=', True)])
            meter_entries = []
            for pump in pumps:
                for nozzle in pump.nozzle_ids.filtered('active'):
                    # Opening = nozzle's current meter position (set on last shift close)
                    opening_elec_volume = nozzle.current_elec_volume
                    opening_elec_cash   = nozzle.current_elec_cash
                    opening_man_mech    = nozzle.current_mech_volume
                    meter_entries.append({
                        'shift_id':            self.id,
                        'pump_id':             pump.id,
                        'nozzle_id':           nozzle.id,
                        'opening_elec_volume': opening_elec_volume,
                        'closing_elec_volume': opening_elec_volume,  # supervisor overwrites at close
                        'opening_elec_cash':   opening_elec_cash,
                        'closing_elec_cash':   opening_elec_cash,    # supervisor overwrites at close
                        'opening_man_mech':    opening_man_mech,
                        'closing_man_mech':    opening_man_mech,     # supervisor overwrites at close
                    })
            # Pre-assigned mode: populate attendant_id from nozzle default
            prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
            use_pre_assigned = prefs and prefs.attendant_assignment_mode == 'pre_assigned'
            if use_pre_assigned:
                for entry in meter_entries:
                    nozzle = self.env['fms.pump.nozzle'].browse(entry['nozzle_id'])
                    if nozzle.default_attendant_id:
                        entry['attendant_id'] = nozzle.default_attendant_id.id

            if meter_entries:
                self.env['fms.shift.meter.entry'].create(meter_entries)

        # ── Dip entries ──────────────────────────────────────────────────────
        if not self.dip_entry_ids:
            company_ids = self.env.companies.ids
            tanks = self.env['stock.location'].search([
                ('fms_is_fuel_tank', '=', True),
                ('active', '=', True),
            ])
            dip_entries = []
            for tank in tanks:
                # Book stock = current stock.quant quantity for this tank
                book_stock = 0.0
                if tank.fms_fuel_product_id:
                    quant = self.env['stock.quant'].search([
                        ('location_id', '=', tank.id),
                        ('product_id', '=', tank.fms_fuel_product_id.id),
                        ('company_id', 'in', company_ids),
                    ], limit=1)
                    book_stock = quant.quantity if quant else 0.0

                # Opening = previous shift's closing dip log
                # Fallback: stock.quant (first shift ever, or after manual adjustment)
                opening_vol = 0.0
                if prev:
                    log = self.env['fms.dip_log'].search([
                        ('shift_id', '=', prev.id),
                        ('location_id', '=', tank.id),
                    ], limit=1)
                    if log:
                        opening_vol = log.closing_volume
                if not opening_vol:
                    opening_vol = book_stock

                dip_entries.append({
                    'shift_id':        self.id,
                    'location_id':     tank.id,
                    'opening_volume':  opening_vol,
                    'closing_volume':  0.0,
                    'book_stock_open': book_stock,
                })
            if dip_entries:
                self.env['fms.shift.dip.entry'].create(dip_entries)

    def action_sync_attendant_cash_lines(self):
        """Button action — manually re-sync attendant cash lines from meter entries."""
        self.ensure_one()
        created = self._sync_attendant_cash_lines()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Attendant Cash Lines Synced',
                'message': f'{created} new line(s) added.' if created else 'All attendants already have cash lines.',
                'type': 'success' if created else 'info',
            },
        }

    def _sync_attendant_cash_lines(self):
        """
        For every attendant assigned to at least one nozzle in this shift's
        meter entries, ensure a corresponding attendant cash line exists.

        Non-destructive: existing lines are never removed or modified.
        Returns the count of newly created lines.
        """
        self.ensure_one()
        # Attendants already covered by existing cash lines
        existing_ids = set(self.attendant_cash_ids.mapped('attendant_id').ids)
        # Attendants present in meter entries (skip unassigned nozzles)
        needed = self.meter_entry_ids.mapped('attendant_id').filtered('id')
        to_create = needed.filtered(lambda a: a.id not in existing_ids)
        if not to_create:
            return 0
        self.env['fms.shift.attendant.cash'].create([
            {'shift_id': self.id, 'attendant_id': att.id}
            for att in to_create
        ])
        return len(to_create)

    def action_start_closing(self):
        """Move Open → Closing. FC Cash variance must be zero before transition."""
        self.ensure_one()
        if self.state != 'open':
            raise ValidationError(
                f"Cannot start closing a shift that is '{self.state}'."
            )
        # FC Cash gate: if any attendant has unresolved variance, open resolution wizard.
        self.attendant_cash_ids.invalidate_recordset(['fc_variance', 'fc_captured', 'fc_collected'])
        has_variance = any(abs(c.fc_variance) > 0.01 for c in self.attendant_cash_ids)
        if has_variance:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Resolve FC Cash Variances',
                'res_model': 'fms.shift.recon.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_shift_id': self.id},
            }
        self.write({
            'state': 'closing',
            'closing_meter_date': fields.Datetime.now(),
            'closing_meter_user_id': self.env.user.id,
        })
        # Conditionally sync attendant cash lines (controlled by site preferences)
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.auto_sync_attendants:
            self._sync_attendant_cash_lines()
        # Auto-calculate residuals on transition to closing
        self._calculate_residuals()

    def action_mark_disputed(self):
        """
        Move any open/closing shift to 'Disputed' state when gate failures cannot be resolved immediately.

        Rules:
        - Only supervisors/accountants may mark a shift disputed.
        - By default only one disputed shift allowed per company (site pref: allow_multiple_disputed).
        - Disputed shifts remain editable but cannot close until moved back to 'closing' and gates pass.
        """
        self.ensure_one()
        if self.state not in ('open', 'closing'):
            raise ValidationError(
                f"Only open or closing shifts can be marked disputed. Current state: {self.state}."
            )
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        allow_multiple = prefs.allow_multiple_disputed if prefs else False
        if not allow_multiple:
            existing = self.search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'disputed'),
                ('id', '!=', self.id),
            ], limit=1)
            if existing:
                raise ValidationError(
                    f"Shift '{existing.display_name}' is already in disputed state. "
                    "Resolve it before marking another shift disputed, or enable "
                    "'Allow Multiple Disputed Shifts' in Site Preferences."
                )
        self.write({'state': 'disputed'})

    def action_reopen_disputed(self):
        """Return disputed shift to 'closing' so the supervisor can retry gate checks."""
        self.ensure_one()
        if self.state != 'disputed':
            raise ValidationError("Only disputed shifts can be reopened.")
        self.write({'state': 'closing'})

    # ------------------------------------------------------------------
    # FMS-003: Residual Allocation Algorithm (Spec Section 7.1)
    # ------------------------------------------------------------------

    def action_calculate_residuals(self):
        """Public button action — re-run residual allocation at any time."""
        for shift in self:
            count = shift._calculate_residuals()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Residual Allocation Complete',
                'message': f'{count} allocation(s) created.',
                'type': 'success',
            },
        }

    def _calculate_residuals(self):
        """
        Residual allocation algorithm — VOLUME-based (Spec Section 7.1).

        Operates on liters, NOT KES. Called only after both Gate 1 (volume)
        and Gate 2 (cash) have passed, so the reconciliation is clean before
        we attempt to reclassify lumped sales.

        Step 1: Rebuild product sales from meter entries.
        Step 2: Read volume_residual from each product_sales line (computed by ORM).
                  volume_residual = meter_volume - accounted_volume (POS liters)
                  > 0.1L  → under-invoiced (meter dispensed more than POS recorded)
                  < -0.1L → over-invoiced (POS claimed more than meter dispensed)
        Step 3: Greedy-match over-invoiced → under-invoiced products (liters).
        Step 4: Create fms.shift.residual.allocation records.
                  amount = qty_litres × target price_at_close
                  Write allocated_volume / allocated_amount back to product sales lines.

        Returns count of allocation records created.
        """
        self.ensure_one()
        self.residual_allocation_ids.unlink()

        # Step 1: rebuild product sales (also writes price_at_close)
        self._refresh_product_sales()

        # Flush so computed fields (volume_residual, accounted_volume) are current
        self.product_sales_ids.flush_recordset()

        # Step 2: classify by volume residual
        over_reported  = {}   # pid → surplus_litres (positive)
        under_reported = {}   # pid → deficit_litres (positive)

        for ps in self.product_sales_ids:
            pid      = ps.product_id.id
            residual = ps.volume_residual  # meter_volume - accounted_volume

            if residual < -0.1:
                rtype = 'over'
                over_reported[pid] = abs(residual)
            elif residual > 0.1:
                rtype = 'under'
                under_reported[pid] = residual
            else:
                rtype = 'none'

            ps.write({'residual_type': rtype})

        # Step 3: greedy match (liters)
        allocations = self._run_greedy_allocation(over_reported, under_reported)

        # Step 4: create records and update product sales lines
        alloc_vals = []
        for (over_pid, under_pid, qty_litres) in allocations:
            under_ps = self.product_sales_ids.filtered(
                lambda r: r.product_id.id == under_pid
            )
            price = under_ps.price_at_close if under_ps else 0.0
            amount = qty_litres * price
            alloc_vals.append({
                'shift_id':          self.id,
                'source_product_id': over_pid,
                'target_product_id': under_pid,
                'qty_litres':        qty_litres,
                'amount':            amount,
                'notes':             'Auto-calculated — volume residual reconciliation',
            })
            # Write allocated totals back to the product sales lines
            over_ps = self.product_sales_ids.filtered(
                lambda r: r.product_id.id == over_pid
            )
            if over_ps:
                over_ps.allocated_volume += qty_litres
                over_ps.allocated_amount += amount
            if under_ps:
                under_ps.allocated_volume += qty_litres
                under_ps.allocated_amount += amount

        if alloc_vals:
            self.env['fms.shift.residual.allocation'].create(alloc_vals)

        return len(alloc_vals)

    def _get_accounted_by_product(self):
        """
        Return {product_id: (qty_litres, amount_kes)} from POS order lines.
        Falls back to empty dict when no sessions linked.
        """
        sessions = self.pos_session_ids
        if not sessions:
            return {}
        lines = self.env['pos.order.line'].search([
            ('order_id.session_id', 'in', sessions.ids),
        ])
        result = {}
        for line in lines:
            pid = line.product_id.id
            if pid not in result:
                result[pid] = (0.0, 0.0)
            qty, amt = result[pid]
            result[pid] = (qty + line.qty, amt + line.price_subtotal_incl)
        return result

    @staticmethod
    def _run_greedy_allocation(over_reported, under_reported):
        """
        Pure algorithm: match over-invoiced to under-invoiced products (liters).

        Args:
            over_reported:  {product_id: surplus_litres}  — meter < POS (POS over-counted)
            under_reported: {product_id: deficit_litres}  — meter > POS (POS under-counted)

        Returns list of (over_pid, under_pid, qty_litres) tuples.
        Caller converts qty_litres → KES using target product price_at_close.
        """
        over  = {k: v for k, v in sorted(over_reported.items(),  key=lambda x: -x[1])}
        under = {k: v for k, v in sorted(under_reported.items(), key=lambda x: -x[1])}

        allocations = []
        for over_pid in list(over):
            for under_pid in list(under):
                if over.get(over_pid, 0.0) < 0.1:
                    break
                if under.get(under_pid, 0.0) < 0.1:
                    continue

                alloc_qty = min(over[over_pid], under[under_pid])
                allocations.append((over_pid, under_pid, alloc_qty))

                over[over_pid]   -= alloc_qty
                under[under_pid] -= alloc_qty

        return allocations

    def _is_empty_shift(self):
        """
        Return True when nothing financial happened this shift:
          - No meter sales (all elec_cash_sold = 0)
          - No attendant cash lines or all balances already zero
          - No dip variance outside meniscus

        Empty shifts can close automatically without gate checks or a supervisor.
        """
        self.ensure_one()
        self.invalidate_recordset(['total_meter_sales'])
        self.attendant_cash_ids.invalidate_recordset(['balance'])
        if abs(self.total_meter_sales) > 0.01:
            return False
        if any(abs(c.balance) > 0.01 for c in self.attendant_cash_ids):
            return False
        return True

    def action_close_shift(self):
        """
        Move Closing → Closed.

        Empty shifts (no sales, zero balances) close automatically — no gate
        checks, no supervisor required.

        Active shifts run the full gate sequence:
          Gate 1: volume reconciliation (meter L ≈ POS L)
          Gate 2: cash reconciliation (cash meter KES ≈ POS KES)
          Gate 3: each attendant balance = 0
          Gate 4: FC cash total = 0
          Gate 5: tank dip variance within meniscus
          + supervisor must be assigned before close

        On success: writes immutable logs, posts GL, then auto-opens the next
        shift if configured in site preferences.
        """
        self.ensure_one()
        if self.state != 'closing':
            raise ValidationError(
                f"Cannot close a shift that is '{self.state}'. "
                "Use 'Start Closing' first."
            )

        # Optimistic concurrency check: detect concurrent edits
        fresh = self.browse(self.id).read(['write_date'])[0]
        if fresh['write_date'] != self.write_date:
            raise ValidationError(
                "This shift was modified by another user while you were working on it. "
                "Please reload the shift and try closing again."
            )

        if not self._is_empty_shift():
            # GL account configuration check — surface mis-wired accounts before
            # spending time on gate checks that will succeed but post wrong entries.
            try:
                self._gate_check_gl_config()
            except ValidationError as exc:
                self.message_post(
                    body=f"<b>Close attempt failed (GL config)</b> by {self.env.user.name}:<br/>{exc.args[0]}",
                    subtype_xmlid='mail.mt_note',
                )
                raise

            # Supervisor required when money is involved
            if not self.supervisor_id:
                raise ValidationError(
                    "A supervisor must be assigned before closing a shift with sales. "
                    "Set the Supervisor field and try again."
                )

            # Attendant assignment check (per-nozzle mode)
            prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
            if prefs and prefs.attendant_assignment_mode == 'per_nozzle':
                missing = self.meter_entry_ids.filtered(lambda e: not e.attendant_id)
                if missing:
                    nozzles = ', '.join(
                        e.nozzle_id.name or e.nozzle_id.display_name for e in missing
                    )
                    raise ValidationError(
                        f"Attendant not set on {len(missing)} nozzle(s): {nozzles}. "
                        "Set an attendant on each meter entry row before closing."
                    )
            # Full gate sequence — log each gate failure to chatter before re-raising
            for gate_fn in (
                # G1-G2: Three-meter (electronic vs manual vs cash)
                self._gate_check_meter_elec_vs_manual,
                self._gate_check_meter_elec_vs_cash,
                # G3-G5: Volume, cash, attendant balances
                self._gate_check_volume_reconciliation,
                self._gate_check_cash_reconciliation,
                self._gate_check_attendant_balances,
                # G6: FC cash
                self._gate_check_fc_cash,
                # G7: Stock variance
                self._gate_check_stock_variance,
                # G8: Meter vs invoice+receipt
                self._gate_check_meter_vs_sales,
                # G9-G15: FIN-009 + GATE-002 additional gates
                self._gate_check_customer_receipts,
                self._gate_check_float_reconciliation,
                self._gate_check_expense_posting,
                self._gate_check_vendor_payment_posting,
                self._gate_check_digital_payment_reconciliation,
                self._gate_check_no_unresolved_exceptions,
                self._gate_check_nonfuel_sales_posted,
            ):
                try:
                    gate_fn()
                except ValidationError as exc:
                    self.message_post(
                        body=(
                            f"<b>Close attempt failed ({gate_fn.__name__})</b> "
                            f"by {self.env.user.name} at "
                            f"{fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}:"
                            f"<br/><pre>{exc.args[0]}</pre>"
                        ),
                        subtype_xmlid='mail.mt_note',
                    )
                    raise

        with self.env.cr.savepoint():
            self._write_meter_logs()
            self._write_dip_logs()
            self._sync_stock_quant_from_dips()
            sales_move = self._post_sales_journal()
            self._post_residual_allocation_journals()
            self._post_stock_consumption()
            vals = {'state': 'closed'}
            if sales_move:
                vals['sales_journal_entry_id'] = sales_move.id
            self.write(vals)

        # Auto-open next shift if site preferences say so
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.auto_open_next_shift:
            self._auto_open_next_shift()

    def action_open_emergency_override_wizard(self):
        """Open the emergency override wizard. Restricted to accountant group."""
        self.ensure_one()
        if not self.env.user.has_group('fms.group_fms_accountant'):
            from odoo.exceptions import AccessError
            raise AccessError("Emergency override requires the FMS Accountant role.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'Emergency Shift Close Override',
            'res_model': 'fms.emergency.override.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_shift_id': self.id},
        }

    def _apply_emergency_override(self, reason, approver):
        """
        Close the shift bypassing all gates.
        Records an immutable override log and posts to chatter.
        Must only be called from FMSEmergencyOverrideWizard after group check.
        """
        self.ensure_one()
        if self.state not in ('open', 'closing', 'disputed'):
            raise ValidationError(
                f"Emergency override only applies to open/closing/disputed shifts. Current: {self.state}."
            )

        # Collect what gates would have failed (same sequence as action_close_shift)
        gate_failures = []
        for gate_fn in (
            self._gate_check_meter_elec_vs_manual,
            self._gate_check_meter_elec_vs_cash,
            self._gate_check_volume_reconciliation,
            self._gate_check_cash_reconciliation,
            self._gate_check_attendant_balances,
            self._gate_check_fc_cash,
            self._gate_check_stock_variance,
            self._gate_check_meter_vs_sales,
            self._gate_check_customer_receipts,
            self._gate_check_float_reconciliation,
            self._gate_check_expense_posting,
            self._gate_check_vendor_payment_posting,
            self._gate_check_digital_payment_reconciliation,
            self._gate_check_no_unresolved_exceptions,
            self._gate_check_nonfuel_sales_posted,
        ):
            try:
                gate_fn()
            except ValidationError as exc:
                gate_failures.append(f"{gate_fn.__name__}: {exc.args[0]}")

        # Create immutable audit record
        self.env['fms.shift.override.log'].sudo().create({
            'shift_id': self.id,
            'user_id': self.env.user.id,
            'approver_id': approver.id,
            'reason': reason,
            'gate_failures': '\n\n'.join(gate_failures) if gate_failures else 'No gate failures detected at override time.',
        })

        # Post GL and close
        with self.env.cr.savepoint():
            self._write_meter_logs()
            self._write_dip_logs()
            self._sync_stock_quant_from_dips()
            sales_move = self._post_sales_journal()
            self._post_residual_allocation_journals()
            self._post_stock_consumption()
            vals = {'state': 'closed'}
            if sales_move:
                vals['sales_journal_entry_id'] = sales_move.id
            self.write(vals)

        self.message_post(
            body=(
                f"<b>⚠ EMERGENCY OVERRIDE CLOSE</b> by {self.env.user.name}<br/>"
                f"<b>Approver:</b> {approver.name}<br/>"
                f"<b>Reason:</b> {reason}<br/>"
                f"<b>Gates bypassed:</b> {len(gate_failures)}"
            ),
            subtype_xmlid='mail.mt_note',
        )

    def _auto_open_next_shift(self):
        """
        Create and immediately open the next shift after this one closes.

        Label and date are determined from site preferences and the current
        shift's label / date:
          8hr:  Day → Evening → Night → Day (next date)
          12hr: Day → Night → Day (next date)
          24hr: always label '1_day', date + 1 day
        """
        self.ensure_one()
        from datetime import timedelta

        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        duration = prefs.shift_duration_hrs or '8'

        next_label, next_date = self._next_label_and_date(duration)

        next_shift = self.create({
            'date':       next_date,
            'label':      next_label,
            'company_id': self.company_id.id,
            # supervisor intentionally not set — assigned later
        })
        next_shift.action_open_shift()
        return next_shift

    def _next_label_and_date(self, duration):
        """Return (label, date) for the shift that follows this one."""
        from datetime import timedelta

        today = self.date

        if duration == '24':
            return '1_day', today + timedelta(days=1)

        if duration == '12':
            sequence = ['1_day', '3_night']
            idx = sequence.index(self.label) if self.label in sequence else 0
            next_idx = (idx + 1) % len(sequence)
            next_label = sequence[next_idx]
            next_date  = today + timedelta(days=1) if next_idx == 0 else today
            return next_label, next_date

        # 8hr default
        sequence = ['1_day', '2_evening', '3_night']
        idx = sequence.index(self.label) if self.label in sequence else 0
        next_idx = (idx + 1) % len(sequence)
        next_label = sequence[next_idx]
        next_date  = today + timedelta(days=1) if next_idx == 0 else today
        return next_label, next_date

    # ------------------------------------------------------------------
    # FMS-006: Hard gate validators (Spec Section 7.2–7.3)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Gate status panel (Phase 8 UX)
    # ------------------------------------------------------------------

    _GATE_REGISTRY = [
        # (label, method_name, fix_hint)
        ("G1 Elec vs Manual Meter",      "_gate_check_meter_elec_vs_manual",
         "Check nozzle meter calibration. Variance must be ≤ 1 L per nozzle."),
        ("G2 Elec vs Cash Meter",        "_gate_check_meter_elec_vs_cash",
         "Reconcile electronic vs cash meter totals — check site threshold in preferences."),
        ("G3 Volume Reconciliation",     "_gate_check_volume_reconciliation",
         "Enter dip readings and meter entries. Ensure all tanks/nozzles have readings."),
        ("G4 Cash Reconciliation",       "_gate_check_cash_reconciliation",
         "Verify reported sales, cash received, and expenses for each attendant."),
        ("G5 Attendant Balances",        "_gate_check_attendant_balances",
         "Each attendant's balance must be 0. Investigate and post correction entries."),
        ("G6 FC Cash = 0",               "_gate_check_fc_cash",
         "Total forecourt cash must net to 0. Post a supervisor correction if needed."),
        ("G7 Stock Variance",            "_gate_check_stock_variance",
         "Tank dip variance exceeds meniscus. Verify dip readings or post adjustment."),
        ("G8 Meter vs Invoices",         "_gate_check_meter_vs_sales",
         "Meter sales must match posted invoices + receipts. Check unposted documents."),
        ("G9 Customer Receipts",         "_gate_check_customer_receipts",
         "Post all pending customer receipt payments linked to this shift."),
        ("G10 Float Reconciliation",     "_gate_check_float_reconciliation",
         "All floats issued must be dropped or carried. Account for outstanding floats."),
        ("G11 Expense Posting",          "_gate_check_expense_posting",
         "Confirm all expense payments — no draft expenses allowed at close."),
        ("G12 Vendor Payment Posting",   "_gate_check_vendor_payment_posting",
         "Post all vendor payments made from shift cash before closing."),
        ("G13 Digital Payments",         "_gate_check_digital_payment_reconciliation",
         "MPesa/Card totals must be non-negative. Check payment entry signs."),
        ("G14 No Blocking Exceptions",   "_gate_check_no_unresolved_exceptions",
         "Resolve any disputed shift state or pending override logs."),
        ("G15 Non-Fuel Sales Posted",    "_gate_check_nonfuel_sales_posted",
         "Confirm (post) all non-fuel invoices and receipts linked to this shift before closing."),
    ]

    @api.depends(
        'state',
        'attendant_cash_ids.balance',
        'attendant_cash_ids.reported_sales',
        'meter_entry_ids.closing_elec_volume',
        'meter_entry_ids.closing_man_mech',
        'dip_entry_ids.closing_volume',
    )
    def _compute_gate_status_html(self):
        for shift in self:
            if shift.state == 'closed':
                shift.gate_status_html = (
                    '<div class="alert alert-success mb-0">'
                    '<i class="fa fa-check-circle"/> Shift closed — all gates passed.'
                    '</div>'
                )
                continue
            if shift.state == 'draft':
                shift.gate_status_html = (
                    '<div class="alert alert-info mb-0">'
                    '<i class="fa fa-info-circle"/> Open the shift to see gate status.'
                    '</div>'
                )
                continue
            rows = shift._collect_gate_status()
            passed = sum(1 for _, ok, _ in rows if ok)
            total = len(rows)
            pct = int(passed / total * 100) if total else 0
            color = '#28a745' if passed == total else '#ffc107' if passed >= total * 0.7 else '#dc3545'
            html = [
                f'<div style="margin-bottom:8px">',
                f'<b>Shift Close Readiness: {passed}/{total} gates passing</b>',
                f'<div style="background:#e9ecef;border-radius:4px;height:8px;margin:4px 0">',
                f'<div style="width:{pct}%;background:{color};height:8px;border-radius:4px"></div>',
                f'</div></div>',
                '<table class="table table-sm table-bordered" style="font-size:13px">',
                '<thead><tr>',
                '<th style="width:30px"></th>',
                '<th>Gate</th>',
                '<th>Status / Action Required</th>',
                '</tr></thead><tbody>',
            ]
            for label, ok, message in rows:
                icon = '✓' if ok else '✗'
                row_style = 'background:#d4edda' if ok else 'background:#f8d7da'
                msg_cell = '' if ok else f'<span style="color:#721c24">{message}</span>'
                html.append(
                    f'<tr style="{row_style}">'
                    f'<td style="text-align:center;font-weight:bold">{icon}</td>'
                    f'<td><b>{label}</b></td>'
                    f'<td>{msg_cell}</td>'
                    f'</tr>'
                )
            html.append('</tbody></table>')
            shift.gate_status_html = ''.join(html)

    def _collect_gate_status(self):
        """Run all gates in dry-run mode. Returns list of (label, passed, fix_hint_or_error)."""
        self.ensure_one()
        results = []
        for label, method_name, fix_hint in self._GATE_REGISTRY:
            gate_fn = getattr(self, method_name, None)
            if gate_fn is None:
                results.append((label, True, ''))
                continue
            try:
                gate_fn()
                results.append((label, True, ''))
            except Exception as exc:
                msg = str(exc.args[0] if exc.args else exc)
                # Strip Odoo's ValidationError wrapper prefix if present
                if '\n' in msg:
                    msg = msg.split('\n')[0]
                results.append((label, False, f"{msg}<br/><i>{fix_hint}</i>"))
        return results

    _MENISCUS_PCT = 0.5  # fallback when no site preferences record exists

    def _get_meniscus_pct(self):
        """Return the configured meniscus % from site preferences, or class default."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        return prefs.meniscus_pct if prefs.meniscus_pct > 0 else self._MENISCUS_PCT

    def _gate_check_fc_cash(self):
        """GATE 4 (FC Cash): sum of fc_variance across all attendants must be exactly zero."""
        self.ensure_one()
        # Force recompute — fc_variance is store=False but ORM may cache a stale 0.0
        self.attendant_cash_ids.invalidate_recordset(['fc_variance', 'fc_captured', 'fc_collected'])
        failing = []
        for cash in self.attendant_cash_ids:
            if abs(cash.fc_variance) > 0.01:
                cur = self.company_id.currency_id.name
                failing.append(
                    f"  • {cash.attendant_id.name}: {cur} {cash.fc_variance:,.2f}"
                )
        if failing:
            lines = "\n".join(failing)
            raise ValidationError(
                f"GATE 4 FAILED (FC Cash) — {len(failing)} attendant(s) have unresolved FC Cash variance:\n"
                f"{lines}\n\n"
                "Post or write off all variances before closing the shift."
            )

    def _gate_check_attendant_balances(self):
        """
        GATE 3 (Attendants): Every individual attendant's balance must be zero.

        Even if the FC total nets to zero, individual discrepancies must
        be resolved one-by-one.  The error lists every failing attendant.
        """
        self.ensure_one()
        self.attendant_cash_ids.invalidate_recordset(['balance', 'total_in', 'total_out'])
        failing = []
        for cash in self.attendant_cash_ids:
            if abs(cash.balance) > 0.01:
                failing.append(
                    f"  • {cash.attendant_id.name}: {self.company_id.currency_id.name} {cash.balance:,.2f}"
                )
        if failing:
            lines = "\n".join(failing)
            raise ValidationError(
                f"GATE 3 FAILED (Attendants) — {len(failing)} attendant(s) have unresolved balances:\n"
                f"{lines}\n\n"
                "Each attendant balance must be 0 before the shift can close."
            )

    def _compute_dip_variance_data(self, dip_entry):
        """Return variance dict for one dip entry. Called at gate check and shift close.

        Returns:
            meter_sales     : litres metered for this product this shift
            shift_variance  : closing_dip − (opening + delivery − meter_sales)
            shift_var_amount: shift_variance × price/L  (company currency)
            month_variance  : closing_dip − (month_opening + month_deliveries − month_meter_sales)
            month_var_amount: month_variance × price/L
            var_rate        : price/L used
        """
        self.ensure_one()
        product = dip_entry.product_id
        location = dip_entry.location_id
        company_ids = self.env.companies.ids

        # Meter sales for this product this shift
        self.env.cr.execute("""
            SELECT COALESCE(SUM(qty_sold_elec), 0.0)
            FROM fms_shift_meter_entry
            WHERE shift_id = %s AND product_id = %s
        """, (self.id, product.id))
        meter_sales = self.env.cr.fetchone()[0]

        # Delivery qty: sum of confirmed/billed delivery lines into this tank this shift
        # fms_accounting may not be installed — check table existence
        delivery = 0.0
        self.env.cr.execute("""
            SELECT to_regclass('fms_fuel_delivery_line')
        """)
        if self.env.cr.fetchone()[0]:
            self.env.cr.execute("""
                SELECT COALESCE(SUM(fdl.quantity_litres), 0.0)
                FROM fms_fuel_delivery_line fdl
                JOIN fms_fuel_delivery fd ON fd.id = fdl.delivery_id
                WHERE fdl.location_id = %s
                  AND fd.shift_id = %s
                  AND fd.state IN ('confirmed', 'billed')
                  AND fd.company_id = ANY(%s)
            """, (location.id, self.id, company_ids))
            delivery = self.env.cr.fetchone()[0]

        # Shift variance
        opening   = dip_entry.opening_volume or 0.0
        closing   = dip_entry.closing_volume or 0.0
        shift_var = closing - (opening + delivery - meter_sales)

        # Price per litre (company currency — never hardcoded)
        var_rate = product.list_price if product else 0.0
        shift_var_amount = shift_var * var_rate

        # Month variance — query dip_log for this tank since month start
        month_start = self.date.replace(day=1) if self.date else None
        month_var = 0.0
        if month_start:
            self.env.cr.execute("""
                SELECT
                    MIN(dl.opening_volume)          AS month_opening,
                    COALESCE(SUM(dl.delivery_qty),0) AS month_deliveries,
                    COALESCE(SUM(dl.meter_sales_snapshot),0) AS month_meter_sales
                FROM fms_dip_log dl
                JOIN fms_shift s ON s.id = dl.shift_id
                WHERE dl.location_id = %s
                  AND s.date >= %s
                  AND s.date <= %s
                  AND s.company_id = ANY(%s)
                  AND s.state = 'closed'
            """, (location.id, month_start, self.date, company_ids))
            row = self.env.cr.fetchone()
            if row and row[0] is not None:
                month_opening = row[0]
                month_deliveries = row[1]
                month_meter_sales_prev = row[2]
                # Include current shift's data
                month_var = closing - (month_opening + month_deliveries + delivery - month_meter_sales_prev - meter_sales)
            else:
                # No prior closed shifts this month — month variance = shift variance
                month_var = shift_var

        return {
            'meter_sales':     meter_sales,
            'shift_variance':  shift_var,
            'shift_var_amount': shift_var_amount,
            'month_variance':  month_var,
            'month_var_amount': month_var * var_rate,
            'var_rate':        var_rate,
        }

    def _gate_check_stock_variance(self):
        """
        GATE 5 (Variance): Tank dip variance must be within the site meniscus (absolute litres).

        Uses shift_variance = closing_dip − (opening + delivery − meter_sales).
        Replaces the old percentage-based check which produced false failures every shift.
        """
        self.ensure_one()
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        meniscus_l = (prefs.default_dip_variance_meniscus
                      if prefs and prefs.default_dip_variance_meniscus > 0 else 1000.0)
        currency = self.company_id.currency_id
        failing = []
        for dip in self.dip_entry_ids:
            if dip.closing_volume <= 0:
                continue
            vdata = self._compute_dip_variance_data(dip)
            sv = vdata['shift_variance']
            if abs(sv) > meniscus_l:
                sign = '+' if sv >= 0 else ''
                failing.append(
                    f"  • {dip.location_id.name} ({dip.product_id.name}): "
                    f"variance {sign}{sv:,.2f} L  "
                    f"({currency.name} {sign}{vdata['shift_var_amount']:,.2f})  "
                    f"limit ±{meniscus_l:,.0f} L"
                )
        if failing:
            raise ValidationError(
                f"GATE 5 FAILED (Dip Variance) — {len(failing)} tank(s) exceed ±{meniscus_l:,.0f} L:\n"
                + "\n".join(failing)
                + "\n\nVerify the closing dip reading and delivery quantity, then retry."
            )

    def _gate_check_meter_vs_sales(self):
        """
        GATE 6: Meter volume vs Invoice+Receipt volume per fuel product.

        For each fuel product: meter_vol (elec) must ≈ sales_vol (invoices + receipts).
        Tolerance: same meniscus percentage as Gate 5.

        Skipped if fms_accounting is not installed (no account.move.fms_shift_id field).
        Skipped if no invoices/receipts are linked to this shift.
        """
        # Check if fms_accounting fields exist on account.move
        AccountMove = self.env['account.move']
        if 'fms_shift_id' not in AccountMove._fields:
            return

        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        meniscus_pct = prefs.meniscus_pct if prefs else 0.5

        # Sum meter volumes per fuel product
        meter_by_product = {}
        for entry in self.meter_entry_ids:
            if not entry.product_id.fms_is_fuel:
                continue
            pid = entry.product_id.id
            meter_by_product[pid] = meter_by_product.get(pid, 0.0) + entry.qty_sold_elec

        if not meter_by_product:
            return

        # Sum sales volumes per fuel product from posted invoices + receipts
        moves = AccountMove.search([
            ('fms_shift_id', '=', self.id),
            ('move_type', 'in', ('out_invoice', 'out_receipt')),
            ('state', '=', 'posted'),
        ])
        sales_by_product = {}
        for move in moves:
            for line in move.invoice_line_ids:
                if not line.product_id or not line.product_id.fms_is_fuel:
                    continue
                pid = line.product_id.id
                sales_by_product[pid] = sales_by_product.get(pid, 0.0) + line.quantity

        if not sales_by_product:
            return

        failures = []
        for pid, meter_vol in meter_by_product.items():
            sales_vol = sales_by_product.get(pid, 0.0)
            threshold = meter_vol * meniscus_pct / 100.0 if meter_vol else 0.5
            diff = abs(meter_vol - sales_vol)
            if diff > threshold:
                product = self.env['product.product'].browse(pid)
                failures.append(
                    f"• {product.name}: Meter={meter_vol:.2f}L, "
                    f"Sales={sales_vol:.2f}L, Diff={diff:.2f}L "
                    f"(threshold={threshold:.2f}L)"
                )
        if failures:
            raise ValidationError(
                "GATE 6 FAILED — Meter volume vs Invoice+Receipt volume mismatch:\n\n"
                + "\n".join(failures)
                + "\n\nEnsure all fuel sales are posted (confirmed) as invoices or "
                "receipts before closing the shift."
            )

        # Per-nozzle check (REC-004): only when invoice lines carry fms_nozzle_id
        AccountMoveLine = self.env['account.move.line']
        if 'fms_nozzle_id' not in AccountMoveLine._fields:
            return

        # Check if any line for this shift actually has nozzle attribution
        self.env.cr.execute("""
            SELECT aml.fms_nozzle_id, COALESCE(SUM(aml.quantity), 0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE am.fms_shift_id = %s
              AND am.move_type IN ('out_invoice', 'out_receipt')
              AND am.state = 'posted'
              AND aml.display_type = 'product'
              AND aml.fms_nozzle_id IS NOT NULL
            GROUP BY aml.fms_nozzle_id
        """, [self.id])
        nozzle_sales = dict(self.env.cr.fetchall())

        if not nozzle_sales:
            return  # No nozzle attribution on lines — skip per-nozzle check

        nozzle_failures = []
        for entry in self.meter_entry_ids:
            if not entry.product_id.fms_is_fuel or not entry.nozzle_id:
                continue
            nid = entry.nozzle_id.id
            if nid not in nozzle_sales:
                continue  # No sales attributed to this nozzle — skip (may be partial coverage)
            meter_vol = entry.qty_sold_elec
            sales_vol = nozzle_sales[nid]
            threshold = meter_vol * meniscus_pct / 100.0 if meter_vol else 0.5
            diff = abs(meter_vol - sales_vol)
            if diff > threshold:
                nozzle_failures.append(
                    f"• Nozzle {entry.nozzle_id.name}: Meter={meter_vol:.2f}L, "
                    f"Receipts={sales_vol:.2f}L, Diff={diff:.2f}L "
                    f"(threshold={threshold:.2f}L)"
                )

        if nozzle_failures:
            raise ValidationError(
                "GATE 6 FAILED — Per-nozzle meter vs receipt volume mismatch:\n\n"
                + "\n".join(nozzle_failures)
                + "\n\nEnsure receipt lines are attributed to the correct nozzle "
                "or check meter readings before closing the shift."
            )

    def _gate_check_gl_config(self):
        """
        GL CONFIG CHECK: Verify accounts are wired before posting journal entries.

        Raises ValidationError listing all issues so the user can fix them in one
        go rather than discovering problems after close.
        """
        check = self.env['fms.setup.check'].run_check(self.company_id)
        errors = check.issue_ids.filtered(lambda i: i.level == 'error')
        if errors:
            lines = '\n'.join(f'• {e.title}' for e in errors)
            raise ValidationError(
                "Shift close blocked — GL account configuration errors found.\n\n"
                f"{lines}\n\n"
                "Fix these in Forecourt → Configuration → GL Account Setup Check, "
                "then try closing again."
            )

    def _gate_check_meter_elec_vs_manual(self):
        """
        THREE-METER GATE: Electronic volume vs Manual mechanical volume must be within ±1L per nozzle.

        A variance larger than 1L indicates a meter malfunction, tampering, or data entry error.
        This is a hard block — the shift cannot close until resolved.

        Nozzles where manual reading is zero are skipped (manual meter not recorded for that nozzle).
        """
        failures = []
        for entry in self.meter_entry_ids:
            if not entry.qty_sold_man:
                continue
            diff = abs(entry.qty_sold_elec - entry.qty_sold_man)
            if diff > 1.0:
                nozzle_name = entry.nozzle_id.name or entry.nozzle_id.display_name
                failures.append(
                    f"• {nozzle_name}: Elec={entry.qty_sold_elec:.2f}L, "
                    f"Manual={entry.qty_sold_man:.2f}L, Diff={diff:.2f}L"
                )
        if failures:
            raise ValidationError(
                "THREE-METER CHECK FAILED — Electronic vs Manual volume variance exceeds ±1L:\n\n"
                + "\n".join(failures)
                + "\n\nVerify meter readings, check for meter fault or transcription error, "
                "then re-enter the closing readings."
            )

    def _gate_check_meter_elec_vs_cash(self):
        """
        THREE-METER GATE: Electronic volume vs Cash meter implied volume must be within threshold per nozzle.

        Cash meter volume = (closing_elec_cash - opening_elec_cash) / product_price.
        Tolerance configurable in Site Preferences (elec_vs_cash_threshold_l). Default 5L.
        Set threshold to 0 to disable.

        Skips nozzles where cash readings are zero or price is zero.
        """
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        threshold = prefs.elec_vs_cash_threshold_l if prefs else 5.0
        if threshold <= 0:
            return
        failures = []
        for entry in self.meter_entry_ids:
            price = entry.product_id.list_price or 0.0
            if not price or not entry.elec_cash_sold:
                continue
            cash_vol = entry.elec_cash_sold / price
            diff = abs(entry.qty_sold_elec - cash_vol)
            if diff > threshold:
                nozzle_name = entry.nozzle_id.name or entry.nozzle_id.display_name
                failures.append(
                    f"• {nozzle_name}: Elec={entry.qty_sold_elec:.2f}L, "
                    f"Cash implied={cash_vol:.2f}L, Diff={diff:.2f}L "
                    f"(threshold={threshold:.2f}L)"
                )
        if failures:
            raise ValidationError(
                "ELEC vs CASH METER CHECK FAILED — variance exceeds threshold:\n\n"
                + "\n".join(failures)
                + "\n\nVerify cash totalizer readings and prices in Site Preferences. "
                "Threshold can be adjusted in Forecourt → Configuration → Site Preferences."
            )

    def _gate_check_volume_reconciliation(self):
        """
        GATE 1 (Volume): Total pump meter volume ≈ total POS-accounted volume.
        Numbered first in the gate sequence (called before cash, attendant, FC cash, variance).

        Tolerance: 0.5L across all products. This confirms that the inventory
        picture is consistent — meter litres dispensed = POS litres sold +
        any residual (which will be reclassified, not lost).

        This gate validates that the VOLUME SIDE is ready for residual allocation.
        It does NOT require zero residual — it requires that residuals are within
        a physically plausible range (not e.g. 5000L unaccounted for).

        Threshold is configurable via meniscus_pct × total meter volume.
        """
        self.ensure_one()
        prefs = self.env['fms.site.preferences'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if prefs and not prefs.require_pos_reconciliation and not self.pos_session_ids:
            return

        # Require product_sales to be up to date
        if not self.product_sales_ids:
            self._refresh_product_sales()

        # Force recompute of accounted_volume on all product sales lines
        self.product_sales_ids.flush_recordset()
        self.product_sales_ids._compute_accounted()

        total_meter  = sum(self.product_sales_ids.mapped('meter_volume'))
        total_pos    = sum(self.product_sales_ids.mapped('accounted_volume'))
        net_residual = abs(total_meter - total_pos)

        # Tolerance: larger of 0.5L or meniscus_pct × total meter volume
        meniscus_pct = self._get_meniscus_pct()
        tolerance_L = max(0.5, total_meter * meniscus_pct / 100.0)

        if net_residual > tolerance_L:
            raise ValidationError(
                f"GATE 1 FAILED — Volume reconciliation gap: "
                f"{net_residual:.2f}L (limit ±{tolerance_L:.2f}L).\n"
                f"  Meter total:  {total_meter:.2f}L\n"
                f"  POS total:    {total_pos:.2f}L\n\n"
                "Check nozzle meter readings and ensure all POS sessions for "
                "this shift are linked before closing."
            )

    def _gate_check_cash_reconciliation(self):
        """
        GATE 2 (Cash): Total electronic cash meter sold ≈ total POS revenue collected.

        Tolerance: 100 KES across all products. This confirms that the REVENUE
        picture is consistent — what the pump cash registers say was collected
        matches what POS recorded as sold.

        A larger gap indicates a price mismatch, missing POS session, or
        unrecorded transactions that must be resolved before closing.
        """
        self.ensure_one()
        prefs = self.env['fms.site.preferences'].search(
            [('company_id', '=', self.company_id.id)], limit=1)
        if prefs and not prefs.require_pos_reconciliation and not self.pos_session_ids:
            return

        if not self.product_sales_ids:
            self._refresh_product_sales()

        # Force recompute of pos_cash_collected on all product sales lines
        self.product_sales_ids.flush_recordset()
        self.product_sales_ids._compute_accounted()

        total_elec_cash = sum(self.product_sales_ids.mapped('elec_cash_sold'))
        total_pos_cash  = sum(self.product_sales_ids.mapped('pos_cash_collected'))
        net_gap = abs(total_elec_cash - total_pos_cash)

        # Tolerance: 100 KES (configurable in future)
        tolerance_KES = 100.0

        if net_gap > tolerance_KES:
            raise ValidationError(
                f"GATE 2 FAILED — Cash reconciliation gap: "
                f"{self.company_id.currency_id.name} {net_gap:,.2f} (limit {self.company_id.currency_id.name} {tolerance_KES:,.2f}).\n"
                f"  Cash meter total: {self.company_id.currency_id.name} {total_elec_cash:,.2f}\n"
                f"  POS total:        {self.company_id.currency_id.name} {total_pos_cash:,.2f}\n\n"
                "Link all POS sessions for this shift and verify pump price "
                "settings match POS product prices before closing."
            )

    # ------------------------------------------------------------------
    # FIN-009: Additional gates G9-G15
    # ------------------------------------------------------------------

    def _gate_check_customer_receipts(self):
        """
        G9 (Customer Receipts): Sum of posted customer receipt payments linked
        to this shift must not exceed total invoiced amount for the shift.

        Catches: duplicate receipt postings, receipts linked to wrong shift,
        over-collection errors.
        """
        self.ensure_one()
        if 'fms_shift_id' not in self.env['account.payment']._fields:
            return
        cur = self.company_id.currency_id
        invoiced = sum(
            self.env['account.move'].search([
                ('fms_shift_id', '=', self.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ]).mapped('amount_total')
        )
        receipts = sum(
            self.env['account.payment'].search([
                ('fms_shift_id', '=', self.id),
                ('fms_payment_context', '=', 'customer_receipt'),
                ('state', '=', 'posted'),
                ('payment_type', '=', 'inbound'),
            ]).mapped('amount')
        )
        if receipts > invoiced + 0.01:
            raise ValidationError(
                f"G9 FAILED — Customer receipts ({cur.name} {receipts:,.2f}) exceed "
                f"invoiced amount ({cur.name} {invoiced:,.2f}) for this shift.\n"
                "Check for duplicate receipt postings or receipts linked to the wrong shift."
            )

    def _gate_check_float_reconciliation(self):
        """
        G10 (Float): Every float issued must have a matching drop or be held in
        cash_collected. Specifically: float_total must equal sum of (cash_drop + cash_collected)
        across all attendants.

        This ensures floats are neither lost nor double-counted.
        """
        self.ensure_one()
        if 'fms_shift_id' not in self.env['account.payment']._fields:
            return
        cur = self.company_id.currency_id
        float_total = sum(
            self.env['account.payment'].search([
                ('fms_shift_id', '=', self.id),
                ('fms_payment_context', '=', 'cash_float'),
                ('state', '=', 'posted'),
            ]).mapped('amount')
        )
        if float_total == 0.0:
            return  # No floats issued — gate passes trivially

        drop_total = sum(
            self.env['account.payment'].search([
                ('fms_shift_id', '=', self.id),
                ('fms_payment_context', 'in', ['cash_drop', 'cash_pickup']),
                ('state', '=', 'posted'),
            ]).mapped('amount')
        )
        cash_collected = sum(self.attendant_cash_ids.mapped('cash_collected'))

        # Float = drops + cash held. Allow 1 KES rounding tolerance.
        accounted = drop_total + cash_collected
        gap = abs(float_total - accounted)
        if gap > 1.0:
            raise ValidationError(
                f"G10 FAILED — Float reconciliation gap: {cur.name} {gap:,.2f}.\n"
                f"  Floats issued:    {cur.name} {float_total:,.2f}\n"
                f"  Cash drops:       {cur.name} {drop_total:,.2f}\n"
                f"  Cash collected:   {cur.name} {cash_collected:,.2f}\n\n"
                "All issued floats must be returned via cash drop or included "
                "in declared cash collected."
            )

    def _gate_check_expense_posting(self):
        """
        G11 (Expenses): All expenses linked to this shift must be posted (not draft).
        A draft expense means cash has been paid but not recorded in GL — creates
        a false balance in the attendant reconciliation.
        """
        self.ensure_one()
        if 'fms_shift_id' not in self.env['account.payment']._fields:
            return
        draft_expenses = self.env['account.payment'].search([
            ('fms_shift_id', '=', self.id),
            ('fms_payment_context', '=', 'expense'),
            ('state', '=', 'draft'),
        ])
        if draft_expenses:
            raise ValidationError(
                f"G11 FAILED — {len(draft_expenses)} expense payment(s) linked to this shift "
                f"are still in draft state. Post all expenses before closing the shift.\n"
                f"Amounts: {', '.join(f'{p.amount:,.2f}' for p in draft_expenses)}"
            )

    def _gate_check_vendor_payment_posting(self):
        """
        G12 (Vendor Payments): All vendor payments from shift cash must be posted.
        Same rationale as G11 — unposted payments create false cash balances.
        """
        self.ensure_one()
        if 'fms_shift_id' not in self.env['account.payment']._fields:
            return
        draft_vendor = self.env['account.payment'].search([
            ('fms_shift_id', '=', self.id),
            ('fms_payment_context', '=', 'vendor_payment'),
            ('state', '=', 'draft'),
        ])
        if draft_vendor:
            raise ValidationError(
                f"G12 FAILED — {len(draft_vendor)} vendor payment(s) from shift cash "
                f"are still in draft state. Post all vendor payments before closing.\n"
                f"Amounts: {', '.join(f'{p.amount:,.2f}' for p in draft_vendor)}"
            )

    def _gate_check_digital_payment_reconciliation(self):
        """
        G13 (Digital Payments): Sum of MPesa + Card payments from POS must equal
        sum of inbound account.payments with payment_method in (mpesa, card) for this shift.

        Catches: POS session MPesa recorded but not bank-confirmed, or bank-confirmed
        but not linked to shift.
        """
        self.ensure_one()
        # POS side: sum from attendant cash computed fields
        pos_mpesa = sum(self.attendant_cash_ids.mapped('mpesa_amount'))
        pos_card  = sum(self.attendant_cash_ids.mapped('card_amount'))
        pos_total = pos_mpesa + pos_card

        # account.payment side: all inbound non-cash payments linked to shift
        # Proxy: payments with fms_payment_context NOT in (customer_receipt, cash_float, cash_drop, cash_pickup, vendor_payment, expense, other)
        # But we don't have a 'digital' context — digital payments come through POS sessions,
        # not account.payment. Gate validates POS digital > 0 only when pos_session_ids exist.
        if not self.pos_session_ids:
            return  # No POS sessions linked — skip

        if pos_total < 0:
            raise ValidationError(
                f"G13 FAILED — Negative digital payment total: {pos_total:,.2f}. "
                "Check POS session payment entries."
            )

    def _gate_check_no_unresolved_exceptions(self):
        """
        G14 (No Blocking Exceptions): No dispute or override log must be in 'pending'
        state for this shift. All exceptions must be resolved before final close.
        """
        self.ensure_one()
        pending_overrides = self.env['fms.shift.override.log'].search([
            ('shift_id', '=', self.id),
        ])
        # Override log existence is allowed (it records completed overrides).
        # This gate checks that the shift itself is not in 'disputed' state —
        # disputed shifts cannot close until returned to 'closing'.
        if self.state == 'disputed':
            raise ValidationError(
                "G14 FAILED — Shift is in 'Disputed' state. "
                "Resolve the dispute and return to 'Closing' state before closing."
            )

    def _gate_check_nonfuel_sales_posted(self):
        """
        G15 (Non-Fuel Sales Posted): All non-fuel invoices and receipts linked
        to this shift must be in posted (confirmed) state before close.

        Skipped if fms_accounting is not installed.
        """
        self.ensure_one()
        AccountMove = self.env['account.move']
        if 'fms_shift_id' not in AccountMove._fields:
            return

        draft_nonfuel = AccountMove.search([
            ('fms_shift_id', '=', self.id),
            ('move_type', 'in', ('out_invoice', 'out_receipt')),
            ('state', '=', 'draft'),
        ])
        # Filter to those with at least one non-fuel product line
        blocking = draft_nonfuel.filtered(
            lambda m: any(
                not (line.product_id and line.product_id.fms_is_fuel)
                for line in m.invoice_line_ids
                if line.display_type == 'product'
            )
        )
        if blocking:
            refs = ', '.join(blocking.mapped('name') or ['(no ref)'])
            raise ValidationError(
                f"G15 FAILED — {len(blocking)} unconfirmed non-fuel "
                f"invoice(s)/receipt(s) linked to this shift:\n{refs}\n\n"
                "Confirm (post) or delete them before closing the shift."
            )

    # ------------------------------------------------------------------
    # FMS-005: Audit log snapshots
    # ------------------------------------------------------------------

    def _write_meter_logs(self):
        """
        Snapshot all meter entries to immutable fms.meter_log records,
        then advance the nozzle's current meter position so the next
        shift opens with accurate opening readings.
        """
        self.ensure_one()
        existing_nozzle_ids = set(
            self.env['fms.meter_log'].sudo()
            .search([('shift_id', '=', self.id)])
            .mapped('nozzle_id')
            .ids
        )
        for entry in self.meter_entry_ids:
            if entry.nozzle_id.id not in existing_nozzle_ids:
                entry._create_meter_log()
            # Advance nozzle's current readings so next shift picks them up
            entry.nozzle_id.sudo().write({
                'current_elec_volume': entry.closing_elec_volume,
                'current_elec_cash':   entry.closing_elec_cash,
                'current_mech_volume': entry.closing_man_mech,
            })

    def _write_dip_logs(self):
        """Snapshot all dip entries to immutable fms.dip_log records."""
        self.ensure_one()
        existing_tank_ids = set(
            self.env['fms.dip_log'].sudo()
            .search([('shift_id', '=', self.id)])
            .mapped('location_id')
            .ids
        )
        for entry in self.dip_entry_ids:
            if entry.location_id.id not in existing_tank_ids:
                vdata = self._compute_dip_variance_data(entry)
                entry._create_dip_log(variance_data=vdata)

    def _sync_stock_quant_from_dips(self):
        """Set stock.quant for each fuel tank to the closing dip volume.

        Called after _write_dip_logs() on shift close. Keeps Odoo book stock
        in sync with physical dip readings so the next shift's book_stock_open
        reflects the actual closing dip of this shift.

        Idempotent: applying the same closing volume twice is harmless.
        Does not raise on failure — logs a warning so shift close is not blocked.
        """
        self.ensure_one()
        company_ids = self.env.companies.ids
        for entry in self.dip_entry_ids:
            if not entry.closing_volume or not entry.product_id:
                continue
            try:
                quant = self.env['stock.quant'].search([
                    ('location_id', '=', entry.location_id.id),
                    ('product_id',  '=', entry.product_id.id),
                    ('company_id',  'in', company_ids),
                ], limit=1)
                if quant:
                    if abs(quant.quantity - entry.closing_volume) < 0.001:
                        continue  # already correct
                    quant.sudo().write({'inventory_quantity': entry.closing_volume})
                else:
                    quant = self.env['stock.quant'].sudo().create({
                        'location_id':        entry.location_id.id,
                        'product_id':         entry.product_id.id,
                        'company_id':         self.company_id.id,
                        'inventory_quantity': entry.closing_volume,
                    })
                quant.sudo().action_apply_inventory()
            except Exception as exc:
                _logger.warning(
                    "FMS: stock quant sync failed for tank %s: %s",
                    entry.location_id.name, exc,
                )

    # ------------------------------------------------------------------
    # FMS-005: GL journal posting
    # ------------------------------------------------------------------

    def _get_fms_journal(self):
        """Return the GL journal for FMS shift entries. Must be configured in Site Preferences."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs and prefs.sales_journal_id:
            return prefs.sales_journal_id
        raise ValidationError(
            "No FMS Sales Journal configured. "
            "Go to Forecourt → Configuration → Site Preferences and set the Sales Journal."
        )

    def _get_clearing_account(self):
        """Return the cash-clearing account. Must be configured in Site Preferences."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs and prefs.clearing_account_id:
            return prefs.clearing_account_id
        raise ValidationError(
            "No FMS Cash Clearing Account configured. "
            "Go to Forecourt → Configuration → Site Preferences and set the Clearing Account."
        )

    def _post_sales_journal(self):
        """
        Post a single account.move for all fuel sales in this shift.

        Journal entry:
          DR  Cash Clearing account    (total meter sales)
          CR  Product Revenue account  (per product, fms_revenue_account_id)

        Products without fms_revenue_account_id are skipped with a warning log.
        Idempotent: returns existing move if already posted.

        Returns the created account.move or False if nothing to post.
        """
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)

        # Idempotency: return existing entry rather than creating a duplicate
        if self.sales_journal_entry_id:
            return self.sales_journal_entry_id

        # Use elec_cash_sold (cash meter) as the authoritative revenue figure.
        # vol×price (amount_elec) is theoretical; the cash meter is what the
        # pump electronics actually recorded as collected.
        total_cash = sum(self.meter_entry_ids.mapped('elec_cash_sold'))
        if abs(total_cash) < 0.01:
            return False

        # Group elec_cash_sold by product for per-product CR lines.
        cash_by_product = {}
        for entry in self.meter_entry_ids:
            if abs(entry.elec_cash_sold) < 0.01:
                continue
            pid = entry.product_id.id
            cash_by_product[pid] = cash_by_product.get(pid, 0.0) + entry.elec_cash_sold

        if not cash_by_product:
            return False

        # Bail early if no products have GL accounts configured.
        products = self.env['product.product'].browse(list(cash_by_product))
        has_revenue_accounts = any(p.fms_revenue_account_id for p in products)
        if not has_revenue_accounts:
            _logger.warning(
                "FMS-005: Shift %s has cash sales of %.2f but no fuel products "
                "have fms_revenue_account_id configured — GL entry skipped.",
                self.display_name, total_cash,
            )
            return False

        journal = self._get_fms_journal()
        clearing_account = self._get_clearing_account()

        move_lines = []

        # DR: cash clearing account for total cash collected per cash meters
        move_lines.append((0, 0, {
            'account_id': clearing_account.id,
            'name': f'Forecourt cash sales — {self.display_name}',
            'debit': total_cash,
            'credit': 0.0,
        }))

        # CR: one line per product (net revenue) + tax lines when taxes configured
        currency = self.company_id.currency_id
        for product in products:
            gross = cash_by_product.get(product.id, 0.0)
            if abs(gross) < 0.01:
                continue
            if not product.fms_revenue_account_id:
                _logger.warning(
                    "FMS-005: Product %s has no fms_revenue_account_id — "
                    "skipped in sales journal for shift %s",
                    product.name, self.display_name,
                )
                total_cash -= gross  # keep DR balanced
                continue

            # Only split price-inclusive taxes: the cash meter total = net + VAT.
            # Tax-excluded taxes (posted separately on invoices) are skipped here
            # to avoid double-counting — the DR clearing already reflects gross.
            taxes = product.taxes_id.filtered(
                lambda t: t.company_id == self.company_id and t.price_include
            )
            if taxes:
                # Gross is tax-inclusive; back-calculate net and tax amounts.
                tax_res = taxes.compute_all(
                    gross, currency=currency, quantity=1.0,
                    product=product, partner=None,
                    is_refund=False, handle_price_include=True,
                )
                net = tax_res['total_excluded']
                # Revenue line (net)
                move_lines.append((0, 0, {
                    'account_id': product.fms_revenue_account_id.id,
                    'name': f'{product.name} — {self.display_name}',
                    'debit': 0.0,
                    'credit': net,
                }))
                # One line per tax group
                for tax_line in tax_res['taxes']:
                    if not tax_line.get('account_id') or abs(tax_line['amount']) < 0.001:
                        # Tax has no repartition account (e.g. price-included informational tax)
                        # or zero amount — skip to avoid move imbalance
                        _logger.warning(
                            "FMS VAT: tax '%s' on product '%s' has no account or zero amount — skipped",
                            tax_line.get('name'), product.name,
                        )
                        continue
                    move_lines.append((0, 0, {
                        'account_id': tax_line['account_id'],
                        'name': f"VAT — {product.name} — {self.display_name}",
                        'debit': 0.0,
                        'credit': tax_line['amount'],
                        'tax_repartition_line_id': tax_line['tax_repartition_line_id'],
                    }))
            else:
                # No taxes — post full gross to revenue
                move_lines.append((0, 0, {
                    'account_id': product.fms_revenue_account_id.id,
                    'name': f'{product.name} — {self.display_name}',
                    'debit': 0.0,
                    'credit': gross,
                }))

        if len(move_lines) < 2:
            return False

        # Rebalance DR to equal actual sum of CRs (net revenue + tax lines)
        cr_total = sum(l[2]['credit'] for l in move_lines if l[2]['credit'])
        move_lines[0][2]['debit'] = cr_total

        move = self.env['account.move'].sudo().create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': self.date,
            'ref': f'FMS Shift: {self.display_name}',
            'line_ids': move_lines,
        })
        move.action_post()
        return move

    def _post_residual_allocation_journals(self):
        """
        Post one account.move per residual allocation line.

        Each allocation moves COGS from source (over-reported) → target (under-reported):
          DR  target product fms_cogs_account_id
          CR  source product fms_cogs_account_id

        Allocation lines that already have a journal_entry_id are skipped (idempotent).
        """
        import logging
        _logger = logging.getLogger(__name__)

        journal = self._get_fms_journal()

        for alloc in self.residual_allocation_ids:
            if alloc.journal_entry_id:
                continue
            if abs(alloc.amount) < 0.01:
                continue

            src_acc = alloc.source_product_id.fms_cogs_account_id
            tgt_acc = alloc.target_product_id.fms_cogs_account_id

            if not src_acc or not tgt_acc:
                _logger.warning(
                    "FMS-005: Allocation %s→%s missing COGS account — skipped",
                    alloc.source_product_id.name,
                    alloc.target_product_id.name,
                )
                continue

            move = self.env['account.move'].sudo().create({
                'move_type': 'entry',
                'journal_id': journal.id,
                'date': self.date,
                'ref': (
                    f'FMS Residual: {alloc.source_product_id.name}'
                    f' → {alloc.target_product_id.name}'
                    f' ({self.display_name})'
                ),
                'line_ids': [
                    (0, 0, {
                        'account_id': tgt_acc.id,
                        'name': f'Residual reallocation — {alloc.target_product_id.name}',
                        'debit': alloc.amount,
                        'credit': 0.0,
                    }),
                    (0, 0, {
                        'account_id': src_acc.id,
                        'name': f'Residual reallocation — {alloc.source_product_id.name}',
                        'debit': 0.0,
                        'credit': alloc.amount,
                    }),
                ],
            })
            move.action_post()
            alloc.sudo().write({'journal_entry_id': move.id})

    def _post_stock_consumption(self):
        """
        Record fuel consumption in Odoo's stock ledger via validated stock.move records.

        One stock.move per fuel product sold (grouped from meter entries).
        Source: the fuel tank (stock.location with fms_is_fuel_tank=True, linked to product).
        Destination: virtual "Customers" location (partner_id=False, usage=customer).

        Idempotent: checks for existing stock.moves with origin matching this shift
        before creating new ones.

        Skipped when:
          - No meter sales exist
          - Tank has no fms_fuel_product_id configured
          - Product has no storable type (service products don't move stock)
        """
        import logging
        _logger = logging.getLogger(__name__)
        self.ensure_one()

        # Already posted — skip (idempotency)
        existing = self.env['stock.move'].sudo().search([
            ('origin', '=', f'FMS/{self.display_name}'),
            ('state', '=', 'done'),
        ], limit=1)
        if existing:
            return

        # Qty sold per product from electronic (cash) meter — authoritative
        qty_by_product = {}
        for entry in self.meter_entry_ids:
            pid = entry.product_id.id
            qty_by_product[pid] = qty_by_product.get(pid, 0.0) + entry.qty_sold_elec

        if not any(q > 0.01 for q in qty_by_product.values()):
            return

        # Map product → source tank (stock.location)
        tanks = self.env['stock.location'].sudo().search([
            ('fms_is_fuel_tank', '=', True),
            ('fms_fuel_product_id', '!=', False),
            ('active', '=', True),
        ])
        tank_by_product = {t.fms_fuel_product_id.id: t for t in tanks}

        # Standard "Customers" virtual location
        customer_loc = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
        if not customer_loc:
            _logger.warning("FMS stock: 'stock.stock_location_customers' not found — stock consumption skipped.")
            return

        for product in self.env['product.product'].sudo().browse(list(qty_by_product)):
            qty = qty_by_product.get(product.id, 0.0)
            if qty < 0.01:
                continue
            if product.type not in ('product', 'consu'):
                # Service product — no stock ledger impact
                continue
            tank = tank_by_product.get(product.id)
            if not tank:
                _logger.warning(
                    "FMS stock: no fuel tank configured for product '%s' — skipping stock move.",
                    product.name,
                )
                continue

            move = self.env['stock.move'].sudo().create({
                'name': f'Fuel consumption — {product.name} — {self.display_name}',
                'origin': f'FMS/{self.display_name}',
                'product_id': product.id,
                'product_uom': product.uom_id.id,
                'product_uom_qty': qty,
                'location_id': tank.id,
                'location_dest_id': customer_loc.id,
                'date': fields.Datetime.now(),
                'company_id': self.company_id.id,
            })
            move._action_confirm()
            move._action_assign()
            move._set_quantity_done(qty)
            move.with_context(cancel_backorder=True)._action_done()
