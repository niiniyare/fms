"""
fms_report_views.py — _auto=False SQL views backing operational reports.

R2  fms.report.daily.station        — Daily Station Report (shift → product)
R3  fms.report.wetstock             — Wetstock Reconciliation (tank → day)
R4  fms.report.attendant.sales      — Attendant Sales & Cash (attendant × shift)
R5  fms.report.stock.position       — Stock Position & Days of Cover
R7  fms.report.meter.variance       — Meter Variance Log (nozzle × shift)
R10 fms.report.residual.exception   — Attribution Residuals (shift × product)
R16 fms.report.gl.reconciliation    — GL Reconciliation Journal
R19 fms.report.sales.summary        — Sales Summary (nozzle × shift)
R21 fms.report.throughput           — Throughput Trend (day × product)
R22 fms.report.nozzle.perf         — Pump & Nozzle Performance
R25 fms.report.attendant.category   — Attendant Sales by Category
R26 fms.report.shortage             — Shortage & Overage Ledger
R27 fms.report.attendant.perf       — Attendant Performance
R28 fms.report.risk.anomaly         — Attendant Risk & Anomaly
R29 fms.report.nozzle.handover      — Nozzle Assignment & Handover Log
"""

from odoo import models, fields, api, tools


class FMSReportDailyStation(models.Model):
    """
    R2 · Daily Station Report.
    One row per shift × product.  Used for the on-screen pivot and the
    QWeb daily report.  Date filter is always shift date, never create_date.
    """

    _name = 'fms.report.daily.station'
    _description = 'Daily Station Report'
    _auto = False
    _order = 'shift_date desc, shift_label, product_name'

    # ── Dimensions ────────────────────────────────────────────────────
    shift_id       = fields.Many2one('fms.shift',       'Shift',      readonly=True)
    shift_date     = fields.Date(                        'Date',       readonly=True)
    shift_label    = fields.Selection([
        ('day',     'Day'),
        ('evening', 'Evening'),
        ('night',   'Night'),
    ], string='Period', readonly=True)
    product_id     = fields.Many2one('product.product', 'Product',    readonly=True)
    product_name   = fields.Char(                        'Product (SQL)',   readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)
    supervisor_id  = fields.Many2one('hr.employee',     'Supervisor', readonly=True)

    # ── Measures ──────────────────────────────────────────────────────
    qty_litres     = fields.Float('Volume (L)',          readonly=True, digits=(16, 2))
    amount_kes     = fields.Float('Sales',         readonly=True, digits=(16, 2))
    rtt_volume     = fields.Float('RTT (L)',             readonly=True, digits=(16, 2))
    shift_count    = fields.Integer('Shifts',            readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_daily_station AS (
                SELECT
                    me.id                                   AS id,
                    me.shift_id                             AS shift_id,
                    s.date                                  AS shift_date,
                    s.label                                 AS shift_label,
                    me.product_id                           AS product_id,
                    pp.default_code || ' ' || pt.name::text AS product_name,
                    s.company_id                            AS company_id,
                    s.supervisor_id                         AS supervisor_id,
                    COALESCE(me.qty_sold_elec, 0)           AS qty_litres,
                    COALESCE(me.amount_elec, 0)             AS amount_kes,
                    COALESCE(me.rtt_volume, 0)              AS rtt_volume,
                    1                                       AS shift_count
                FROM fms_shift_meter_entry me
                JOIN fms_shift s             ON s.id = me.shift_id
                JOIN product_product pp      ON pp.id = me.product_id
                JOIN product_template pt     ON pt.id = pp.product_tmpl_id
                WHERE s.state = 'closed'
            )
        """)


class FMSReportAttendantSales(models.Model):
    """
    R4 · Attendant Sales & Cash.
    One row per attendant × shift.  Shortage = balance (negative = over-declared).
    """

    _name = 'fms.report.attendant.sales'
    _description = 'Attendant Sales & Cash'
    _auto = False
    _order = 'shift_date desc, attendant_name'

    # ── Dimensions ────────────────────────────────────────────────────
    shift_id       = fields.Many2one('fms.shift',       'Shift',      readonly=True)
    shift_date     = fields.Date(                        'Date',       readonly=True)
    shift_label    = fields.Selection([
        ('day',     'Day'),
        ('evening', 'Evening'),
        ('night',   'Night'),
    ], string='Period', readonly=True)
    attendant_id   = fields.Many2one('hr.employee',     'Attendant',  readonly=True)
    attendant_name = fields.Char('Attendant (SQL)', readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)

    # ── Measures ──────────────────────────────────────────────────────
    reported_sales = fields.Float('Reported Sales', readonly=True, digits=(16, 2))
    mpesa_amount   = fields.Float('MPesa',          readonly=True, digits=(16, 2))
    card_amount    = fields.Float('Card',            readonly=True, digits=(16, 2))
    ar_amount      = fields.Float('AR',              readonly=True, digits=(16, 2))
    expense_amount = fields.Float('Expenses',        readonly=True, digits=(16, 2))
    cash_collected = fields.Float('Cash Dropped',    readonly=True, digits=(16, 2))
    balance        = fields.Float('Shortage / Overage',    readonly=True, digits=(16, 2))
    shift_count    = fields.Integer('Shifts',              readonly=True)

    def init(self):
        # mpesa_amount, card_amount, ar_amount, expense_amount, balance are computed
        # (non-stored) — use 0 placeholders; real values load via Python compute.
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_attendant_sales AS (
                SELECT
                    ac.id                                   AS id,
                    ac.shift_id                             AS shift_id,
                    s.date                                  AS shift_date,
                    s.label                                 AS shift_label,
                    ac.attendant_id                         AS attendant_id,
                    e.name                                  AS attendant_name,
                    s.company_id                            AS company_id,
                    COALESCE(ac.reported_sales, 0)          AS reported_sales,
                    0::numeric                              AS mpesa_amount,
                    0::numeric                              AS card_amount,
                    0::numeric                              AS ar_amount,
                    0::numeric                              AS expense_amount,
                    COALESCE(ac.cash_collected, 0)          AS cash_collected,
                    0::numeric                              AS balance,
                    1                                       AS shift_count
                FROM fms_shift_attendant_cash ac
                JOIN fms_shift s             ON s.id = ac.shift_id
                JOIN hr_employee e           ON e.id = ac.attendant_id
                WHERE s.state = 'closed'
            )
        """)


