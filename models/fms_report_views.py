"""
fms_report_views.py — _auto=False SQL views backing operational reports.

R2  fms.report.daily.station   — Daily Station Report (shift → product)
R4  fms.report.attendant.sales — Attendant Sales & Cash (attendant → shift)
R3  fms.report.wetstock        — Wetstock Reconciliation (tank → day)
"""

from odoo import models, fields, api


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
    product_name   = fields.Char(                        'Product',   readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)
    supervisor_id  = fields.Many2one('hr.employee',     'Supervisor', readonly=True)

    # ── Measures ──────────────────────────────────────────────────────
    qty_litres     = fields.Float('Volume (L)',          readonly=True, digits=(16, 2))
    amount_kes     = fields.Float('Sales (KES)',         readonly=True, digits=(16, 2))
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
    attendant_name = fields.Char(                        'Attendant', readonly=True)
    company_id     = fields.Many2one('res.company',     'Company',    readonly=True)

    # ── Measures ──────────────────────────────────────────────────────
    reported_sales = fields.Float('Reported Sales (KES)', readonly=True, digits=(16, 2))
    mpesa_amount   = fields.Float('MPesa (KES)',          readonly=True, digits=(16, 2))
    card_amount    = fields.Float('Card (KES)',            readonly=True, digits=(16, 2))
    ar_amount      = fields.Float('AR (KES)',              readonly=True, digits=(16, 2))
    expense_amount = fields.Float('Expenses (KES)',        readonly=True, digits=(16, 2))
    cash_collected = fields.Float('Cash Dropped (KES)',    readonly=True, digits=(16, 2))
    balance        = fields.Float('Shortage / Overage',    readonly=True, digits=(16, 2))
    shift_count    = fields.Integer('Shifts',              readonly=True)

    def init(self):
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
                    COALESCE(ac.mpesa_amount, 0)            AS mpesa_amount,
                    COALESCE(ac.card_amount, 0)             AS card_amount,
                    COALESCE(ac.ar_amount, 0)               AS ar_amount,
                    COALESCE(ac.expense_amount, 0)          AS expense_amount,
                    COALESCE(ac.cash_collected, 0)          AS cash_collected,
                    COALESCE(ac.balance, 0)                 AS balance,
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
    tank_name     = fields.Char(                           'Tank',    readonly=True)
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
    tank_name            = fields.Char(                       'Tank',   readonly=True)
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
