#!/usr/bin/env python3
"""
load_demo_data.py — Load FMS demo data into an existing Odoo database.

Usage:
    python scripts/load_demo_data.py [--db fms_demo]

Requires the odoo-venv Python and ODOO source on sys.path.
Run from the fms/ directory.
"""

import sys
import os
import argparse

# Add Odoo to path
ODOO_HOME = os.path.expanduser('~/odoo18')
sys.path.insert(0, ODOO_HOME)

import odoo
from odoo.tools import config

parser = argparse.ArgumentParser(description='Load FMS demo data')
parser.add_argument('--db', default='fms_demo', help='Database name')
args = parser.parse_args()

# Configure Odoo
config['db_name'] = args.db
config['addons_path'] = f"{ODOO_HOME}/odoo/addons,{ODOO_HOME}/addons,{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}"
config['without_demo'] = ''

odoo.service.server.load_server_wide_modules()

db = odoo.sql_db.db_connect(args.db)

with odoo.api.Environment.manage():
    with db.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        import odoo.tools.convert as convert

        demo_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'demo', 'fms_demo_data.xml'
        )
        print(f"Loading demo data from: {demo_file}")
        convert.convert_file(env, 'fms', 'demo/fms_demo_data.xml', {}, mode='init', noupdate=True)
        cr.commit()

        print("\n✅ Demo data loaded successfully!\n")
        print(f"  Pumps         : {env['fms.pump'].search_count([])}")
        print(f"  Nozzles       : {env['fms.pump.nozzle'].search_count([])}")
        print(f"  Fuel tanks    : {env['stock.location'].search_count([('fms_is_fuel_tank','=',True)])}")
        print(f"  Employees     : {env['hr.employee'].search_count([('fms_is_attendant','=',True)])}")
        print(f"  Shifts        : {env['fms.shift'].search_count([])}")
        print(f"  Meter entries : {env['fms.shift.meter.entry'].search_count([])}")
        print(f"  Dip entries   : {env['fms.shift.dip.entry'].search_count([])}")
        print(f"  Cash entries  : {env['fms.shift.attendant.cash'].search_count([])}")
        print()
        print("Open http://localhost:8069 → Forecourt → Shifts to see the demo shift.")