class FMSReportWetstock(models.Model):
    """
    R3 · Wetstock Reconciliation.
    One row per tank × shift date.
    NOTE: volume figures use dip readings directly (mm → L conversion via
    strapping chart is not yet implemented — load calibration tables first).
    """

    _name = 'fms.report.wetstock'
    _description = 'Wetstock Reconciliation'
    _auto = False
    _order = 'shift_date desc, tank_name'

    # ── Dimensions ────────────────────────────────────────────────────
    shift_id      = fields.Many2one('fms.shift',          'Shift',    readonly=True)
    shift_date    = fields.Date(                           'Date',     readonly=True)
    shift_label   = fields.Selection([
        ('day',     'Day'),
        ('evening', 'Evening'),
        ('night',   'Night'),
    ], string='Period', readonly=True)
    tank_id       = fields.Many2one('stock.location',     'Tank',     readonly=True)
    tank_name     = fields.Char(                           'Tank (SQL)',    readonly=True)
    product_id    = fields.Many2one('product.product',    'Product',  readonly=True)
    company_id    = fields.Many2one('res.company',        'Company',  readonly=True)

    # ── Measures ──────────────────────────────────────────────────────
    opening_vol   = fields.Float('Opening (L)',            readonly=True, digits=(16, 2))
    closing_vol   = fields.Float('Closing (L)',            readonly=True, digits=(16, 2))
    metered_sale  = fields.Float('Metered Sale (L)',       readonly=True, digits=(16, 2))
    book_stock    = fields.Float('Book Stock (L)',         readonly=True, digits=(16, 2))
    variance_l    = fields.Float('Variance (L)',           readonly=True, digits=(16, 2))
    variance_pct  = fields.Float('Variance %',             readonly=True, digits=(16, 4))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_wetstock AS (
                SELECT
                    de.id                                               AS id,
                    de.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    de.location_id                                      AS tank_id,
                    sl.complete_name                                    AS tank_name,
                    de.product_id                                       AS product_id,
                    s.company_id                                        AS company_id,
                    COALESCE(de.opening_volume, 0)                      AS opening_vol,
                    COALESCE(de.closing_volume, 0)                      AS closing_vol,
                    -- metered sale: sum of elec qty sold for this product on this shift
                    COALESCE((
                        SELECT SUM(me.qty_sold_elec)
                        FROM fms_shift_meter_entry me
                        WHERE me.shift_id = de.shift_id
                          AND me.product_id = de.product_id
                    ), 0)                                               AS metered_sale,
                    -- book stock: opening + receipts - metered sales (receipts = 0 for now)
                    COALESCE(de.opening_volume, 0) - COALESCE((
                        SELECT SUM(me.qty_sold_elec)
                        FROM fms_shift_meter_entry me
                        WHERE me.shift_id = de.shift_id
                          AND me.product_id = de.product_id
                    ), 0)                                               AS book_stock,
                    -- variance: closing dip minus book stock
                    COALESCE(de.closing_volume, 0) - (
                        COALESCE(de.opening_volume, 0) - COALESCE((
                            SELECT SUM(me.qty_sold_elec)
                            FROM fms_shift_meter_entry me
                            WHERE me.shift_id = de.shift_id
                              AND me.product_id = de.product_id
                        ), 0)
                    )                                                   AS variance_l,
                    COALESCE(de.variance_pct, 0)                        AS variance_pct
                FROM fms_shift_dip_entry de
                JOIN fms_shift s           ON s.id = de.shift_id
                JOIN stock_location sl     ON sl.id = de.location_id
                WHERE s.state = 'closed'
            )
        """)


class FMSReportStockPosition(models.Model):
    """
    R5 · Stock Position & Days of Cover.
    One row per fuel tank.  Refreshed each time the view is queried.
    Reorder alert is raised by ir.cron (fms_stock_alert_cron).
    """

    _name = 'fms.report.stock.position'
    _description = 'Stock Position & Days of Cover'
    _auto = False
    _order = 'days_cover asc nulls first'

    # ── Dimensions ────────────────────────────────────────────────────
    location_id          = fields.Many2one('stock.location', 'Tank',    readonly=True)
    tank_name            = fields.Char(                       'Tank (SQL)',   readonly=True)
    product_id           = fields.Many2one('product.product', 'Product',readonly=True)
    company_id           = fields.Many2one('res.company',     'Company',readonly=True)

    # ── Stock measures ────────────────────────────────────────────────
    current_stock        = fields.Float('Current Stock (L)',   readonly=True, digits=(16, 0))
    tank_capacity        = fields.Float('Capacity (L)',        readonly=True, digits=(16, 0))
    ullage               = fields.Float('Ullage (L)',          readonly=True, digits=(16, 0))

    # ── Run rate ──────────────────────────────────────────────────────
    run_rate_7d          = fields.Float('Run Rate 7d (L/day)', readonly=True, digits=(16, 0))
    run_rate_30d         = fields.Float('Run Rate 30d (L/day)',readonly=True, digits=(16, 0))

    # ── Cover ─────────────────────────────────────────────────────────
    days_cover           = fields.Float('Days of Cover',       readonly=True, digits=(16, 1))
    reorder_point_days   = fields.Float('Reorder Point (days)',readonly=True, digits=(16, 1))
    reorder_flag         = fields.Boolean('Below Reorder Point',readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_stock_position AS (
                SELECT
                    sl.id                                           AS id,
                    sl.id                                           AS location_id,
                    sl.complete_name                                AS tank_name,
                    sl.fms_fuel_product_id                          AS product_id,
                    rc.id                                           AS company_id,
                    -- current stock from Odoo quants
                    COALESCE((
                        SELECT SUM(sq.quantity)
                        FROM stock_quant sq
                        WHERE sq.location_id = sl.id
                          AND sq.product_id  = sl.fms_fuel_product_id
                    ), 0)                                           AS current_stock,
                    COALESCE(sl.fms_tank_capacity_l, 0)             AS tank_capacity,
                    GREATEST(
                        COALESCE(sl.fms_tank_capacity_l, 0) - COALESCE((
                            SELECT SUM(sq.quantity) FROM stock_quant sq
                            WHERE sq.location_id = sl.id
                              AND sq.product_id  = sl.fms_fuel_product_id
                        ), 0),
                        0
                    )                                               AS ullage,
                    -- 7-day run rate
                    COALESCE((
                        SELECT SUM(me.qty_sold_elec) / 7.0
                        FROM fms_shift_meter_entry me
                        JOIN fms_shift s ON s.id = me.shift_id
                        WHERE me.product_id = sl.fms_fuel_product_id
                          AND s.date >= CURRENT_DATE - INTERVAL '7 days'
                          AND s.state = 'closed'
                    ), 0)                                           AS run_rate_7d,
                    -- 30-day run rate
                    COALESCE((
                        SELECT SUM(me.qty_sold_elec) / 30.0
                        FROM fms_shift_meter_entry me
                        JOIN fms_shift s ON s.id = me.shift_id
                        WHERE me.product_id = sl.fms_fuel_product_id
                          AND s.date >= CURRENT_DATE - INTERVAL '30 days'
                          AND s.state = 'closed'
                    ), 0)                                           AS run_rate_30d,
                    -- days of cover using 7-day run rate (fall back to 30-day)
                    CASE
                        WHEN COALESCE((
                            SELECT SUM(me.qty_sold_elec) / 7.0
                            FROM fms_shift_meter_entry me
                            JOIN fms_shift s ON s.id = me.shift_id
                            WHERE me.product_id = sl.fms_fuel_product_id
                              AND s.date >= CURRENT_DATE - INTERVAL '7 days'
                              AND s.state = 'closed'
                        ), 0) > 0
                        THEN COALESCE((
                            SELECT SUM(sq.quantity) FROM stock_quant sq
                            WHERE sq.location_id = sl.id
                              AND sq.product_id  = sl.fms_fuel_product_id
                        ), 0) / (
                            SELECT SUM(me.qty_sold_elec) / 7.0
                            FROM fms_shift_meter_entry me
                            JOIN fms_shift s ON s.id = me.shift_id
                            WHERE me.product_id = sl.fms_fuel_product_id
                              AND s.date >= CURRENT_DATE - INTERVAL '7 days'
                              AND s.state = 'closed'
                        )
                        ELSE NULL
                    END                                             AS days_cover,
                    COALESCE(sl.fms_reorder_point_days, 3)          AS reorder_point_days,
                    -- reorder flag
                    CASE
                        WHEN COALESCE((
                            SELECT SUM(me.qty_sold_elec) / 7.0
                            FROM fms_shift_meter_entry me
                            JOIN fms_shift s ON s.id = me.shift_id
                            WHERE me.product_id = sl.fms_fuel_product_id
                              AND s.date >= CURRENT_DATE - INTERVAL '7 days'
                              AND s.state = 'closed'
                        ), 0) > 0
                        AND COALESCE((
                            SELECT SUM(sq.quantity) FROM stock_quant sq
                            WHERE sq.location_id = sl.id
                              AND sq.product_id  = sl.fms_fuel_product_id
                        ), 0) / (
                            SELECT SUM(me.qty_sold_elec) / 7.0
                            FROM fms_shift_meter_entry me
                            JOIN fms_shift s ON s.id = me.shift_id
                            WHERE me.product_id = sl.fms_fuel_product_id
                              AND s.date >= CURRENT_DATE - INTERVAL '7 days'
                              AND s.state = 'closed'
                        ) <= COALESCE(sl.fms_reorder_point_days, 3)
                        THEN TRUE
                        ELSE FALSE
                    END                                             AS reorder_flag
                FROM stock_location sl
                CROSS JOIN (SELECT id FROM res_company LIMIT 1) rc
                WHERE sl.fms_is_fuel_tank = TRUE
                  AND sl.fms_fuel_product_id IS NOT NULL
                  AND sl.active = TRUE
            )
        """)

    def action_raise_reorder_activities(self):
        """Called by ir.cron — raise an activity on each tank below reorder point."""
        Activity = self.env['mail.activity']
        activity_type = self.env.ref('mail.mail_activity_data_warning', raise_if_not_found=False)
        if not activity_type:
            activity_type = self.env['mail.activity.type'].search([], limit=1)

        tanks_below = self.search([('reorder_flag', '=', True)])
        for row in tanks_below:
            tank = self.env['stock.location'].browse(row.location_id.id)
            # Avoid duplicate activities: skip if one already exists today
            existing = Activity.search([
                ('res_model', '=', 'stock.location'),
                ('res_id', '=', tank.id),
                ('activity_type_id', '=', activity_type.id),
                ('date_deadline', '=', fields.Date.today()),
            ], limit=1)
            if existing:
                continue
            cover = f"{row.days_cover:.1f}" if row.days_cover is not None else "unknown"
            Activity.create({
                'res_model_id': self.env['ir.model']._get_id('stock.location'),
                'res_id': tank.id,
                'activity_type_id': activity_type.id,
                'summary': f"Reorder {row.product_id.name} — {cover} days cover",
                'note': (
                    f"<p><b>{tank.complete_name}</b> has {cover} days of cover "
                    f"(reorder point: {row.reorder_point_days:.1f} days).<br/>"
                    f"Current stock: {row.current_stock:,.0f} L. "
                    f"7-day run rate: {row.run_rate_7d:,.0f} L/day.</p>"
                ),
                'user_id': self.env.ref('base.user_admin').id,
                'date_deadline': fields.Date.today(),
            })


