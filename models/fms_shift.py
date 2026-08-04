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

    fms_is_fuel_tank = fields.Boolean('Is Fuel Tank', default=False)
    fms_fuel_product_id = fields.Many2one(
        'product.product', 'Fuel Product in Tank',
        domain=[('fms_is_fuel', '=', True)],
    )


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
        ('1_day',     '1. Day (06:00–14:00)'),
        ('2_evening', '2. Evening (14:00–22:00)'),
        ('3_night',   '3. Night (22:00–06:00)'),
    ], string='Shift Period', required=True)

    supervisor_id = fields.Many2one('hr.employee', 'Supervisor', required=True)
    company_id = fields.Many2one(
        'res.company', 'Company',
        required=True, default=lambda self: self.env.company,
    )

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    state = fields.Selection([
        ('draft',   'Draft'),
        ('open',    'Open'),
        ('closing', 'Closing'),
        ('closed',  'Closed'),
    ], string='Status', default='draft', readonly=True, copy=False)

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
        'Total Meter Sales (KES)', compute='_compute_totals', store=True, digits=(16, 2),
    )
    total_reported_sales = fields.Float(
        'Total Reported Sales (KES)', compute='_compute_totals', store=True, digits=(16, 2),
    )
    fc_cash_balance = fields.Float(
        'FC Cash Balance (KES)', compute='_compute_totals', store=True, digits=(16, 2),
        help="Total Reported Sales minus Total Meter Sales. Must be 0 to close.",
    )

    @api.depends(
        'meter_entry_ids.amount_elec',
        'attendant_cash_ids.total_in',
        'attendant_cash_ids.balance',
    )
    def _compute_totals(self):
        for shift in self:
            shift.total_meter_sales = sum(shift.meter_entry_ids.mapped('amount_elec'))
            shift.total_reported_sales = sum(shift.attendant_cash_ids.mapped('total_in'))
            shift.fc_cash_balance = sum(shift.attendant_cash_ids.mapped('balance'))

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

    # ------------------------------------------------------------------
    # Product sales rollup
    # ------------------------------------------------------------------

    def action_report_fms_shift(self):
        """Open the Shift Reconciliation PDF report for this shift."""
        self.ensure_one()
        return self.env.ref('fms.action_report_fms_shift').report_action(self)

    def action_refresh_product_sales(self):
        """Re-aggregate meter entries into product sales summary lines."""
        for shift in self:
            shift._refresh_product_sales()

    def _refresh_product_sales(self):
        """
        Delete existing product_sales_ids and rebuild from meter_entry_ids.
        Called explicitly by the supervisor button or on shift close.
        """
        self.ensure_one()
        self.product_sales_ids.unlink()

        # Group meter entries by product
        by_product = {}
        for entry in self.meter_entry_ids:
            if not entry.product_id:
                continue
            pid = entry.product_id.id
            if pid not in by_product:
                by_product[pid] = {'qty_elec': 0.0, 'qty_man': 0.0, 'amount': 0.0}
            by_product[pid]['qty_elec'] += entry.qty_sold_elec
            by_product[pid]['qty_man'] += entry.qty_sold_man
            by_product[pid]['amount'] += entry.amount_elec

        for product_id, totals in by_product.items():
            self.env['fms.shift.product.sales'].create({
                'shift_id': self.id,
                'product_id': product_id,
                'qty_sold_elec': totals['qty_elec'],
                'qty_sold_man': totals['qty_man'],
                'amount_elec': totals['amount'],
            })

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
            vals.setdefault('company_id', self.env.company.id)
        return super().create(vals_list)

    def unlink(self):
        if any(s.state == 'closed' for s in self):
            raise ValidationError(
                "Closed shifts cannot be deleted — they are part of the audit trail."
            )
        return super().unlink()

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
                    opening_man_mech    = nozzle.current_man_mech
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
            if meter_entries:
                self.env['fms.shift.meter.entry'].create(meter_entries)

        # ── Dip entries ──────────────────────────────────────────────────────
        if not self.dip_entry_ids:
            tanks = self.env['stock.location'].search([
                ('fms_is_fuel_tank', '=', True),
                ('active', '=', True),
            ])
            dip_entries = []
            for tank in tanks:
                opening_vol = 0.0
                if prev:
                    log = self.env['fms.dip_log'].search([
                        ('shift_id', '=', prev.id),
                        ('location_id', '=', tank.id),
                    ], limit=1)
                    if log:
                        opening_vol = log.closing_volume
                dip_entries.append({
                    'shift_id':      self.id,
                    'location_id':   tank.id,
                    'opening_volume': opening_vol,
                    'closing_volume': 0.0,  # entered at shift end
                })
            if dip_entries:
                self.env['fms.shift.dip.entry'].create(dip_entries)

    def action_start_closing(self):
        """
        Move Open → Closing and auto-run residual allocation algorithm.
        """
        self.ensure_one()
        if self.state != 'open':
            raise ValidationError(
                f"Cannot start closing a shift that is '{self.state}'."
            )
        self.write({
            'state': 'closing',
            'closing_meter_date': fields.Datetime.now(),
            'closing_meter_user_id': self.env.user.id,
        })
        # Auto-calculate residuals on transition to closing
        self._calculate_residuals()

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
        Full 5-step residual allocation algorithm (Spec Section 7.1).

        Step 1: Rebuild product sales from meter entries.
        Step 2: Compute accounted amounts per product from POS order lines.
        Step 3: Residual = meter_amount − accounted_amount.
                  < 0 → over-reported in POS (lumped non-fuel)
                  > 0 → under-reported in POS (absorbed lumped sales)
        Step 4: Greedy-match over-reported → under-reported products.
        Step 5: Create fms.shift.residual.allocation records.

        Returns count of allocation records created.
        """
        self.ensure_one()

        # Clear existing allocations so re-runs are idempotent
        self.residual_allocation_ids.unlink()

        # Step 1: rebuild product sales
        self._refresh_product_sales()

        # Step 2: accounted amounts from POS order lines per product
        accounted_by_product = self._get_accounted_by_product()

        # Step 3: compute residuals and classify each product sales line
        meter_by_product = {}
        for ps in self.product_sales_ids:
            pid = ps.product_id.id
            meter_by_product[pid] = ps.amount_elec

        over_reported  = {}   # pid → surplus amount (positive)
        under_reported = {}   # pid → deficit amount (positive)

        for ps in self.product_sales_ids:
            pid      = ps.product_id.id
            meter    = ps.amount_elec
            acc      = accounted_by_product.get(pid, 0.0)
            residual = meter - acc   # +ve = under, -ve = over

            price = ps.product_id.list_price or 1.0
            res_qty = residual / price if price else 0.0

            if residual < -0.01:
                rtype = 'over'
                over_reported[pid] = abs(residual)
            elif residual > 0.01:
                rtype = 'under'
                under_reported[pid] = residual
            else:
                rtype = 'none'

            ps.write({
                'residual_amount': residual,
                'residual_qty': res_qty,
                'residual_type': rtype,
            })

        # Step 4: greedy matching (largest over-reported first)
        allocations = self._run_greedy_allocation(over_reported, under_reported)

        # Step 5: create allocation records
        alloc_vals = []
        for (over_pid, under_pid, amt) in allocations:
            under_product = self.env['product.product'].browse(under_pid)
            price = under_product.list_price or 1.0
            alloc_vals.append({
                'shift_id':          self.id,
                'source_product_id': over_pid,
                'target_product_id': under_pid,
                'qty_litres':        amt / price,
                'amount':            amt,
                'notes':             'Auto-calculated — residual reconciliation',
            })
        if alloc_vals:
            self.env['fms.shift.residual.allocation'].create(alloc_vals)

        return len(alloc_vals)

    def _get_accounted_by_product(self):
        """
        Return {product_id: amount} from POS order lines for linked sessions.
        Falls back to empty dict when no sessions linked (all residuals = meter).
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
            result[pid] = result.get(pid, 0.0) + line.price_subtotal_incl
        return result

    @staticmethod
    def _run_greedy_allocation(over_reported, under_reported):
        """
        Pure algorithm: match over-reported to under-reported using greedy approach.

        Args:
            over_reported:  {product_id: surplus_amount}  — products POS over-credited
            under_reported: {product_id: deficit_amount}  — products POS under-credited

        Returns list of (over_pid, under_pid, qty_litres, amount) tuples.
        NOTE: qty_litres here is amount/1 — caller must scale by product price.
              We return (over_pid, under_pid, 0.0, amount) and let the caller
              compute qty from the under_product's price.
        """
        # Work on copies, sorted largest-first so biggest gaps are matched first
        over  = {k: v for k, v in sorted(over_reported.items(),  key=lambda x: -x[1])}
        under = {k: v for k, v in sorted(under_reported.items(), key=lambda x: -x[1])}

        allocations = []
        for over_pid in list(over):
            for under_pid in list(under):
                if over.get(over_pid, 0.0) < 0.01:
                    break  # this over-product is fully allocated
                if under.get(under_pid, 0.0) < 0.01:
                    continue  # this under-product is fully absorbed

                alloc_amt = min(over[over_pid], under[under_pid])
                allocations.append((over_pid, under_pid, alloc_amt))

                over[over_pid]   -= alloc_amt
                under[under_pid] -= alloc_amt

        return allocations

    def action_close_shift(self):
        """
        Move Closing → Closed:
          1. Snapshot meter and dip entries into immutable logs.
          2. Post sales GL journal (DR Cash Clearing | CR Fuel Revenue per product).
          3. Post residual reallocation journals (DR target COGS | CR source COGS).
          4. Transition state to 'closed'.

        All steps are wrapped in a savepoint so any GL failure rolls back
        the whole close, keeping shift in 'closing' for supervisor to fix.

        Hard gate validation (FMS-006) will be added on top of this method.
        """
        self.ensure_one()
        if self.state != 'closing':
            raise ValidationError(
                f"Cannot close a shift that is '{self.state}'. "
                "Use 'Start Closing' first."
            )
        # FMS-006: Hard gate validation — all must pass before shift can close
        self._gate_check_fc_cash()
        self._gate_check_attendant_balances()
        self._gate_check_stock_variance()

        with self.env.cr.savepoint():
            self._write_meter_logs()
            self._write_dip_logs()
            sales_move = self._post_sales_journal()
            self._post_residual_allocation_journals()

        vals = {'state': 'closed'}
        if sales_move:
            vals['sales_journal_entry_id'] = sales_move.id
        self.write(vals)

    # ------------------------------------------------------------------
    # FMS-006: Hard gate validators (Spec Section 7.2–7.3)
    # ------------------------------------------------------------------

    # Default maximum allowed tank variance (±0.5% of closing dip volume).
    # Overridable via ir.config_parameter 'fms.meniscus_pct' in future.
    _MENISCUS_PCT = 0.5

    def _gate_check_fc_cash(self):
        """
        GATE 1: Forecourt cash balance must be exactly zero.

        fc_cash_balance = sum of all attendant balances.
        If it is non-zero the supervisor has not resolved a discrepancy —
        they must post a correction before the shift can close.
        """
        self.ensure_one()
        # Re-compute to get latest value from computed fields
        balance = sum(c.balance for c in self.attendant_cash_ids)
        if abs(balance) > 0.01:
            raise ValidationError(
                f"GATE 1 FAILED — Forecourt Cash Balance is KES {balance:,.2f} "
                "(must be exactly 0).\n"
                "Resolve all attendant discrepancies before closing the shift."
            )

    def _gate_check_attendant_balances(self):
        """
        GATE 2: Every individual attendant's balance must be zero.

        Even if the FC total nets to zero, individual discrepancies must
        be resolved one-by-one.  The error lists every failing attendant.
        """
        self.ensure_one()
        failing = []
        for cash in self.attendant_cash_ids:
            if abs(cash.balance) > 0.01:
                failing.append(
                    f"  • {cash.attendant_id.name}: KES {cash.balance:,.2f}"
                )
        if failing:
            lines = "\n".join(failing)
            raise ValidationError(
                f"GATE 2 FAILED — {len(failing)} attendant(s) have unresolved balances:\n"
                f"{lines}\n\n"
                "Each attendant balance must be 0 before the shift can close."
            )

    def _gate_check_stock_variance(self):
        """
        GATE 3: Tank dip variance must be within the allowed meniscus.

        Default meniscus: ±0.5% of closing dip volume.
        If a tank's variance_pct exceeds this, the supervisor must
        investigate and post an adjustment or dip correction.
        """
        self.ensure_one()
        meniscus = self._MENISCUS_PCT
        failing = []
        for dip in self.dip_entry_ids:
            if dip.closing_volume <= 0:
                continue  # Skip tanks with no reading — not an error
            if dip.variance_pct > meniscus:
                failing.append(
                    f"  • {dip.location_id.name}: "
                    f"variance {dip.variance_pct:.4f}% "
                    f"(limit ±{meniscus}%)"
                )
        if failing:
            lines = "\n".join(failing)
            raise ValidationError(
                f"GATE 3 FAILED — {len(failing)} tank(s) exceed the "
                f"±{meniscus}% variance meniscus:\n"
                f"{lines}\n\n"
                "Investigate the variance or post a dip adjustment before closing."
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
                'current_man_mech':    entry.closing_man_mech,
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
                entry._create_dip_log()

    # ------------------------------------------------------------------
    # FMS-005: GL journal posting
    # ------------------------------------------------------------------

    def _get_fms_journal(self):
        """
        Return the GL journal to use for FMS shift entries.

        Looks for a journal named 'Forecourt Sales' first; falls back to
        the first sale-type journal in the company.  Raises if none found.
        """
        Journal = self.env['account.journal']
        journal = Journal.search([
            ('name', 'ilike', 'forecourt'),
            ('type', '=', 'sale'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal:
            journal = Journal.search([
                ('type', '=', 'sale'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not journal:
            raise ValidationError(
                "No sale-type journal found for this company. "
                "Create a 'Forecourt Sales' journal in Accounting → Journals."
            )
        return journal

    def _get_clearing_account(self):
        """
        Return the cash-clearing account for the Debit side of the sales entry.

        Tries to find an account with 'clearing' or 'forecourt' in its name
        (type receivable or current asset).  Falls back to the journal's default
        debit account, then to the first receivable account.
        """
        Account = self.env['account.account']
        acc = Account.search([
            ('name', 'ilike', 'clearing'),
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ('asset_receivable', 'asset_current')),
        ], limit=1)
        if not acc:
            acc = Account.search([
                ('account_type', '=', 'asset_receivable'),
                ('company_id', '=', self.company_id.id),
            ], limit=1)
        if not acc:
            raise ValidationError(
                "Cannot find a receivable/clearing account for the sales journal entry. "
                "Configure accounts in Accounting → Chart of Accounts."
            )
        return acc

    def _post_sales_journal(self):
        """
        Post a single account.move for all fuel sales in this shift.

        Journal entry:
          DR  Cash Clearing account    (total meter sales)
          CR  Product Revenue account  (per product, fms_revenue_account_id)

        Products without fms_revenue_account_id are skipped with a warning log.

        Returns the created account.move or False if nothing to post.
        """
        self.ensure_one()
        import logging
        _logger = logging.getLogger(__name__)

        if not self.product_sales_ids:
            return False

        total_sales = sum(ps.amount_elec for ps in self.product_sales_ids)
        if abs(total_sales) < 0.01:
            return False

        # Bail early if no products have GL accounts configured —
        # avoids journal/account lookups when the chart of accounts is not yet wired.
        has_revenue_accounts = any(
            ps.product_id.fms_revenue_account_id
            for ps in self.product_sales_ids
            if abs(ps.amount_elec) >= 0.01
        )
        if not has_revenue_accounts:
            _logger.warning(
                "FMS-005: Shift %s has sales of KES %.2f but no fuel products "
                "have fms_revenue_account_id configured — GL entry skipped.",
                self.display_name, total_sales,
            )
            return False

        journal = self._get_fms_journal()
        clearing_account = self._get_clearing_account()

        move_lines = []

        # DR line: cash/clearing account for total sales
        move_lines.append((0, 0, {
            'account_id': clearing_account.id,
            'name': f'Forecourt sales — {self.display_name}',
            'debit': total_sales,
            'credit': 0.0,
        }))

        # CR lines: one per product
        for ps in self.product_sales_ids:
            if abs(ps.amount_elec) < 0.01:
                continue
            revenue_account = ps.product_id.fms_revenue_account_id
            if not revenue_account:
                _logger.warning(
                    "FMS-005: Product %s has no fms_revenue_account_id — "
                    "skipped in sales journal for shift %s",
                    ps.product_id.name, self.display_name,
                )
                continue
            move_lines.append((0, 0, {
                'account_id': revenue_account.id,
                'name': f'{ps.product_id.name} — {self.display_name}',
                'debit': 0.0,
                'credit': ps.amount_elec,
            }))

        if not move_lines or len(move_lines) < 2:
            return False

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
