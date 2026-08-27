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

import json
from odoo import api, fields, models
from datetime import date, timedelta


class FMSOverview(models.TransientModel):
    _name        = 'fms.overview'
    _description = 'Forecourt Overview Dashboard'

    _rec_name = 'display_name'

    display_name = fields.Char(default='Forecourt Overview', readonly=True)

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
    yesterday_sales_kes     = fields.Float('Sales',            readonly=True, digits=(16, 0))
    yesterday_cash_var      = fields.Float('Cash Over/Short',  readonly=True, digits=(16, 2))
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

    total_ar                = fields.Float('Total AR',         readonly=True, digits=(16, 0))
    over_limit_count        = fields.Integer('Over Limit',           readonly=True)
    ar_overdue_90           = fields.Float('90+ Days',         readonly=True, digits=(16, 0))

    # ── Row 6  People ─────────────────────────────────────────────────────────

    current_shift_label     = fields.Char('Current Shift',          readonly=True)
    current_supervisor      = fields.Char('Supervisor',             readonly=True)
    current_attendant_count = fields.Integer('Attendants on Shift', readonly=True)
    open_shortage_kes       = fields.Float('Outstanding Shortages', readonly=True, digits=(16, 0))

    # ── Graph — 30-day daily throughput (L) for dashboard_graph widget ────────
    throughput_graph        = fields.Text('Throughput Graph JSON',  readonly=True)

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

    def _safe_query(self, sql, params, default):
        """Run sql inside a savepoint; return fetchone() or default on any error.

        PostgreSQL aborts the whole transaction on any SQL error. Without a
        savepoint, a single bad query poisons every subsequent cr.execute() call
        with 'current transaction is aborted'.  We wrap each optional / view-
        backed query in its own savepoint so failures are silently isolated.
        """
        cr = self.env.cr
        cr.execute("SAVEPOINT _fms_ov")
        try:
            cr.execute(sql, params)
            result = cr.fetchone()
            cr.execute("RELEASE SAVEPOINT _fms_ov")
            return result
        except Exception:
            cr.execute("ROLLBACK TO SAVEPOINT _fms_ov")
            return default

    @api.model
    def _compute_overview(self):
        cr  = self.env.cr
        today     = date.today()
        yesterday = today - timedelta(days=1)
        ago_7     = today - timedelta(days=7)
        ago_30    = today - timedelta(days=30)
        cid       = self.env.company.id

        vals = {'display_name': 'Forecourt Overview'}

        # ── Row 1: alerts ─────────────────────────────────────────────────

        row = self._safe_query("""
            SELECT COUNT(*) FROM fms_shift
            WHERE state = 'open' AND company_id = %s AND planned_close < NOW()
        """, (cid,), (0,))
        vals['shifts_open_late'] = row[0] or 0

        row = self._safe_query("""
            SELECT COUNT(*) FROM fms_report_residual_exception
            WHERE company_id = %s AND NOT is_allocated
        """, (cid,), (0,))
        vals['open_residuals'] = row[0] or 0

        row = self._safe_query("""
            SELECT COUNT(*) FROM fms_incident
            WHERE company_id = %s
              AND recovery_status NOT IN ('recovered','written_off')
        """, (cid,), (0,))
        vals['unrecovered_incidents'] = row[0] or 0

        row = self._safe_query("""
            SELECT COUNT(*) FROM fms_shift
            WHERE state = 'closed' AND company_id = %s
              AND date >= %s AND ABS(fc_cash_balance) > 0.01
        """, (cid, ago_30), (0,))
        vals['gates_failed'] = row[0] or 0

        vals['any_alert'] = bool(
            vals['shifts_open_late'] or
            vals['open_residuals'] or
            vals['unrecovered_incidents']
        )

        # ── Row 2: yesterday ──────────────────────────────────────────────

        vals['yesterday_date'] = yesterday

        row = self._safe_query("""
            SELECT COUNT(*),
                   COALESCE(SUM(total_meter_sales), 0),
                   COALESCE(SUM(fc_cash_balance),   0)
            FROM fms_shift
            WHERE date = %s AND company_id = %s AND state = 'closed'
        """, (yesterday, cid), (0, 0.0, 0.0))
        vals['yesterday_shifts']    = row[0] or 0
        vals['yesterday_sales_kes'] = float(row[1] or 0)
        vals['yesterday_cash_var']  = float(row[2] or 0)

        row = self._safe_query("""
            SELECT COALESCE(SUM(me.qty_sold_elec), 0)
            FROM fms_shift_meter_entry me
            JOIN fms_shift s ON s.id = me.shift_id
            WHERE s.date = %s AND s.company_id = %s AND s.state = 'closed'
        """, (yesterday, cid), (0.0,))
        vals['yesterday_throughput_l'] = float(row[0] or 0)

        row = self._safe_query("""
            SELECT COALESCE(SUM(me.qty_sold_elec), 0) / 7.0
            FROM fms_shift_meter_entry me
            JOIN fms_shift s ON s.id = me.shift_id
            WHERE s.date >= %s AND s.date < %s
              AND s.company_id = %s AND s.state = 'closed'
        """, (ago_7, yesterday, cid), (0.0,))
        avg_7 = float(row[0] or 0)
        vals['yesterday_throughput_vs'] = (
            round((vals['yesterday_throughput_l'] - avg_7) / avg_7 * 100, 1)
            if avg_7 > 0 else 0.0
        )

        wrow = self._safe_query("""
            SELECT tank_name, variance_pct
            FROM fms_report_wetstock
            WHERE company_id = %s AND shift_date >= %s
            ORDER BY ABS(variance_pct) DESC NULLS LAST
            LIMIT 1
        """, (cid, ago_7), None)
        if wrow:
            pct = abs(float(wrow[1] or 0))
            vals['worst_tank_name']        = wrow[0]
            vals['worst_variance_pct']     = pct
            vals['worst_variance_verdict'] = (
                'breach' if pct > 1.0 else 'warn' if pct > 0.5 else 'ok'
            )
        else:
            vals['worst_tank_name']        = '—'
            vals['worst_variance_pct']     = 0.0
            vals['worst_variance_verdict'] = 'ok'

        # ── Row 3: reorder count ──────────────────────────────────────────

        row = self._safe_query("""
            SELECT COUNT(*) FROM fms_report_stock_position
            WHERE company_id = %s AND reorder_flag = TRUE
        """, (cid,), (0,))
        vals['reorder_tank_count'] = row[0] or 0

        # ── Row 5: debtors (fms_accounting optional) ──────────────────────

        drow = self._safe_query("""
            SELECT COALESCE(SUM(balance), 0),
                   COUNT(*) FILTER (WHERE over_limit),
                   COALESCE(SUM(bucket_90_plus), 0)
            FROM fms_report_debtor_aging
            WHERE company_id = %s
        """, (cid,), (0.0, 0, 0.0))
        vals['total_ar']         = float(drow[0] or 0)
        vals['over_limit_count'] = drow[1] or 0
        vals['ar_overdue_90']    = float(drow[2] or 0)

        # ── Row 6: current shift ──────────────────────────────────────────

        srow = self._safe_query("""
            SELECT label, supervisor_id
            FROM fms_shift
            WHERE date = %s AND company_id = %s AND state = 'open'
            ORDER BY id DESC LIMIT 1
        """, (today, cid), None)
        if srow:
            label_map = dict(
                self.env['fms.shift'].fields_get(['label'])['label']['selection']
            )
            sup = (self.env['hr.employee'].browse(srow[1]).name
                   if srow[1] else '—')
            vals['current_shift_label'] = label_map.get(srow[0], srow[0] or '')
            vals['current_supervisor']  = sup
        else:
            vals['current_shift_label'] = 'No open shift'
            vals['current_supervisor']  = '—'

        row = self._safe_query("""
            SELECT COUNT(DISTINCT ac.attendant_id)
            FROM fms_shift_attendant_cash ac
            JOIN fms_shift s ON s.id = ac.shift_id
            WHERE s.date = %s AND s.company_id = %s AND s.state = 'open'
        """, (today, cid), (0,))
        vals['current_attendant_count'] = row[0] or 0

        row = self._safe_query("""
            SELECT COALESCE(ABS(SUM(cumulative_balance) FILTER (WHERE cumulative_balance < 0)), 0)
            FROM fms_report_shortage
            WHERE company_id = %s
        """, (cid,), (0.0,))
        vals['open_shortage_kes'] = float(row[0] or 0)

        # ── 30-day throughput graph (L per day) ───────────────────────────
        graph_rows = []
        try:
            cr.execute("""
                SELECT s.date::text, COALESCE(SUM(me.qty_sold_elec), 0)
                FROM fms_shift s
                LEFT JOIN fms_shift_meter_entry me ON me.shift_id = s.id
                WHERE s.company_id = %s AND s.state = 'closed'
                  AND s.date >= %s
                GROUP BY s.date ORDER BY s.date
            """, (cid, ago_30))
            graph_rows = [{'x': r[0], 'y': float(r[1])} for r in cr.fetchall()]
        except Exception:
            pass
        vals['throughput_graph'] = json.dumps([{
            'values': graph_rows,
            'title': 'Throughput (L)',
            'key': 'throughput',
            'area': True,
        }])

        return vals