# ═══════════════════════════════════════════════════════════════════════════════
# R7 · Meter Variance Log
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportMeterVariance(models.Model):
    """R7 — Electronic vs manual variance per nozzle per shift."""

    _name        = 'fms.report.meter.variance'
    _description = 'Meter Variance Log'
    _auto        = False
    _order       = 'shift_date desc, pump_name, nozzle_name'

    shift_id      = fields.Many2one('fms.shift',        'Shift',      readonly=True)
    shift_date    = fields.Date(                         'Date',       readonly=True)
    shift_label   = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    nozzle_id     = fields.Many2one('fms.pump.nozzle',  'Nozzle',     readonly=True)
    nozzle_name   = fields.Char(                         'Nozzle (SQL)',     readonly=True)
    pump_id       = fields.Many2one('fms.pump',          'Pump',       readonly=True)
    pump_name     = fields.Char(                         'Pump (SQL)',       readonly=True)
    attendant_id  = fields.Many2one('hr.employee',       'Attendant',  readonly=True)
    product_id    = fields.Many2one('product.product',   'Product',    readonly=True)
    company_id    = fields.Many2one('res.company',       'Company',    readonly=True)

    qty_sold_elec  = fields.Float('Electronic (L)',      readonly=True, digits=(16, 2))
    qty_sold_man   = fields.Float('Manual (L)',          readonly=True, digits=(16, 2))
    variance_l     = fields.Float('Variance (L)',        readonly=True, digits=(16, 2))
    variance_pct   = fields.Float('Variance %',         readonly=True, digits=(16, 4))
    elec_cash_sold = fields.Float('Cash Meter',    readonly=True, digits=(16, 2))
    rtt_volume     = fields.Float('RTT (L)',             readonly=True, digits=(16, 2))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_meter_variance AS (
                SELECT
                    me.id                                               AS id,
                    me.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    me.nozzle_id                                        AS nozzle_id,
                    n.name                                              AS nozzle_name,
                    n.pump_id                                           AS pump_id,
                    p.name                                              AS pump_name,
                    me.attendant_id                                     AS attendant_id,
                    me.product_id                                       AS product_id,
                    s.company_id                                        AS company_id,
                    COALESCE(me.qty_sold_elec,  0)                      AS qty_sold_elec,
                    COALESCE(me.qty_sold_man,   0)                      AS qty_sold_man,
                    COALESCE(me.qty_sold_man, 0) - COALESCE(me.qty_sold_elec, 0) AS variance_l,
                    CASE
                        WHEN COALESCE(me.qty_sold_elec, 0) > 0
                        THEN (COALESCE(me.qty_sold_man, 0) - COALESCE(me.qty_sold_elec, 0))
                             / me.qty_sold_elec * 100
                        ELSE 0
                    END                                                 AS variance_pct,
                    COALESCE(me.elec_cash_sold, 0)                      AS elec_cash_sold,
                    COALESCE(me.rtt_volume, 0)                          AS rtt_volume
                FROM fms_shift_meter_entry me
                JOIN fms_shift      s ON s.id  = me.shift_id
                JOIN fms_pump_nozzle n ON n.id  = me.nozzle_id
                JOIN fms_pump       p ON p.id  = n.pump_id
                WHERE s.state = 'closed'
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R10 · Attribution Residuals (today's list — diagnostic half blocked on D11)
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportResidualException(models.Model):
    """R10 — Open residuals per shift × product. Diagnostic columns added after D11."""

    _name        = 'fms.report.residual.exception'
    _description = 'Attribution Residuals'
    _auto        = False
    _order       = 'shift_date desc, product_name'

    shift_id       = fields.Many2one('fms.shift',       'Shift',      readonly=True)
    shift_date     = fields.Date(                        'Date',       readonly=True)
    shift_label    = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    product_id     = fields.Many2one('product.product', 'Product',    readonly=True)
    product_name   = fields.Char(                        'Product (SQL)',   readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)
    supervisor_id  = fields.Many2one('hr.employee',     'Supervisor', readonly=True)

    meter_volume   = fields.Float('Meter (L)',           readonly=True, digits=(16, 2))
    volume_residual = fields.Float('Volume Residual (L)', readonly=True, digits=(16, 2))
    cash_residual  = fields.Float('Cash Residual', readonly=True, digits=(16, 2))
    residual_type  = fields.Selection([
        ('none', 'Balanced'),
        ('over', 'Over-invoiced'),
        ('under', 'Under-invoiced'),
    ], string='Type', readonly=True)
    is_allocated   = fields.Boolean('Allocated',         readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_residual_exception AS (
                SELECT
                    ps.id                                               AS id,
                    ps.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    ps.product_id                                       AS product_id,
                    pt.name->>'en_US'                                   AS product_name,
                    s.company_id                                        AS company_id,
                    s.supervisor_id                                     AS supervisor_id,
                    COALESCE(ps.meter_volume, 0)                        AS meter_volume,
                    COALESCE(ps.volume_residual, 0)                     AS volume_residual,
                    COALESCE(ps.cash_residual, 0)                       AS cash_residual,
                    COALESCE(ps.residual_type, 'none')                  AS residual_type,
                    EXISTS (
                        SELECT 1 FROM fms_shift_residual_allocation ra
                        WHERE ra.shift_id = ps.shift_id
                          AND (ra.source_product_id = ps.product_id
                               OR ra.target_product_id = ps.product_id)
                    )                                                   AS is_allocated
                FROM fms_shift_product_sales ps
                JOIN fms_shift         s  ON s.id  = ps.shift_id
                JOIN product_product   pp ON pp.id = ps.product_id
                JOIN product_template  pt ON pt.id = pp.product_tmpl_id
                WHERE s.state = 'closed'
                  AND (ABS(COALESCE(ps.volume_residual, 0)) > 0.5
                       OR ABS(COALESCE(ps.cash_residual, 0)) > 10)
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R16 · GL Reconciliation Journal
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportGLReconciliation(models.Model):
    """R16 — Sales journal entries linked to closed shifts."""

    _name        = 'fms.report.gl.reconciliation'
    _description = 'GL Reconciliation Journal'
    _auto        = False
    _order       = 'shift_date desc, account_code'

    shift_id      = fields.Many2one('fms.shift',          'Shift',       readonly=True)
    shift_date    = fields.Date(                           'Date',        readonly=True)
    shift_label   = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    move_id       = fields.Many2one('account.move',       'Journal Entry', readonly=True)
    move_name     = fields.Char(                           'Entry',       readonly=True)
    account_id    = fields.Many2one('account.account',    'Account',     readonly=True)
    account_code  = fields.Char(                           'Account Code', readonly=True)
    account_name  = fields.Char(                           'Account Name', readonly=True)
    partner_id    = fields.Many2one('res.partner',        'Partner',     readonly=True)
    company_id    = fields.Many2one('res.company',        'Company',     readonly=True)
    debit         = fields.Float('Debit',            readonly=True, digits=(16, 2))
    credit        = fields.Float('Credit',           readonly=True, digits=(16, 2))
    balance       = fields.Float('Balance',          readonly=True, digits=(16, 2))
    label         = fields.Char('Label',                   readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_gl_reconciliation AS (
                SELECT
                    aml.id                                              AS id,
                    s.id                                                AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    aml.move_id                                         AS move_id,
                    am.name                                             AS move_name,
                    aml.account_id                                      AS account_id,
                    aa.code_store->>(s.company_id::text)                AS account_code,
                    aa.name->>'en_US'                                   AS account_name,
                    aml.partner_id                                      AS partner_id,
                    s.company_id                                        AS company_id,
                    COALESCE(aml.debit, 0)                              AS debit,
                    COALESCE(aml.credit, 0)                             AS credit,
                    COALESCE(aml.debit, 0) - COALESCE(aml.credit, 0)   AS balance,
                    aml.name                                            AS label
                FROM fms_shift s
                JOIN account_move      am  ON am.id = s.sales_journal_entry_id
                JOIN account_move_line aml ON aml.move_id = am.id
                JOIN account_account   aa  ON aa.id = aml.account_id
                WHERE s.state = 'closed'
                  AND s.sales_journal_entry_id IS NOT NULL
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R19 · Sales Summary
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportSalesSummary(models.Model):
    """R19 — Granular sales per nozzle × shift. Pivot groups any dimension."""

    _name        = 'fms.report.sales.summary'
    _description = 'Sales Summary'
    _auto        = False
    _order       = 'shift_date desc, product_name, attendant_name'

    shift_id      = fields.Many2one('fms.shift',        'Shift',      readonly=True)
    shift_date    = fields.Date(                         'Date',       readonly=True)
    shift_label   = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    nozzle_id     = fields.Many2one('fms.pump.nozzle',  'Nozzle',     readonly=True)
    nozzle_name   = fields.Char(                         'Nozzle (SQL)',     readonly=True)
    pump_id       = fields.Many2one('fms.pump',          'Pump',       readonly=True)
    pump_name     = fields.Char(                         'Pump (SQL)',       readonly=True)
    attendant_id  = fields.Many2one('hr.employee',       'Attendant',  readonly=True)
    attendant_name = fields.Char('Attendant (SQL)',  readonly=True)
    product_id    = fields.Many2one('product.product',   'Product',    readonly=True)
    product_name  = fields.Char(                         'Product (SQL)',    readonly=True)
    categ_id      = fields.Many2one('product.category',  'Category',   readonly=True)
    company_id    = fields.Many2one('res.company',       'Company',    readonly=True)

    qty_sold_elec  = fields.Float('Volume (L)',           readonly=True, digits=(16, 2))
    elec_cash_sold = fields.Float('Cash Meter',     readonly=True, digits=(16, 2))
    rtt_volume     = fields.Float('RTT (L)',              readonly=True, digits=(16, 2))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_sales_summary AS (
                SELECT
                    me.id                                               AS id,
                    me.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    me.nozzle_id                                        AS nozzle_id,
                    n.name                                              AS nozzle_name,
                    n.pump_id                                           AS pump_id,
                    p.name                                              AS pump_name,
                    me.attendant_id                                     AS attendant_id,
                    e.name                                              AS attendant_name,
                    me.product_id                                       AS product_id,
                    pt.name->>'en_US'                                   AS product_name,
                    pt.categ_id                                         AS categ_id,
                    s.company_id                                        AS company_id,
                    COALESCE(me.qty_sold_elec,  0)                      AS qty_sold_elec,
                    COALESCE(me.elec_cash_sold, 0)                      AS elec_cash_sold,
                    COALESCE(me.rtt_volume,     0)                      AS rtt_volume
                FROM fms_shift_meter_entry me
                JOIN fms_shift         s   ON s.id   = me.shift_id
                JOIN fms_pump_nozzle   n   ON n.id   = me.nozzle_id
                JOIN fms_pump          p   ON p.id   = n.pump_id
                JOIN hr_employee       e   ON e.id   = me.attendant_id
                JOIN product_product   pp  ON pp.id  = me.product_id
                JOIN product_template  pt  ON pt.id  = pp.product_tmpl_id
                WHERE s.state = 'closed'
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R21 · Throughput Trend
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportThroughput(models.Model):
    """R21 — Daily throughput by product; graph-first for trend view."""

    _name        = 'fms.report.throughput'
    _description = 'Throughput Trend'
    _auto        = False
    _order       = 'shift_date desc, product_name'

    shift_date   = fields.Date(                        'Date',     readonly=True)
    product_id   = fields.Many2one('product.product',  'Product',  readonly=True)
    product_name = fields.Char(                         'Product (SQL)', readonly=True)
    company_id   = fields.Many2one('res.company',      'Company',  readonly=True)

    qty_sold     = fields.Float('Volume (L)',            readonly=True, digits=(16, 2))
    cash_total   = fields.Float('Cash Meter',      readonly=True, digits=(16, 2))
    shift_count  = fields.Integer('Shifts',              readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_throughput AS (
                SELECT
                    ROW_NUMBER() OVER ()                                AS id,
                    s.date                                              AS shift_date,
                    me.product_id                                       AS product_id,
                    pt.name->>'en_US'                                   AS product_name,
                    s.company_id                                        AS company_id,
                    SUM(COALESCE(me.qty_sold_elec,  0))                 AS qty_sold,
                    SUM(COALESCE(me.elec_cash_sold, 0))                 AS cash_total,
                    COUNT(DISTINCT me.shift_id)                         AS shift_count
                FROM fms_shift_meter_entry me
                JOIN fms_shift        s  ON s.id  = me.shift_id
                JOIN product_product  pp ON pp.id = me.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE s.state = 'closed'
                GROUP BY s.date, me.product_id, pt.name->>'en_US', s.company_id
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R22 · Pump & Nozzle Performance
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportNozzlePerf(models.Model):
    """R22 — Aggregate performance per nozzle over a date range."""

    _name        = 'fms.report.nozzle.perf'
    _description = 'Pump & Nozzle Performance'
    _auto        = False
    _order       = 'total_qty desc'

    nozzle_id    = fields.Many2one('fms.pump.nozzle',  'Nozzle',   readonly=True)
    nozzle_name  = fields.Char(                         'Nozzle (SQL)',  readonly=True)
    pump_id      = fields.Many2one('fms.pump',          'Pump',    readonly=True)
    pump_name    = fields.Char(                         'Pump (SQL)',    readonly=True)
    product_id   = fields.Many2one('product.product',  'Product',  readonly=True)
    product_name = fields.Char(                         'Product (SQL)', readonly=True)
    company_id   = fields.Many2one('res.company',      'Company',  readonly=True)

    shift_count  = fields.Integer('Shifts',             readonly=True)
    total_qty    = fields.Float('Total Volume (L)',      readonly=True, digits=(16, 0))
    avg_qty      = fields.Float('Avg per Shift (L)',     readonly=True, digits=(16, 0))
    total_cash   = fields.Float('Total Cash',      readonly=True, digits=(16, 0))
    total_rtt    = fields.Float('Total RTT (L)',         readonly=True, digits=(16, 0))
    avg_variance = fields.Float('Avg Mech Variance (L)', readonly=True, digits=(16, 2))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_nozzle_perf AS (
                SELECT
                    n.id                                                AS id,
                    n.id                                                AS nozzle_id,
                    n.name                                              AS nozzle_name,
                    n.pump_id                                           AS pump_id,
                    p.name                                              AS pump_name,
                    n.product_id                                        AS product_id,
                    pt.name->>'en_US'                                   AS product_name,
                    rc.id                                               AS company_id,
                    COUNT(DISTINCT me.shift_id)                         AS shift_count,
                    COALESCE(SUM(me.qty_sold_elec),  0)                 AS total_qty,
                    COALESCE(AVG(me.qty_sold_elec),  0)                 AS avg_qty,
                    COALESCE(SUM(me.elec_cash_sold), 0)                 AS total_cash,
                    COALESCE(SUM(me.rtt_volume),     0)                 AS total_rtt,
                    COALESCE(AVG(
                        COALESCE(me.qty_sold_man, 0) - COALESCE(me.qty_sold_elec, 0)
                    ), 0)                                               AS avg_variance
                FROM fms_pump_nozzle   n
                JOIN fms_pump          p   ON p.id  = n.pump_id
                JOIN product_product   pp  ON pp.id = n.product_id
                JOIN product_template  pt  ON pt.id = pp.product_tmpl_id
                CROSS JOIN (SELECT id FROM res_company LIMIT 1) rc
                LEFT JOIN fms_shift_meter_entry me ON me.nozzle_id = n.id
                LEFT JOIN fms_shift s ON s.id = me.shift_id AND s.state = 'closed'
                WHERE n.active = TRUE
                GROUP BY n.id, n.name, n.pump_id, p.name, n.product_id, pt.name->>'en_US', rc.id
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R25 · Attendant Sales by Category
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportAttendantCategory(models.Model):
    """R25 — Attendant sales at nozzle × shift granularity (fuel only until D11)."""

    _name        = 'fms.report.attendant.category'
    _description = 'Attendant Sales by Category'
    _auto        = False
    _order       = 'shift_date desc, attendant_name, product_name'

    shift_id       = fields.Many2one('fms.shift',        'Shift',      readonly=True)
    shift_date     = fields.Date(                         'Date',       readonly=True)
    shift_label    = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    attendant_id   = fields.Many2one('hr.employee',      'Attendant',  readonly=True)
    attendant_name = fields.Char('Attendant (SQL)', readonly=True)
    nozzle_id      = fields.Many2one('fms.pump.nozzle',  'Nozzle',    readonly=True)
    nozzle_name    = fields.Char(                         'Nozzle (SQL)',    readonly=True)
    product_id     = fields.Many2one('product.product',  'Product',    readonly=True)
    product_name   = fields.Char(                         'Product (SQL)',   readonly=True)
    categ_id       = fields.Many2one('product.category', 'Category',   readonly=True)
    company_id     = fields.Many2one('res.company',      'Company',    readonly=True)

    qty_sold_elec  = fields.Float('Volume (L)',            readonly=True, digits=(16, 2))
    elec_cash_sold = fields.Float('Value',           readonly=True, digits=(16, 2))
    rtt_volume     = fields.Float('RTT (L)',               readonly=True, digits=(16, 2))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_attendant_category AS (
                SELECT
                    me.id                                               AS id,
                    me.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    me.attendant_id                                     AS attendant_id,
                    e.name                                              AS attendant_name,
                    me.nozzle_id                                        AS nozzle_id,
                    n.name                                              AS nozzle_name,
                    me.product_id                                       AS product_id,
                    pt.name->>'en_US'                                   AS product_name,
                    pt.categ_id                                         AS categ_id,
                    s.company_id                                        AS company_id,
                    COALESCE(me.qty_sold_elec,  0)                      AS qty_sold_elec,
                    COALESCE(me.elec_cash_sold, 0)                      AS elec_cash_sold,
                    COALESCE(me.rtt_volume,     0)                      AS rtt_volume
                FROM fms_shift_meter_entry me
                JOIN fms_shift         s   ON s.id  = me.shift_id
                JOIN hr_employee       e   ON e.id  = me.attendant_id
                JOIN fms_pump_nozzle   n   ON n.id  = me.nozzle_id
                JOIN product_product   pp  ON pp.id = me.product_id
                JOIN product_template  pt  ON pt.id = pp.product_tmpl_id
                WHERE s.state = 'closed'
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R26 · Shortage & Overage Ledger
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportShortage(models.Model):
    """R26 — Running shortage/overage per attendant with PostgreSQL window function."""

    _name        = 'fms.report.shortage'
    _description = 'Shortage & Overage Ledger'
    _auto        = False
    _order       = 'attendant_name, shift_date'

    shift_id          = fields.Many2one('fms.shift',     'Shift',      readonly=True)
    shift_date        = fields.Date(                      'Date',       readonly=True)
    shift_label       = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    attendant_id      = fields.Many2one('hr.employee',   'Attendant',  readonly=True)
    attendant_name    = fields.Char('Attendant (SQL)', readonly=True)
    supervisor_id     = fields.Many2one('hr.employee',   'Supervisor', readonly=True)
    company_id        = fields.Many2one('res.company',   'Company',    readonly=True)

    reported_sales    = fields.Float('Expected',   readonly=True, digits=(16, 2))
    cash_collected    = fields.Float('Declared',   readonly=True, digits=(16, 2))
    mpesa_amount      = fields.Float('MPesa',      readonly=True, digits=(16, 2))
    card_amount       = fields.Float('Card',       readonly=True, digits=(16, 2))
    ar_amount         = fields.Float('AR',         readonly=True, digits=(16, 2))
    expense_amount    = fields.Float('Expenses',   readonly=True, digits=(16, 2))
    balance           = fields.Float('Shortage/Overage', readonly=True, digits=(16, 2))
    cumulative_balance = fields.Float('Cumulative', readonly=True, digits=(16, 2))

    def init(self):
        # mpesa_amount, card_amount, ar_amount, expense_amount, balance are computed
        # (non-stored) fields — use 0 placeholders; real values load via Python compute.
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_shortage AS (
                SELECT
                    ac.id                                               AS id,
                    ac.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    ac.attendant_id                                     AS attendant_id,
                    e.name                                              AS attendant_name,
                    s.supervisor_id                                     AS supervisor_id,
                    s.company_id                                        AS company_id,
                    COALESCE(ac.reported_sales,  0)                     AS reported_sales,
                    COALESCE(ac.cash_collected,  0)                     AS cash_collected,
                    0::numeric                                          AS mpesa_amount,
                    0::numeric                                          AS card_amount,
                    0::numeric                                          AS ar_amount,
                    0::numeric                                          AS expense_amount,
                    0::numeric                                          AS balance,
                    0::numeric                                          AS cumulative_balance
                FROM fms_shift_attendant_cash ac
                JOIN fms_shift   s ON s.id  = ac.shift_id
                JOIN hr_employee e ON e.id  = ac.attendant_id
                WHERE s.state = 'closed'
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R27 · Attendant Performance
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportAttendantPerf(models.Model):
    """R27 — Aggregated KPIs per attendant × month."""

    _name        = 'fms.report.attendant.perf'
    _description = 'Attendant Performance'
    _auto        = False
    _order       = 'total_qty desc'

    attendant_id   = fields.Many2one('hr.employee',   'Attendant',  readonly=True)
    attendant_name = fields.Char('Attendant (SQL)', readonly=True)
    company_id     = fields.Many2one('res.company',   'Company',    readonly=True)

    shift_count    = fields.Integer('Shifts',           readonly=True)
    total_qty      = fields.Float('Volume (L)',          readonly=True, digits=(16, 0))
    avg_qty        = fields.Float('Avg L/shift',         readonly=True, digits=(16, 0))
    total_cash_due = fields.Float('Total Due',     readonly=True, digits=(16, 0))
    total_shortage = fields.Float('Total Shortage', readonly=True, digits=(16, 0))
    shortage_shifts = fields.Integer('Short Shifts',     readonly=True)
    overage_shifts  = fields.Integer('Over Shifts',      readonly=True)
    accuracy_pct    = fields.Float('Cash Accuracy %',    readonly=True, digits=(16, 1))
    total_rtt      = fields.Float('Total RTT (L)',        readonly=True, digits=(16, 0))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_attendant_perf AS (
                SELECT
                    e.id                                                AS id,
                    e.id                                                AS attendant_id,
                    e.name                                              AS attendant_name,
                    rc.id                                               AS company_id,
                    COUNT(DISTINCT ac.shift_id)                         AS shift_count,
                    COALESCE(SUM(me_agg.qty),  0)                       AS total_qty,
                    COALESCE(AVG(me_agg.qty),  0)                       AS avg_qty,
                    COALESCE(SUM(ac.reported_sales), 0)                 AS total_cash_due,
                    0::numeric                                          AS total_shortage,
                    0::bigint                                           AS shortage_shifts,
                    0::bigint                                           AS overage_shifts,
                    100::numeric                                        AS accuracy_pct,
                    COALESCE(SUM(me_agg.rtt), 0)                        AS total_rtt
                FROM hr_employee e
                CROSS JOIN (SELECT id FROM res_company LIMIT 1) rc
                LEFT JOIN fms_shift_attendant_cash ac ON ac.attendant_id = e.id
                LEFT JOIN fms_shift s ON s.id = ac.shift_id AND s.state = 'closed'
                LEFT JOIN LATERAL (
                    SELECT
                        SUM(me.qty_sold_elec) AS qty,
                        SUM(me.rtt_volume)    AS rtt
                    FROM fms_shift_meter_entry me
                    WHERE me.shift_id = ac.shift_id
                      AND me.attendant_id = e.id
                ) me_agg ON TRUE
                WHERE e.fms_is_attendant = TRUE
                GROUP BY e.id, e.name, rc.id
                HAVING COUNT(DISTINCT ac.shift_id) > 0
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R28 · Attendant Risk & Anomaly
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportRiskAnomaly(models.Model):
    """R28 — Per-attendant anomaly summary. Restricted to supervisor+."""

    _name        = 'fms.report.risk.anomaly'
    _description = 'Attendant Risk & Anomaly'
    _auto        = False
    _order       = 'risk_score desc'

    attendant_id      = fields.Many2one('hr.employee', 'Attendant',  readonly=True)
    attendant_name    = fields.Char('Attendant (SQL)', readonly=True)
    company_id        = fields.Many2one('res.company', 'Company',    readonly=True)

    shift_count       = fields.Integer('Shifts Analysed',     readonly=True)
    shortage_shifts   = fields.Integer('Shortage Shifts',      readonly=True)
    consecutive_short = fields.Integer('Max Consecutive Short', readonly=True)
    round_readings    = fields.Integer('Round Meter Readings',  readonly=True)
    high_variance_shifts = fields.Integer('High Mech Variance Shifts', readonly=True)
    rtt_shifts        = fields.Integer('Shifts with RTT',      readonly=True)
    total_shortage    = fields.Float('Total Shortage',    readonly=True, digits=(16, 2))
    avg_shortage      = fields.Float('Avg Shortage/shift', readonly=True, digits=(16, 2))
    risk_score        = fields.Integer('Risk Score',            readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_risk_anomaly AS (
                WITH base AS (
                    SELECT
                        ac.attendant_id,
                        ac.shift_id,
                        s.date                                          AS shift_date,
                        0::numeric                                      AS balance,
                        -- round-number closing elec volume: closing ends in 000
                        COUNT(*) FILTER (
                            WHERE CAST(me.closing_elec_volume AS INTEGER) % 100 = 0
                              AND me.closing_elec_volume > 0
                        )                                               AS round_count,
                        -- high mechanical variance: abs(man-elec) > 10L on any nozzle
                        COUNT(*) FILTER (
                            WHERE ABS(COALESCE(me.qty_sold_man, 0)
                                      - COALESCE(me.qty_sold_elec, 0)) > 10
                        )                                               AS high_var_count,
                        -- RTT activity
                        CASE WHEN SUM(COALESCE(me.rtt_volume, 0)) > 0 THEN 1 ELSE 0 END AS rtt_flag
                    FROM fms_shift_attendant_cash ac
                    JOIN fms_shift s ON s.id = ac.shift_id AND s.state = 'closed'
                    LEFT JOIN fms_shift_meter_entry me
                           ON me.shift_id = ac.shift_id AND me.attendant_id = ac.attendant_id
                    GROUP BY ac.attendant_id, ac.shift_id, s.date
                )
                SELECT
                    e.id                                                AS id,
                    e.id                                                AS attendant_id,
                    e.name                                              AS attendant_name,
                    rc.id                                               AS company_id,
                    COUNT(b.shift_id)                                   AS shift_count,
                    COUNT(*) FILTER (WHERE b.balance < -1)              AS shortage_shifts,
                    -- max consecutive shortage: approximate via dense window ranking
                    COALESCE(MAX(rn.consec), 0)                        AS consecutive_short,
                    COALESCE(SUM(b.round_count), 0)                    AS round_readings,
                    COUNT(*) FILTER (WHERE b.high_var_count > 0)        AS high_variance_shifts,
                    COALESCE(SUM(b.rtt_flag), 0)                        AS rtt_shifts,
                    COALESCE(SUM(
                        CASE WHEN b.balance < 0 THEN ABS(b.balance) ELSE 0 END
                    ), 0)                                               AS total_shortage,
                    CASE
                        WHEN COUNT(*) FILTER (WHERE b.balance < -1) > 0
                        THEN COALESCE(SUM(
                            CASE WHEN b.balance < 0 THEN ABS(b.balance) ELSE 0 END
                        ), 0) / COUNT(*) FILTER (WHERE b.balance < -1)
                        ELSE 0
                    END                                                 AS avg_shortage,
                    -- risk score: shortage_shifts*2 + round_readings + high_variance_shifts*2
                    (   COUNT(*) FILTER (WHERE b.balance < -1) * 2
                      + COALESCE(SUM(b.round_count), 0)
                      + COUNT(*) FILTER (WHERE b.high_var_count > 0) * 2
                    )                                                   AS risk_score
                FROM hr_employee e
                CROSS JOIN (SELECT id FROM res_company LIMIT 1) rc
                LEFT JOIN base b ON b.attendant_id = e.id
                LEFT JOIN LATERAL (
                    SELECT MAX(cnt) AS consec
                    FROM (
                        SELECT COUNT(*) AS cnt
                        FROM base b2
                        WHERE b2.attendant_id = e.id AND b2.balance < -1
                        GROUP BY (
                            SELECT COUNT(*) FROM base b3
                            WHERE b3.attendant_id = e.id
                              AND b3.shift_date <= b2.shift_date
                              AND b3.balance >= -1
                        )
                    ) grp
                ) rn ON TRUE
                WHERE e.fms_is_attendant = TRUE
                GROUP BY e.id, e.name, rc.id
                HAVING COUNT(b.shift_id) > 0
            )
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# R29 · Nozzle Assignment & Handover Log
# ═══════════════════════════════════════════════════════════════════════════════

class FMSReportNozzleHandover(models.Model):
    """R29 — Per-shift nozzle assignment. No handover event model yet (D4 pending)."""

    _name        = 'fms.report.nozzle.handover'
    _description = 'Nozzle Assignment & Handover Log'
    _auto        = False
    _order       = 'shift_date desc, pump_name, nozzle_name'

    shift_id       = fields.Many2one('fms.shift',       'Shift',      readonly=True)
    shift_date     = fields.Date(                        'Date',       readonly=True)
    shift_label    = fields.Selection([
        ('day', 'Day'), ('evening', 'Evening'), ('night', 'Night'),
    ], string='Period', readonly=True)
    nozzle_id      = fields.Many2one('fms.pump.nozzle', 'Nozzle',    readonly=True)
    nozzle_name    = fields.Char(                        'Nozzle (SQL)',    readonly=True)
    pump_id        = fields.Many2one('fms.pump',         'Pump',      readonly=True)
    pump_name      = fields.Char(                        'Pump (SQL)',      readonly=True)
    attendant_id   = fields.Many2one('hr.employee',     'Attendant',  readonly=True)
    attendant_name = fields.Char('Attendant (SQL)', readonly=True)
    product_id     = fields.Many2one('product.product', 'Product',    readonly=True)
    supervisor_id  = fields.Many2one('hr.employee',     'Supervisor', readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)

    opening_vol    = fields.Float('Opening Elec (L)',    readonly=True, digits=(16, 2))
    closing_vol    = fields.Float('Closing Elec (L)',    readonly=True, digits=(16, 2))
    qty_sold       = fields.Float('Volume Sold (L)',     readonly=True, digits=(16, 2))

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_nozzle_handover AS (
                SELECT
                    me.id                                               AS id,
                    me.shift_id                                         AS shift_id,
                    s.date                                              AS shift_date,
                    s.label                                             AS shift_label,
                    me.nozzle_id                                        AS nozzle_id,
                    n.name                                              AS nozzle_name,
                    n.pump_id                                           AS pump_id,
                    p.name                                              AS pump_name,
                    me.attendant_id                                     AS attendant_id,
                    e.name                                              AS attendant_name,
                    me.product_id                                       AS product_id,
                    s.supervisor_id                                     AS supervisor_id,
                    s.company_id                                        AS company_id,
                    COALESCE(me.opening_elec_volume, 0)                 AS opening_vol,
                    COALESCE(me.closing_elec_volume, 0)                 AS closing_vol,
                    COALESCE(me.qty_sold_elec, 0)                       AS qty_sold
                FROM fms_shift_meter_entry me
                JOIN fms_shift         s  ON s.id  = me.shift_id
                JOIN fms_pump_nozzle   n  ON n.id  = me.nozzle_id
                JOIN fms_pump          p  ON p.id  = n.pump_id
                JOIN hr_employee       e  ON e.id  = me.attendant_id
                WHERE s.state = 'closed'
            )
        """)


# =============================================================================
# FIN-008: Attendant Cash Breakdown Report
# Per attendant per shift: fuel sales, customer receipts, floats, drops,
# vendor payments, expenses, declared cash, expected, variance.
# =============================================================================

class FMSReportAttendantCashBreakdown(models.Model):
    """
    R27: Per-attendant cash breakdown for a closed shift.
    Joins fms.shift.attendant.cash with account.payment aggregations.
    Read-only SQL view — source of truth is always the source records.

    FIN-008 requirement: show all transaction types in one line per attendant.
    """
    _name        = 'fms.report.attendant.cash.breakdown'
    _description = 'Attendant Cash Breakdown Report (FIN-008)'
    _auto        = False
    _order       = 'shift_date DESC, attendant_name'

    id              = fields.Integer('ID',          readonly=True)
    shift_id        = fields.Many2one('fms.shift',  'Shift',      readonly=True)
    shift_date      = fields.Date('Shift Date',                   readonly=True)
    shift_label     = fields.Char('Shift (SQL)',                   readonly=True)
    company_id      = fields.Many2one('res.company', 'Station',   readonly=True)
    attendant_id    = fields.Many2one('hr.employee', 'Attendant', readonly=True)
    attendant_name  = fields.Char('Attendant (SQL)',               readonly=True)

    # ── Revenue sources ───────────────────────────────────────────────
    meter_sales         = fields.Float('Meter Sales (KES)',        readonly=True, digits=(16, 2))
    customer_receipts   = fields.Float('Customer Receipts (KES)', readonly=True, digits=(16, 2))
    float_received      = fields.Float('Float Received (KES)',    readonly=True, digits=(16, 2))
    cash_drops          = fields.Float('Cash Drops (KES)',         readonly=True, digits=(16, 2))
    mpesa               = fields.Float('MPesa (KES)',              readonly=True, digits=(16, 2))
    card                = fields.Float('Card (KES)',               readonly=True, digits=(16, 2))
    ar_credit           = fields.Float('AR / Credit (KES)',        readonly=True, digits=(16, 2))

    # ── Outgoings ─────────────────────────────────────────────────────
    vendor_payments     = fields.Float('Vendor Payments (KES)',    readonly=True, digits=(16, 2))
    expenses            = fields.Float('Expenses (KES)',           readonly=True, digits=(16, 2))

    # ── Declared vs expected ──────────────────────────────────────────
    cash_declared       = fields.Float('Cash Declared (KES)',      readonly=True, digits=(16, 2))
    expected_cash       = fields.Float('Expected Cash (KES)',      readonly=True, digits=(16, 2))
    variance            = fields.Float('Variance (KES)',           readonly=True, digits=(16, 2))
    is_balanced         = fields.Boolean('Balanced',               readonly=True)

    def init(self):
        # Check if fms_accounting is installed (account_payment.fms_shift_id exists).
        # When fms is installed standalone (no fms_accounting), use a simplified view
        # with zeros for payment-based columns.
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'account_payment' AND column_name = 'fms_shift_id'
            LIMIT 1
        """)
        has_fms_accounting = bool(self.env.cr.fetchone())

        if has_fms_accounting:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW fms_report_attendant_cash_breakdown AS (
                    SELECT
                        ac.id                                                          AS id,
                        ac.shift_id                                                    AS shift_id,
                        s.date                                                         AS shift_date,
                        s.label                                                        AS shift_label,
                        s.company_id                                                   AS company_id,
                        ac.attendant_id                                                AS attendant_id,
                        e.name                                                         AS attendant_name,
                        COALESCE(ac.reported_sales, 0)                                 AS meter_sales,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.fms_shift_id = ac.shift_id
                              AND ap.fms_attendant_id = ac.attendant_id
                              AND ap.fms_payment_context = 'customer_receipt'
                              AND ap.state = 'posted'
                              AND ap.payment_type = 'inbound'
                        ), 0)                                                          AS customer_receipts,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.fms_shift_id = ac.shift_id
                              AND (ap.fms_attendant_id = ac.attendant_id OR ap.fms_attendant_id IS NULL)
                              AND ap.fms_payment_context = 'cash_float'
                              AND ap.state = 'posted'
                        ), 0)                                                          AS float_received,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.fms_shift_id = ac.shift_id
                              AND (ap.fms_attendant_id = ac.attendant_id OR ap.fms_attendant_id IS NULL)
                              AND ap.fms_payment_context IN ('cash_drop', 'cash_pickup')
                              AND ap.state = 'posted'
                        ), 0)                                                          AS cash_drops,
                        COALESCE(ac.mpesa_amount, 0)                                   AS mpesa,
                        COALESCE(ac.card_amount, 0)                                    AS card,
                        COALESCE(ac.ar_amount, 0)                                      AS ar_credit,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.fms_shift_id = ac.shift_id
                              AND ap.fms_attendant_id = ac.attendant_id
                              AND ap.fms_payment_context = 'vendor_payment'
                              AND ap.state = 'posted'
                        ), 0)                                                          AS vendor_payments,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.fms_shift_id = ac.shift_id
                              AND ap.fms_attendant_id = ac.attendant_id
                              AND ap.fms_payment_context = 'expense'
                              AND ap.state = 'posted'
                        ), 0)                                                          AS expenses,
                        COALESCE(ac.cash_collected, 0)                                 AS cash_declared,
                        COALESCE(ac.total_in, 0)                                       AS expected_cash,
                        COALESCE(ac.balance, 0)                                        AS variance,
                        ABS(COALESCE(ac.balance, 0)) < 0.01                            AS is_balanced
                    FROM fms_shift_attendant_cash ac
                    JOIN fms_shift   s ON s.id  = ac.shift_id
                    JOIN hr_employee e ON e.id  = ac.attendant_id
                )
            """)
        else:
            # Simplified view: no account_payment subqueries (fms_accounting not installed)
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW fms_report_attendant_cash_breakdown AS (
                    SELECT
                        ac.id                          AS id,
                        ac.shift_id                    AS shift_id,
                        s.date                         AS shift_date,
                        s.label                        AS shift_label,
                        s.company_id                   AS company_id,
                        ac.attendant_id                AS attendant_id,
                        e.name                         AS attendant_name,
                        COALESCE(ac.reported_sales, 0) AS meter_sales,
                        0::numeric                     AS customer_receipts,
                        0::numeric                     AS float_received,
                        0::numeric                     AS cash_drops,
                        COALESCE(ac.mpesa_amount, 0)   AS mpesa,
                        COALESCE(ac.card_amount, 0)    AS card,
                        COALESCE(ac.ar_amount, 0)      AS ar_credit,
                        0::numeric                     AS vendor_payments,
                        0::numeric                     AS expenses,
                        COALESCE(ac.cash_collected, 0) AS cash_declared,
                        COALESCE(ac.total_in, 0)       AS expected_cash,
                        COALESCE(ac.balance, 0)        AS variance,
                        ABS(COALESCE(ac.balance, 0)) < 0.01 AS is_balanced
                    FROM fms_shift_attendant_cash ac
                    JOIN fms_shift   s ON s.id  = ac.shift_id
                    JOIN hr_employee e ON e.id  = ac.attendant_id
                )
            """)


# =============================================================================
# E5.2: Cash Reconciliation Report — shift-level physical cash accountability
# =============================================================================

class FMSReportCashReconciliation(models.Model):
    """
    R28: Shift-level cash reconciliation report.
    Aggregates across all attendants for a shift.
    Every amount is traceable to its source transaction type.
    Read-only SQL view.
    """
    _name        = 'fms.report.cash.reconciliation'
    _description = 'Cash Reconciliation Report (E5.2)'
    _auto        = False
    _order       = 'shift_date DESC, attendant_name'

    id             = fields.Integer('ID',            readonly=True)
    shift_id       = fields.Many2one('fms.shift',    'Shift',         readonly=True)
    shift_date     = fields.Date('Shift Date',                        readonly=True)
    shift_label    = fields.Char('Shift (SQL)',                        readonly=True)
    company_id     = fields.Many2one('res.company',  'Station',       readonly=True)
    attendant_id   = fields.Many2one('hr.employee',  'Attendant',     readonly=True)
    attendant_name = fields.Char('Attendant (SQL)',                    readonly=True)

    # ── Inflows ───────────────────────────────────────────────────────────────
    meter_cash_sales   = fields.Float('Meter Cash Sales (KES)',   readonly=True, digits=(16, 2),
        help="elec_cash_sold from pump meters — expected cash from fuel dispensed.")
    direct_cash_sales  = fields.Float('Direct Cash Sales (KES)',  readonly=True, digits=(16, 2),
        help="Posted out_receipt (cash journal) for non-fuel products (carwash, LPG, misc).")
    customer_receipts  = fields.Float('Customer Receipts (KES)', readonly=True, digits=(16, 2),
        help="account.payment inbound, fms_payment_context=customer_receipt, posted.")
    float_in           = fields.Float('Float Received (KES)',     readonly=True, digits=(16, 2),
        help="Cash floats issued to this attendant.")

    # ── Outflows (reduce physical cash holding) ───────────────────────────────
    digital_payments   = fields.Float('Digital Payments (KES)',  readonly=True, digits=(16, 2),
        help="MPesa + Card + digital receipts — no physical cash exchange.")
    credit_sales       = fields.Float('Credit Sales (KES)',      readonly=True, digits=(16, 2),
        help="AR sales (out_invoice or out_receipt on credit) — no physical cash.")
    cash_drops         = fields.Float('Cash Drops (KES)',        readonly=True, digits=(16, 2),
        help="Mid-shift drops to safe — reduces expected holding.")
    expenses_paid      = fields.Float('Expenses Paid (KES)',     readonly=True, digits=(16, 2),
        help="Expenses paid from shift cash.")
    vendor_payments    = fields.Float('Vendor Payments (KES)',   readonly=True, digits=(16, 2),
        help="Vendor payments made from shift cash.")

    # ── Expected vs declared ──────────────────────────────────────────────────
    expected_cash  = fields.Float('Expected Cash (KES)',  readonly=True, digits=(16, 2),
        help="Inflows minus non-cash outflows = physical cash the attendant should hold.")
    declared_cash  = fields.Float('Declared Cash (KES)', readonly=True, digits=(16, 2),
        help="cash_collected — what the attendant physically handed over.")
    variance       = fields.Float('Variance (KES)',       readonly=True, digits=(16, 2),
        help="expected_cash - declared_cash. Must be 0.")
    is_balanced    = fields.Boolean('Balanced',           readonly=True)

    def init(self):
        # Graceful degradation: payment columns require fms_accounting
        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'account_payment' AND column_name = 'fms_shift_id'
            LIMIT 1
        """)
        has_fms_acc = bool(self.env.cr.fetchone())

        self.env.cr.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'account_move' AND column_name = 'fms_payment_classification'
            LIMIT 1
        """)
        has_receipt_cls = bool(self.env.cr.fetchone())

        if has_fms_acc and has_receipt_cls:
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW fms_report_cash_reconciliation AS (
                    SELECT
                        ac.id                                                    AS id,
                        ac.shift_id                                              AS shift_id,
                        s.date                                                   AS shift_date,
                        s.label                                                  AS shift_label,
                        s.company_id                                             AS company_id,
                        ac.attendant_id                                          AS attendant_id,
                        e.name                                                   AS attendant_name,

                        -- Fuel cash from pump meters
                        COALESCE(ac.reported_sales, 0)                           AS meter_cash_sales,

                        -- Dry-stock cash receipts (out_receipt, cash journal, non-fuel)
                        COALESCE(ac.direct_sales_cash, 0)                        AS direct_cash_sales,

                        -- Customer receipts (outstanding invoices paid)
                        COALESCE(ac.customer_receipt_amount, 0)                  AS customer_receipts,

                        -- Cash floats received
                        COALESCE(ac.float_amount, 0)                             AS float_in,

                        -- Digital payments (mpesa + card + digital receipts)
                        COALESCE(ac.mpesa_amount, 0)
                        + COALESCE(ac.card_amount, 0)
                        + COALESCE(ac.direct_sales_digital, 0)                   AS digital_payments,

                        -- Credit/AR sales (no physical cash)
                        COALESCE(ac.ar_amount, 0)
                        + COALESCE(ac.direct_sales_credit, 0)                    AS credit_sales,

                        -- Cash drops to safe
                        COALESCE(ac.cash_drop_amount, 0)                         AS cash_drops,

                        -- Expenses from shift cash
                        COALESCE(ac.expense_amount, 0)                           AS expenses_paid,

                        -- Vendor payments from shift cash
                        COALESCE(ac.vendor_payment_amount, 0)                    AS vendor_payments,

                        -- Expected = total_in (pre-computed, stored)
                        COALESCE(ac.total_in, 0)                                 AS expected_cash,

                        -- Declared = cash handed over
                        COALESCE(ac.cash_collected, 0)                           AS declared_cash,

                        -- Variance
                        COALESCE(ac.balance, 0)                                  AS variance,

                        ABS(COALESCE(ac.balance, 0)) < 0.01                      AS is_balanced

                    FROM fms_shift_attendant_cash ac
                    JOIN fms_shift   s ON s.id  = ac.shift_id
                    JOIN hr_employee e ON e.id  = ac.attendant_id
                )
            """)
        else:
            # Simplified view without fms_accounting payment columns
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW fms_report_cash_reconciliation AS (
                    SELECT
                        ac.id                                    AS id,
                        ac.shift_id                              AS shift_id,
                        s.date                                   AS shift_date,
                        s.label                                  AS shift_label,
                        s.company_id                             AS company_id,
                        ac.attendant_id                          AS attendant_id,
                        e.name                                   AS attendant_name,
                        COALESCE(ac.reported_sales, 0)           AS meter_cash_sales,
                        0::numeric                               AS direct_cash_sales,
                        0::numeric                               AS customer_receipts,
                        0::numeric                               AS float_in,
                        COALESCE(ac.mpesa_amount, 0)
                        + COALESCE(ac.card_amount, 0)            AS digital_payments,
                        COALESCE(ac.ar_amount, 0)                AS credit_sales,
                        0::numeric                               AS cash_drops,
                        0::numeric                               AS expenses_paid,
                        0::numeric                               AS vendor_payments,
                        COALESCE(ac.total_in, 0)                 AS expected_cash,
                        COALESCE(ac.cash_collected, 0)           AS declared_cash,
                        COALESCE(ac.balance, 0)                  AS variance,
                        ABS(COALESCE(ac.balance, 0)) < 0.01      AS is_balanced
                    FROM fms_shift_attendant_cash ac
                    JOIN fms_shift   s ON s.id  = ac.shift_id
                    JOIN hr_employee e ON e.id  = ac.attendant_id
                )
            """)


