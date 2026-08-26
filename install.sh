#!/bin/bash
# FMS Bare-Metal Installer
# Tested on: Ubuntu 22.04 / 24.04 / WSL2
# Usage: bash install.sh
set -e

ODOO_DIR="$HOME/odoo18"
OCA_DIR="$HOME/oca"
FMS_DIR="$HOME/fms"
FMS_ACC_DIR="$HOME/fms_accounting"
VENV="$HOME/odoo-venv"
DB_NAME="fms_e2e"
SEED="${FMS_SEED:-false}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()  { echo -e "${GREEN}✓ $*${NC}"; }
log() { echo -e "${YELLOW}→ $*${NC}"; }
err() { echo -e "${RED}✗ $*${NC}"; exit 1; }

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║  FMS — Forecourt Management System       ║"
echo "  ║  Installer v1.0                          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# ── 1. System packages ────────────────────────────────────────────────────────
log "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-client libpq-dev \
    git curl wget \
    libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
    libjpeg-dev libpng-dev libfreetype6-dev \
    node-less npm wkhtmltopdf \
    build-essential
ok "System packages installed"

# ── 2. PostgreSQL ─────────────────────────────────────────────────────────────
log "Configuring PostgreSQL..."
sudo service postgresql start 2>/dev/null || true
# Create odoo pg user if not exists
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$USER'" \
    | grep -q 1 || sudo -u postgres createuser --superuser "$USER"
ok "PostgreSQL ready (user: $USER)"

# ── 3. Odoo 18 ────────────────────────────────────────────────────────────────
if [ ! -d "$ODOO_DIR" ]; then
    log "Cloning Odoo 18..."
    git clone --depth=1 --branch 18.0 https://github.com/odoo/odoo.git "$ODOO_DIR"
    ok "Odoo 18 cloned"
else
    ok "Odoo 18 already present — skipping clone"
fi

# ── 4. Python venv ────────────────────────────────────────────────────────────
if [ ! -d "$VENV" ]; then
    log "Creating Python virtual environment..."
    python3 -m venv "$VENV"
fi
log "Installing Python dependencies..."
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$ODOO_DIR/requirements.txt" -q
"$VENV/bin/pip" install openupgradelib cairosvg -q
ok "Python venv ready"

# ── 5. OCA modules ────────────────────────────────────────────────────────────
log "Cloning OCA modules..."
mkdir -p "$OCA_DIR"
OCA_REPOS=(
    account-financial-reporting
    account-financial-tools
    account-reconcile
    credit-control
    web
    server-ux
    reporting-engine
    server-tools
    mis-builder
)
for repo in "${OCA_REPOS[@]}"; do
    if [ ! -d "$OCA_DIR/$repo" ]; then
        git clone --depth=1 --branch 18.0 \
            "https://github.com/OCA/$repo.git" "$OCA_DIR/$repo" 2>/dev/null \
        || git clone --depth=1 --branch 17.0 \
            "https://github.com/OCA/$repo.git" "$OCA_DIR/$repo"
    fi
done
# OCA pip extras
"$VENV/bin/pip" install \
    -r "$OCA_DIR/reporting-engine/requirements.txt" \
    -r "$OCA_DIR/mis-builder/requirements.txt" \
    -q 2>/dev/null || true
ok "OCA modules ready"

# ── 6. FMS modules ────────────────────────────────────────────────────────────
log "Cloning FMS modules..."
if [ ! -d "$FMS_DIR" ]; then
    git clone https://github.com/niiniyare/fms.git "$FMS_DIR"
else
    git -C "$FMS_DIR" pull --ff-only
fi
if [ ! -d "$FMS_ACC_DIR" ]; then
    git clone https://github.com/niiniyare/fms_accounting.git "$FMS_ACC_DIR"
else
    git -C "$FMS_ACC_DIR" pull --ff-only
fi
ok "FMS modules ready"

# ── 7. Write Odoo config ──────────────────────────────────────────────────────
ADDONS="$ODOO_DIR/addons,$HOME,$OCA_DIR/account-financial-reporting,$OCA_DIR/account-financial-tools,$OCA_DIR/account-reconcile,$OCA_DIR/credit-control,$OCA_DIR/web,$OCA_DIR/server-ux,$OCA_DIR/reporting-engine,$OCA_DIR/server-tools,$OCA_DIR/mis-builder"

cat > "$HOME/.odoorc" << EOF
[options]
addons_path = $ADDONS
data_dir = $HOME/.local/share/Odoo
db_host = False
db_port = False
db_user = $USER
logfile = False
EOF
ok "Odoo config written to ~/.odoorc"

# ── 8. Install FMS database ───────────────────────────────────────────────────
ODOO_CMD="$VENV/bin/python $ODOO_DIR/odoo-bin"

log "Creating database $DB_NAME and installing FMS..."
$ODOO_CMD -d "$DB_NAME" \
    -i fms,fms_accounting \
    --addons-path="$ADDONS" \
    --stop-after-init --without-demo=all \
    --load-language=en_US
ok "FMS modules installed on $DB_NAME"

# ── 9. Seed demo data (optional) ──────────────────────────────────────────────
if [ "$SEED" = "true" ]; then
    log "Seeding demo data..."
    $ODOO_CMD shell -d "$DB_NAME" \
        --addons-path="$ADDONS" --no-http \
        < "$FMS_DIR/scripts/seed_e2e.py"
    ok "Demo data seeded"
fi

# ── 10. Desktop shortcut (WSL only) ──────────────────────────────────────────
if grep -qi microsoft /proc/version 2>/dev/null; then
    DESKTOP=$(powershell.exe -Command "[Environment]::GetFolderPath('Desktop')" 2>/dev/null \
        | tr -d '\r' | sed 's|\\|/|g' | sed 's|C:|/mnt/c|')
    if [ -n "$DESKTOP" ] && [ -d "$DESKTOP" ]; then
        cat > "$DESKTOP/FMS - Start.bat" << 'BAT'
@echo off
title FMS - Forecourt Management System
start "" wsl.exe -d Ubuntu -e bash -c "cd ~/fms && make run 2>&1 | tee /tmp/fms_server.log"
timeout /t 20 /nobreak >nul
start "" "http://localhost:8070/web"
BAT
        ok "Desktop shortcut created"
    fi
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  FMS Installation Complete!              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Start server:  cd ~/fms && make run"
echo "  Open browser:  http://localhost:8070"
echo "  Login:         admin / admin"
echo ""
echo "  To load demo data:  FMS_SEED=true bash install.sh"
echo ""
