"""
fms_overview.py — Computed dashboard model backing the §15 Overview page.

One TransientModel, one SQL pass per open, no persistent state.
Every figure reads from existing tables or SQL views — no duplicate logic.

Tile layout (§15.2):
  Row 1  Alerts     — hidden when empty; sorted by money at risk
  Row 2  Yesterday  — throughput · sales · cash · worst wetstock variance
  Row 3  Stock      — one row per tank, days of cover, reorder flag
  Row 4  Chart      — action button → R3 (30-day cumulative variance)
  Row 5  Debtors    — total AR, aging split, over-limit count
  Row 6  People     — current shift, nozzle assignments
"""

from odoo import api, fields, models
from datetime import date, timedelta


class FMSOverview(models.TransientModel):
    _name        = 'fms.overview'
    _description = 'Forecourt Overview Dashboard'

    # ── Row 1  Alerts ─────────────────────────────────────────────────────────

    shifts_open_late      = fields.Integer('Shifts Open Late',       readonly=True)
    open_residuals        = fields.Integer('Open Residuals',         readonly=True)
    unrecovered_incidents = fields.Integer('Unrecovered Incidents',  readonly=True)
    gates_failed          = fields.Integer('Close Failures (30d)',   readonly=True)
    any_alert             = fields.Boolean('Any Alert',              readonly=True,
                                           help="True when at least one Row-1 tile has content")

    # ── Row 2  Yesterday ──────────────────────────────────────────────────────

    yesterday_date          = fields.Date('Yesterday',               readonly=True)
    yesterday_throughput_l  = fields.Float('Throughput (L)',         readonly=True, digits=(16, 0))
    yesterday_throughput_vs = fields.Float('vs 7-day avg (%)',       readonly=True, digits=(16, 1))
    yesterday_sales_kes     = fields.Float('Sales (KES)',            readonly=True, digits=(16, 0))
    yesterday_cash_var      = fields.Float('Cash Over/Short (KES)',  readonly=True, digits=(16, 2))
    yesterday_shifts        = fields.Integer('Shifts Yesterday',     readonly=True)

    # Worst wetstock variance across all tanks (rolling 7-day)
    worst_tank_name         = fields.Char('Worst Tank',              readonly=True)
    worst_variance_pct      = fields.Float('Worst Variance %',       readonly=True, digits=(16, 2))
    worst_variance_verdict  = fields.Selection([
        ('ok',     'Within tolerance'),
        ('warn',   'Approaching limit'),
        ('breach', 'Tolerance breached'),
    ], 'Verdict', readonly=True)

    # ── Row 3  Stock ──────────────────────────────────────────────────────────
    # Rendered as embedded list via fms.report.stock.position action — no fields here.

    reorder_tank_count      = fields.Integer('Tanks at Reorder',     readonly=True)

    # ── Row 5  Debtors ────────────────────────────────────────────────────────

    total_ar                = fields.Float('Total AR (KES)',         readonly=True, digits=(16, 0))
    over_limit_count        = fields.Integer('Over Limit',           readonly=True)
    ar_overdue_90           = fields.Float('90+ Days (KES)',         readonly=True, digits=(16, 0))

    # ── Row 6  People ─────────────────────────────────────────────────────────

    current_shift_label     = fields.Char('Current Shift',          readonly=True)
    current_supervisor      = fields.Char('Supervisor',             readonly=True)
    current_attendant_count = fields.Integer('Attendants on Shift', readonly=True)
    open_shortage_kes       = fields.Float('Outstanding Shortages (KES)', readonly=True, digits=(16, 0))

    # ------------------------------------------------------------------
    # Singleton entry point — action opens (or refreshes) one record
    # ------------------------------------------------------------------

    def action_refresh(self):
        """Re-compute and reload — called by the Refresh button on the form."""
        rec = self.create(self._compute_overview())
        return {
            'type':      'ir.actions.act_window',
            'name':      'Forecourt Overview',
            'res_model': 'fms.overview',
            'res_id':    rec.id,
            'view_mode': 'form',
            'view_id':   self.env.ref('fms.view_fms_overview_form').id,
            'target':    'main',
            'flags':     {'mode': 'readonly'},
        }

    def action_open_debtors(self):
        """Open Debtor Aging report — gracefully absent if fms_accounting not installed."""
        try:
            return self.env.ref('fms_accounting.action_fms_debtor_aging').read()[0]
        except Exception:
            return {'type': 'ir.actions.act_window_close'}

    @api.model
    def action_open_overview(self):
        """Create a fresh computed record and open it. Called by the server action menu entry."""
        rec = self.create(self._compute_overview())
        return {
            'type':      'ir.actions.act_window',
            'name':      'Forecourt Overview',
            'res_model': 'fms.overview',
            'res_id':    rec.id,
            'view_mode': 'form',
            'view_id':   self.env.ref('fms.view_fms_overview_form').id,
            'target':    'main',
            'flags':     {'mode': 'readonly'},
        }

    # ------------------------------------------------------------------
    # Computation — one method, one DB round-trip per section
    # ------------------------------------------------------------------

    @api.model
    def _compute_overview(self):
        cr = self.env.cr
        today     = date.today()
        yesterday = today - timedelta(days=1)
        ago_7     = today - timedelta(days=7)
        ago_30    = today - timedelta(days=30)
        cid       = self.env.company.id

        vals = {}

        # ── Row 1: alerts ─────────────────────────────────────────────────

        # Shifts still open past their planned close time
        cr.execute("""
            SELECT COUNT(*) FROM fms_shift
            WHERE state = 'open'
              AND company_id = %s
              AND planned_close < NOW()
        """, (cid,))
        vals['shifts_open_late'] = cr.fetchone()[0] or 0

        # Unallocated attribution residuals
        try:
            cr.execute("""
                SELECT COUNT(*) FROM fms_report_residual_exception
                WHERE company_id = %s AND NOT is_allocated
            """, (cid,))
            vals['open_residuals'] = cr.fetchone()[0] or 0
        except Exception:
            vals['open_residuals'] = 0

        # Unrecovered incidents
        try:
            cr.execute("""
                SELECT COUNT(*) FROM fms_incident
                WHERE company_id = %s AND recovery_status NOT IN ('recovered','written_off')
            """, (cid,))
            vals['unrecovered_incidents'] = cr.fetchone()[0] or 0
        except Exception:
            vals['unrecovered_incidents'] = 0

        # Gate failures (shifts closed with validation overrides in last 30 days)
        # Proxy: shifts in 'disputed' state or shifts whose close took >1 attempt
        # Simple proxy: count closed shifts with non-zero fc_cash_balance in last 30d
        cr.execute("""
            SELECT COUNT(*) FROM fms_shift
            WHERE state = 'closed'
              AND company_id = %s
              AND date >= %s
              AND ABS(fc_cash_balance) > 0.01
        """, (cid, ago_30))
        vals['gates_failed'] = cr.fetchone()[0] or 0

        vals['any_alert'] = any([
            vals['shifts_open_late'],
            vals['open_residuals'],
            vals['unrecovered_incidents'],
        ])

        # ── Row 2: yesterday ──────────────────────────────────────────────

        vals['yesterday_date'] = yesterday

        cr.execute("""
            SELECT
                COUNT(*)                              AS shift_count,
                COALESCE(SUM(total_meter_sales), 0)   AS sales_kes,
                COALESCE(SUM(fc_cash_balance),   0)   AS cash_var
            FROM fms_shift
            WHERE date = %s AND company_id = %s AND state = 'closed'
        """, (yesterday, cid))
        row = cr.fetchone()
        vals['yesterday_shifts']   = row[0] or 0
        vals['yesterday_sales_kes'] = row[1] or 0.0
        vals['yesterday_cash_var'] = row[2] or 0.0

        # Throughput: sum of meter entries for yesterday's closed shifts
        cr.execute("""
            SELECT COALESCE(SUM(me.qty_sold_elec), 0)
            FROM fms_shift_meter_entry me
            JOIN fms_shift s ON s.id = me.shift_id
            WHERE s.date = %s AND s.company_id = %s AND s.state = 'closed'
        """, (yesterday, cid))
        vals['yesterday_throughput_l'] = cr.fetchone()[0] or 0.0

        # 7-day average throughput per day (excluding yesterday itself)
        cr.execute("""
            SELECT COALESCE(SUM(me.qty_sold_elec), 0) / 7.0
            FROM fms_shift_meter_entry me
            JOIN fms_shift s ON s.id = me.shift_id
            WHERE s.date >= %s AND s.date < %s
              AND s.company_id = %s AND s.state = 'closed'
        """, (ago_7, yesterday, cid))
        avg_7 = cr.fetchone()[0] or 0.0
        if avg_7 > 0:
            vals['yesterday_throughput_vs'] = round(
                (vals['yesterday_throughput_l'] - avg_7) / avg_7 * 100, 1)
        else:
            vals['yesterday_throughput_vs'] = 0.0

        # Worst 7-day wetstock variance
        try:
            cr.execute("""
                SELECT tank_name, variance_pct_7d
                FROM fms_report_wetstock
                WHERE company_id = %s
                  AND shift_date >= %s
                ORDER BY ABS(variance_pct_7d) DESC NULLS LAST
                LIMIT 1
            """, (cid, ago_7))
            wrow = cr.fetchone()
            if wrow:
                vals['worst_tank_name']    = wrow[0]
                vals['worst_variance_pct'] = abs(wrow[1] or 0.0)
                pct = vals['worst_variance_pct']
                vals['worst_variance_verdict'] = (
                    'breach' if pct > 1.0 else
                    'warn'   if pct > 0.5 else
                    'ok'
                )
            else:
                vals['worst_tank_name']       = '—'
                vals['worst_variance_pct']    = 0.0
                vals['worst_variance_verdict'] = 'ok'
        except Exception:
            vals['worst_tank_name']       = '—'
            vals['worst_variance_pct']    = 0.0
            vals['worst_variance_verdict'] = 'ok'

        # ── Row 3: reorder count ──────────────────────────────────────────

        try:
            cr.execute("""
                SELECT COUNT(*) FROM fms_report_stock_position
                WHERE company_id = %s AND reorder_flag = TRUE
            """, (cid,))
            vals['reorder_tank_count'] = cr.fetchone()[0] or 0
        except Exception:
            vals['reorder_tank_count'] = 0

        # ── Row 5: debtors (fms_accounting optional) ──────────────────────

        try:
            cr.execute("""
                SELECT
                    COALESCE(SUM(outstanding_balance), 0) AS total_ar,
                    COUNT(*) FILTER (WHERE over_limit)    AS over_limit,
                    COALESCE(SUM(bucket_90plus), 0)       AS ar_90
                FROM fms_report_debtor_aging
                WHERE company_id = %s
            """, (cid,))
            drow = cr.fetchone()
            vals['total_ar']        = drow[0] or 0.0
            vals['over_limit_count'] = drow[1] or 0
            vals['ar_overdue_90']   = drow[2] or 0.0
        except Exception:
            vals['total_ar']        = 0.0
            vals['over_limit_count'] = 0
            vals['ar_overdue_90']   = 0.0

        # ── Row 6: current shift ──────────────────────────────────────────

        cr.execute("""
            SELECT label, supervisor_id
            FROM fms_shift
            WHERE date = %s AND company_id = %s AND state = 'open'
            ORDER BY id DESC LIMIT 1
        """, (today, cid))
        srow = cr.fetchone()
        if srow:
            label = dict(self.env['fms.shift'].fields_get(
                ['label'])['label']['selection']).get(srow[0], srow[0] or '')
            sup = self.env['hr.employee'].browse(srow[1]).name if srow[1] else '—'
            vals['current_shift_label']   = label
            vals['current_supervisor']    = sup
        else:
            vals['current_shift_label']   = 'No open shift'
            vals['current_supervisor']    = '—'

        cr.execute("""
            SELECT COUNT(DISTINCT ac.attendant_id)
            FROM fms_shift_attendant_cash ac
            JOIN fms_shift s ON s.id = ac.shift_id
            WHERE s.date = %s AND s.company_id = %s AND s.state = 'open'
        """, (today, cid))
        vals['current_attendant_count'] = cr.fetchone()[0] or 0

        # Outstanding shortage balance (cumulative negative balance)
        try:
            cr.execute("""
                SELECT COALESCE(ABS(SUM(cumulative_balance)) FILTER (
                    WHERE cumulative_balance < 0
                ), 0)
                FROM fms_report_shortage
                WHERE company_id = %s
            """, (cid,))
            vals['open_shortage_kes'] = cr.fetchone()[0] or 0.0
        except Exception:
            vals['open_shortage_kes'] = 0.0

        return vals
