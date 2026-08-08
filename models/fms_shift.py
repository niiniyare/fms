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
        help="Sum of elec_cash_sold across all nozzles — total cash the pumps say was collected.",
    )
    total_reported_sales = fields.Float(
        'Total Reported Sales (KES)', compute='_compute_totals', store=True, digits=(16, 2),
        help="Sum of reported_sales across all attendant cash lines (derived from their nozzle meters).",
    )
    fc_cash_balance = fields.Float(
        'FC Cash Balance (KES)', compute='_compute_totals', store=True, digits=(16, 2),
        help="Net balance across all attendants (total_in − total_out). Must be 0 to close.",
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

        for product_id, totals in by_product.items():
            product = self.env['product.product'].browse(product_id)
            self.env['fms.shift.product.sales'].create({
                'shift_id':         self.id,
                'product_id':       product_id,
                'meter_volume':     totals['meter_volume'],
                'meter_volume_man': totals['meter_volume_man'],
                'elec_cash_sold':   totals['elec_cash_sold'],
                'price_at_close':   product.list_price or 0.0,
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
            # Always use the creating user's company — ignore any passed value.
            vals['company_id'] = self.env.company.id
            # Set planned open/close from site preferences if not already set.
            if not vals.get('planned_open') and vals.get('date') and vals.get('label'):
                planned_open, planned_close = self._compute_planned_times(
                    vals['date'], vals['label'], self.env.company
                )
                vals.setdefault('planned_open',  planned_open)
                vals.setdefault('planned_close', planned_close)

        # Block creating a new shift if one is already active (draft/open/closing).
        company_id = self.env.company.id
        conflict = self.search([
            ('company_id', '=', company_id),
            ('state', 'in', ('draft', 'open', 'closing')),
        ], limit=1)
        if conflict:
            raise ValidationError(
                f"Shift '{conflict.display_name}' is already active "
                f"({conflict.state}). Close or delete it before creating a new shift."
            )

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
        # Conditionally sync attendant cash lines (controlled by site preferences)
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.auto_sync_attendants:
            self._sync_attendant_cash_lines()
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

        if not self._is_empty_shift():
            # Supervisor required when money is involved
            if not self.supervisor_id:
                raise ValidationError(
                    "A supervisor must be assigned before closing a shift with sales. "
                    "Set the Supervisor field and try again."
                )
            # Full gate sequence
            self._gate_check_volume_reconciliation()
            self._gate_check_cash_reconciliation()
            self._gate_check_attendant_balances()
            self._gate_check_fc_cash()
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

        # Auto-open next shift if site preferences say so
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.auto_open_next_shift:
            self._auto_open_next_shift()

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

    _MENISCUS_PCT = 0.5  # fallback when no site preferences record exists

    def _get_meniscus_pct(self):
        """Return the configured meniscus % from site preferences, or class default."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        return prefs.meniscus_pct if prefs.meniscus_pct > 0 else self._MENISCUS_PCT

    def _gate_check_fc_cash(self):
        """
        GATE 4 (FC Cash): Forecourt cash balance must be exactly zero.

        fc_cash_balance = sum of all attendant balances.
        If it is non-zero the supervisor has not resolved a discrepancy —
        they must post a correction before the shift can close.
        """
        self.ensure_one()
        # Re-compute to get latest value from computed fields
        balance = sum(c.balance for c in self.attendant_cash_ids)
        if abs(balance) > 0.01:
            raise ValidationError(
                f"GATE 4 FAILED (FC Cash) — Forecourt Cash Balance is KES {balance:,.2f} "
                "(must be exactly 0).\n"
                "Resolve all attendant discrepancies before closing the shift."
            )

    def _gate_check_attendant_balances(self):
        """
        GATE 3 (Attendants): Every individual attendant's balance must be zero.

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
                f"GATE 3 FAILED (Attendants) — {len(failing)} attendant(s) have unresolved balances:\n"
                f"{lines}\n\n"
                "Each attendant balance must be 0 before the shift can close."
            )

    def _gate_check_stock_variance(self):
        """
        GATE 5 (Variance): Tank dip variance must be within the allowed meniscus.

        Default meniscus: ±0.5% of closing dip volume.
        If a tank's variance_pct exceeds this, the supervisor must
        investigate and post an adjustment or dip correction.
        """
        self.ensure_one()
        meniscus = self._get_meniscus_pct()
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
                f"GATE 5 FAILED (Variance) — {len(failing)} tank(s) exceed the "
                f"±{meniscus}% variance meniscus:\n"
                f"{lines}\n\n"
                "Investigate the variance or post a dip adjustment before closing."
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
                f"KES {net_gap:,.2f} (limit KES {tolerance_KES:,.2f}).\n"
                f"  Cash meter total: KES {total_elec_cash:,.2f}\n"
                f"  POS total:        KES {total_pos_cash:,.2f}\n\n"
                "Link all POS sessions for this shift and verify pump price "
                "settings match POS product prices before closing."
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
                entry._create_dip_log()

    # ------------------------------------------------------------------
    # FMS-005: GL journal posting
    # ------------------------------------------------------------------

    def _get_fms_journal(self):
        """Return the GL journal for FMS shift entries (site prefs → name search → fallback)."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.sales_journal_id:
            return prefs.sales_journal_id
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
                "No sale-type journal found. "
                "Set one in Forecourt → Configuration → Site Preferences."
            )
        return journal

    def _get_clearing_account(self):
        """Return the cash-clearing account (site prefs → name search → fallback)."""
        prefs = self.env['fms.site.preferences'].get_for_company(self.company_id)
        if prefs.clearing_account_id:
            return prefs.clearing_account_id
        Account = self.env['account.account']
        acc = Account.search([
            ('name', 'ilike', 'clearing'),
            ('company_ids', 'in', self.company_id.id),
            ('account_type', 'in', ('asset_receivable', 'asset_current')),
        ], limit=1)
        if not acc:
            acc = Account.search([
                ('account_type', '=', 'asset_receivable'),
                ('company_ids', 'in', self.company_id.id),
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
                "FMS-005: Shift %s has cash sales of KES %.2f but no fuel products "
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

        # CR: one line per product
        for product in products:
            amount = cash_by_product.get(product.id, 0.0)
            if abs(amount) < 0.01:
                continue
            if not product.fms_revenue_account_id:
                _logger.warning(
                    "FMS-005: Product %s has no fms_revenue_account_id — "
                    "skipped in sales journal for shift %s",
                    product.name, self.display_name,
                )
                total_cash -= amount  # keep DR balanced
                continue
            move_lines.append((0, 0, {
                'account_id': product.fms_revenue_account_id.id,
                'name': f'{product.name} — {self.display_name}',
                'debit': 0.0,
                'credit': amount,
            }))

        if len(move_lines) < 2:
            return False

        # Rebalance DR to equal actual sum of CRs (after skipping unconfigured products)
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
