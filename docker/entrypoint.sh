#!/bin/bash
set -e

ODOO="/opt/odoo-venv/bin/python /opt/odoo18/odoo-bin"
CONF="-c /etc/odoo/odoo.conf"
DB="${FMS_DB:-fms}"

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
until pg_isready -h db -U odoo -q; do sleep 2; done
echo "PostgreSQL ready."

if [ "$1" = "odoo" ]; then
    # First boot: install modules if DB doesn't exist
    if ! psql -h db -U odoo -lqt 2>/dev/null | cut -d\| -f1 | grep -qw "$DB"; then
        echo "Creating database $DB and installing FMS..."
        $ODOO $CONF -d "$DB" \
            -i fms,fms_accounting \
            --without-demo=all \
            --load-language=en_US \
            --stop-after-init

        # Seed demo data if requested
        if [ "${FMS_SEED:-false}" = "true" ]; then
            echo "Seeding demo data..."
            $ODOO $CONF shell -d "$DB" --no-http < /opt/fms/scripts/seed_e2e.py
        fi

        echo "FMS installation complete."
    fi

    echo "Starting Odoo on port 8069..."
    exec $ODOO $CONF -d "$DB"
else
    exec "$@"
fi