# =============================================================================
# E5.3: Meter Reconciliation Report — per-nozzle three-meter variance
# =============================================================================

class FMSReportMeterReconciliation(models.Model):
    """
    R29: Per-nozzle meter reconciliation for a closed shift.
    Shows electronic vs manual vs cash-meter discrepancies.
    Read-only SQL view — source of truth is fms_shift_meter_entry.

    Gate thresholds:
      elec vs manual: > 1L = blocking error
      elec vs cash:   > site_preferences.elec_vs_cash_threshold_l = blocking error
    """
    _name        = 'fms.report.meter.reconciliation'
    _description = 'Meter Reconciliation Report (E5.3)'
    _auto        = False
    _order       = 'shift_date DESC, pump_name, nozzle_name'

    id              = fields.Integer('ID',               readonly=True)
    shift_id        = fields.Many2one('fms.shift',       'Shift',           readonly=True)
    shift_date      = fields.Date('Shift Date',                             readonly=True)
    shift_label     = fields.Char('Shift (SQL)',                             readonly=True)
    company_id      = fields.Many2one('res.company',     'Station',         readonly=True)
    pump_id         = fields.Many2one('fms.pump',        'Pump',            readonly=True)
    pump_name       = fields.Char('Pump (SQL)',                              readonly=True)
    nozzle_id       = fields.Many2one('fms.pump.nozzle', 'Nozzle',         readonly=True)
    nozzle_name     = fields.Char('Nozzle (SQL)',                           readonly=True)
    product_id      = fields.Many2one('product.product', 'Product',        readonly=True)
    attendant_id    = fields.Many2one('hr.employee',     'Attendant',       readonly=True)

    # ── Electronic meter ─────────────────────────────────────────────────────
    elec_open       = fields.Float('Elec Opening (L)',   readonly=True, digits=(16, 3))
    elec_close      = fields.Float('Elec Closing (L)',   readonly=True, digits=(16, 3))
    elec_sold       = fields.Float('Elec Sold (L)',      readonly=True, digits=(16, 3))
    elec_cash_sold  = fields.Float('Elec Cash (KES)',    readonly=True, digits=(16, 2))

    # ── Manual mechanical meter ───────────────────────────────────────────────
    man_open        = fields.Float('Manual Opening (L)', readonly=True, digits=(16, 3))
    man_close       = fields.Float('Manual Closing (L)', readonly=True, digits=(16, 3))
    man_sold        = fields.Float('Manual Sold (L)',    readonly=True, digits=(16, 3))

    # ── Variances ─────────────────────────────────────────────────────────────
    elec_vs_man_var = fields.Float('Elec/Manual Variance (L)', readonly=True, digits=(16, 3),
        help="Electronic − Manual dispensed. > ±1L triggers Gate G1 block.")
    elec_vs_man_abs = fields.Float('|Elec/Manual| (L)',        readonly=True, digits=(16, 3))
    man_gate_ok     = fields.Boolean('Manual Gate OK',         readonly=True,
        help="True if |elec − manual| ≤ 1L.")

    # ── Status ────────────────────────────────────────────────────────────────
    shift_state     = fields.Char('Shift Status (SQL)',         readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_meter_reconciliation AS (
                SELECT
                    me.id                                                AS id,
                    me.shift_id                                          AS shift_id,
                    s.date                                               AS shift_date,
                    s.label                                              AS shift_label,
                    s.company_id                                         AS company_id,
                    s.state                                              AS shift_state,
                    n.pump_id                                            AS pump_id,
                    p.name                                               AS pump_name,
                    me.nozzle_id                                         AS nozzle_id,
                    n.name                                               AS nozzle_name,
                    me.product_id                                        AS product_id,
                    me.attendant_id                                      AS attendant_id,

                    -- Electronic meter
                    COALESCE(me.opening_elec_volume, 0)                  AS elec_open,
                    COALESCE(me.closing_elec_volume, 0)                  AS elec_close,
                    COALESCE(me.qty_sold_elec, 0)                        AS elec_sold,
                    COALESCE(me.elec_cash_sold, 0)                       AS elec_cash_sold,

                    -- Manual meter
                    COALESCE(me.opening_man_mech, 0)                     AS man_open,
                    COALESCE(me.closing_man_mech, 0)                     AS man_close,
                    COALESCE(me.qty_sold_man, 0)                         AS man_sold,

                    -- Elec vs Manual variance
                    COALESCE(me.qty_sold_elec, 0)
                    - COALESCE(me.qty_sold_man, 0)                       AS elec_vs_man_var,

                    ABS(
                        COALESCE(me.qty_sold_elec, 0)
                        - COALESCE(me.qty_sold_man, 0)
                    )                                                    AS elec_vs_man_abs,

                    ABS(
                        COALESCE(me.qty_sold_elec, 0)
                        - COALESCE(me.qty_sold_man, 0)
                    ) <= 1.0                                             AS man_gate_ok

                FROM fms_shift_meter_entry me
                JOIN fms_shift         s  ON s.id  = me.shift_id
                JOIN fms_pump_nozzle   n  ON n.id  = me.nozzle_id
                JOIN fms_pump          p  ON p.id  = n.pump_id
            )
        """)


# ══════════════════════════════════════════════════════════════════════════════
# R30 — E5.4: Tank Loss Source Analysis
# ══════════════════════════════════════════════════════════════════════════════
class FMSReportTankLoss(models.Model):
    """Per-tank per-shift loss breakdown.

    Traces dip variance to three sources:
      • Meter drift  — electronic vs manual meter gap (qty_sold_elec - qty_sold_man)
      • Dip variance — what dip says was consumed vs what meter says was sold
        (positive = tank has less fuel than meter implies → likely evaporation/seepage)
      • Residual gap — allocated residual volume for this tank's product

    All quantities in litres. Negative dip_vs_meter means tank has MORE
    fuel than meter implies (over-dip / measurement error).
    """

    _name = 'fms.report.tank.loss'
    _description = 'Tank Loss Source Analysis'
    _auto = False
    _order = 'shift_date desc, company_id, location_id'

    # Identity
    shift_id        = fields.Many2one('fms.shift',        'Shift',       readonly=True)
    shift_date      = fields.Date(                         'Date',        readonly=True)
    shift_state     = fields.Char(                         'Shift State', readonly=True)
    company_id      = fields.Many2one('res.company',      'Company',     readonly=True)
    location_id     = fields.Many2one('stock.location',   'Tank',        readonly=True)
    product_id      = fields.Many2one('product.product',  'Product',     readonly=True)

    # Dip readings
    dip_opening     = fields.Float('Dip Open (L)',  readonly=True, digits=(16, 2))
    dip_closing     = fields.Float('Dip Close (L)', readonly=True, digits=(16, 2))
    dip_consumed    = fields.Float('Dip Consumed (L)',
                                   help="opening - closing (volume removed from tank)",
                                   readonly=True, digits=(16, 2))

    # Meter totals aggregated across all nozzles drawing from this tank's product
    meter_sold_elec = fields.Float('Meter Elec Sold (L)', readonly=True, digits=(16, 2))
    meter_sold_man  = fields.Float('Meter Man Sold (L)',  readonly=True, digits=(16, 2))

    # Variance columns
    dip_vs_meter    = fields.Float('Dip vs Meter (L)',
                                   help="dip_consumed - meter_sold_elec. "
                                        "Positive = tank emptied more than meter recorded "
                                        "(evaporation, seepage, theft). "
                                        "Negative = meter recorded more than tank lost "
                                        "(over-dip or meter over-read).",
                                   readonly=True, digits=(16, 2))
    meter_drift     = fields.Float('Meter Drift (L)',
                                   help="meter_sold_elec - meter_sold_man. "
                                        "Non-zero indicates electronic/mechanical calibration gap.",
                                   readonly=True, digits=(16, 2))
    residual_vol    = fields.Float('Residual (L)',
                                   help="Net residual allocation volume for this product in this shift.",
                                   readonly=True, digits=(16, 2))

    # Meniscus gate
    meniscus_pct    = fields.Float('Meniscus %',    readonly=True, digits=(16, 2))
    meniscus_limit  = fields.Float('Meniscus Limit (L)',
                                   help="dip_closing * meniscus_pct / 100",
                                   readonly=True, digits=(16, 2))
    within_meniscus = fields.Boolean('Within Meniscus', readonly=True)

    # Loss classification (advisory — not enforced)
    loss_category   = fields.Char('Loss Category', readonly=True,
                                  help="Evaporation/Seepage, Meter Drift, Over-Dip, or OK")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'fms_report_tank_loss')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fms_report_tank_loss AS (
                WITH dip AS (
                    -- One row per tank per shift from immutable dip logs
                    -- company_id sourced from fms_shift (not on dip log itself)
                    SELECT
                        dl.shift_id,
                        dl.location_id,
                        dl.product_id,
                        COALESCE(dl.opening_volume, 0)                       AS dip_opening,
                        COALESCE(dl.closing_volume, 0)                       AS dip_closing,
                        COALESCE(dl.opening_volume, 0)
                            - COALESCE(dl.closing_volume, 0)                 AS dip_consumed
                    FROM fms_dip_log dl
                ),
                meters AS (
                    -- Aggregate all nozzle meter logs by shift + product
                    -- (multiple nozzles can serve the same product/tank)
                    -- company_id sourced from fms_shift via outer join
                    SELECT
                        ml.shift_id,
                        ml.product_id,
                        SUM(COALESCE(ml.qty_sold_elec, 0))                   AS meter_sold_elec,
                        SUM(COALESCE(ml.qty_sold_man,  0))                   AS meter_sold_man
                    FROM fms_meter_log ml
                    GROUP BY ml.shift_id, ml.product_id
                ),
                residuals AS (
                    -- Net residual volume per shift + product from product sales rollup
                    -- (fms_shift_product_sales has product_id + volume_residual)
                    SELECT
                        ps.shift_id,
                        ps.product_id,
                        COALESCE(ps.volume_residual, 0)                      AS residual_vol
                    FROM fms_shift_product_sales ps
                ),
                prefs AS (
                    SELECT company_id, meniscus_pct FROM fms_site_preferences
                )
                SELECT
                    ROW_NUMBER() OVER ()                                     AS id,
                    s.id                                                     AS shift_id,
                    s.date                                                   AS shift_date,
                    s.state                                                  AS shift_state,
                    s.company_id,
                    d.location_id,
                    d.product_id,

                    -- Dip
                    d.dip_opening,
                    d.dip_closing,
                    d.dip_consumed,

                    -- Meter (may be NULL if no meter logs yet)
                    COALESCE(m.meter_sold_elec, 0)                           AS meter_sold_elec,
                    COALESCE(m.meter_sold_man,  0)                           AS meter_sold_man,

                    -- Variances
                    d.dip_consumed
                        - COALESCE(m.meter_sold_elec, 0)                     AS dip_vs_meter,
                    COALESCE(m.meter_sold_elec, 0)
                        - COALESCE(m.meter_sold_man, 0)                      AS meter_drift,
                    COALESCE(r.residual_vol, 0)                              AS residual_vol,

                    -- Meniscus
                    COALESCE(p.meniscus_pct, 0.5)                            AS meniscus_pct,
                    d.dip_closing
                        * COALESCE(p.meniscus_pct, 0.5) / 100.0             AS meniscus_limit,
                    ABS(
                        d.dip_consumed - COALESCE(m.meter_sold_elec, 0)
                    ) <= d.dip_closing
                        * COALESCE(p.meniscus_pct, 0.5) / 100.0             AS within_meniscus,

                    -- Advisory category
                    CASE
                        WHEN ABS(
                            d.dip_consumed - COALESCE(m.meter_sold_elec, 0)
                        ) <= d.dip_closing
                            * COALESCE(p.meniscus_pct, 0.5) / 100.0
                            THEN 'OK'
                        WHEN d.dip_consumed > COALESCE(m.meter_sold_elec, 0)
                            THEN 'Evaporation / Seepage'
                        WHEN COALESCE(m.meter_sold_elec, 0)
                            > COALESCE(m.meter_sold_man, 0) + 1.0
                            THEN 'Meter Drift'
                        ELSE 'Over-Dip / Measurement Error'
                    END                                                      AS loss_category

                FROM dip d
                JOIN fms_shift  s  ON s.id = d.shift_id
                LEFT JOIN meters    m  ON m.shift_id   = d.shift_id
                                      AND m.product_id  = d.product_id
                LEFT JOIN residuals r  ON r.shift_id   = d.shift_id
                                      AND r.product_id  = d.product_id
                LEFT JOIN prefs     p  ON p.company_id  = s.company_id
            )
        """)
