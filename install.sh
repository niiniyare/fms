#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  FMS — Forecourt Management System  |  Bare-Metal Installer
#  Supports: Ubuntu 22.04 / 24.04  |  Debian 11 / 12  |  WSL2
#  Usage:
#    bash install.sh               # install only
#    FMS_SEED=true bash install.sh # install + load demo data
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────
ODOO_DIR="$HOME/odoo18"
OCA_DIR="$HOME/oca"
FMS_DIR="$HOME/fms"
FMS_ACC_DIR="$HOME/fms_accounting"
VENV="$HOME/odoo-venv"
DB_NAME="${FMS_DB:-fms_e2e}"
SEED="${FMS_SEED:-false}"

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

# ── Helpers ───────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ok()   { echo -e "${GREEN}  ✓ $*${NC}"; }
log()  { echo -e "${YELLOW}  → $*${NC}"; }
info() { echo -e "${BLUE}  ℹ $*${NC}"; }
die()  { echo -e "${RED}  ✗ $*${NC}"; exit 1; }

# ── OS detection ──────────────────────────────────────────────────
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"           # ubuntu | debian
        OS_VER="$VERSION_ID"  # 22.04 | 24.04 | 11 | 12
    else
        die "Cannot detect OS. Supported: Ubuntu 22.04/24.04, Debian 11/12."
    fi

    case "$OS_ID" in
        ubuntu)
            case "$OS_VER" in
                22.04|24.04) ;;
                *) die "Ubuntu $OS_VER not supported. Use 22.04 or 24.04." ;;
            esac ;;
        debian)
            case "$OS_VER" in
                11|12) ;;
                *) die "Debian $OS_VER not supported. Use 11 (Bullseye) or 12 (Bookworm)." ;;
            esac ;;
        *)
            die "Unsupported OS: $OS_ID. Supported: Ubuntu 22.04/24.04, Debian 11/12." ;;
    esac

    IS_WSL=false
    grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=true
}

# ── Banner ────────────────────────────────────────────────────────
print_banner() {
    echo ""
    echo -e "${BLUE}  ╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}  ║  FMS — Forecourt Management System           ║${NC}"
    echo -e "${BLUE}  ║  Installer  |  Odoo 18 Community             ║${NC}"
    echo -e "${BLUE}  ╚══════════════════════════════════════════════╝${NC}"
    echo ""
    info "OS: $OS_ID $OS_VER${IS_WSL:+ (WSL2)}"
    info "DB: $DB_NAME  |  Seed: $SEED"
    echo ""
}

# ── 1. System packages ────────────────────────────────────────────
install_system_packages() {
    log "Updating package lists..."
    sudo apt-get update -qq

    log "Installing system packages..."
    sudo apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv python3-dev \
        postgresql postgresql-client libpq-dev \
        git curl \
        libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
        libjpeg-dev libpng-dev libfreetype6-dev \
        build-essential \
        npm

    # node-less: package name differs by distro/version
    sudo apt-get install -y --no-install-recommends node-less 2>/dev/null \
        || sudo npm install -g less

    # wkhtmltopdf: use distro package where available, else download
    if apt-cache show wkhtmltopdf &>/dev/null; then
        sudo apt-get install -y --no-install-recommends wkhtmltopdf
    else
        log "Installing wkhtmltopdf from GitHub release..."
        local arch; arch=$(dpkg --print-architecture)
        local deb="wkhtmltox_0.12.6.1-2.jammy_${arch}.deb"
        curl -fsSL "https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-2/$deb" \
            -o /tmp/wkhtmltox.deb
        sudo apt-get install -y /tmp/wkhtmltox.deb
        rm /tmp/wkhtmltox.deb
    fi

    ok "System packages installed"
}

# ── 2. PostgreSQL ─────────────────────────────────────────────────
setup_postgres() {
    log "Starting PostgreSQL..."
    sudo service postgresql start 2>/dev/null \
        || sudo pg_ctlcluster "$(pg_lsclusters -h | awk 'NR==1{print $1}')" main start 2>/dev/null \
        || true

    log "Creating PostgreSQL user '$USER'..."
    if ! sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$USER'" \
            2>/dev/null | grep -q 1; then
        sudo -u postgres createuser --superuser "$USER"
    fi

    ok "PostgreSQL ready (user: $USER)"
}

# ── 3. Odoo 18 ────────────────────────────────────────────────────
install_odoo() {
    if [ -d "$ODOO_DIR/.git" ]; then
        log "Updating Odoo 18..."
        git -C "$ODOO_DIR" pull --ff-only --quiet
    else
        log "Cloning Odoo 18 (this may take a few minutes)..."
        git clone --depth=1 --branch 18.0 \
            https://github.com/odoo/odoo.git "$ODOO_DIR"
    fi
    ok "Odoo 18 ready"
}

# ── 4. Python venv ────────────────────────────────────────────────
setup_venv() {
    if [ ! -d "$VENV" ]; then
        log "Creating Python virtual environment..."
        python3 -m venv "$VENV"
    fi

    log "Installing Python dependencies..."
    "$VENV/bin/pip" install --upgrade pip --quiet
    "$VENV/bin/pip" install -r "$ODOO_DIR/requirements.txt" --quiet
    "$VENV/bin/pip" install openupgradelib cairosvg --quiet

    ok "Python venv ready ($VENV)"
}

# ── 5. OCA modules ────────────────────────────────────────────────
install_oca() {
    log "Cloning OCA modules..."
    mkdir -p "$OCA_DIR"

    for repo in "${OCA_REPOS[@]}"; do
        if [ -d "$OCA_DIR/$repo/.git" ]; then
            git -C "$OCA_DIR/$repo" pull --ff-only --quiet
        else
            git clone --depth=1 --branch 18.0 \
                "https://github.com/OCA/$repo.git" "$OCA_DIR/$repo" \
                || die "Failed to clone OCA/$repo branch 18.0. Check it exists at https://github.com/OCA/$repo"
        fi
    done

    # Extra Python deps required by specific OCA modules
    "$VENV/bin/pip" install \
        -r "$OCA_DIR/reporting-engine/requirements.txt" \
        -r "$OCA_DIR/mis-builder/requirements.txt" \
        --quiet 2>/dev/null || true

    ok "OCA modules ready ($OCA_DIR)"
}

# ── 6. FMS modules ────────────────────────────────────────────────
install_fms() {
    log "Installing FMS modules..."

    if [ -d "$FMS_DIR/.git" ]; then
        git -C "$FMS_DIR" pull --ff-only --quiet
    else
        git clone https://github.com/niiniyare/fms.git "$FMS_DIR"
    fi

    if [ -d "$FMS_ACC_DIR/.git" ]; then
        git -C "$FMS_ACC_DIR" pull --ff-only --quiet
    else
        git clone https://github.com/niiniyare/fms_accounting.git "$FMS_ACC_DIR"
    fi

    ok "FMS modules ready"
}

# ── 7. Odoo config ────────────────────────────────────────────────
write_odoo_config() {
    local addons
    addons="$ODOO_DIR/addons,$HOME"
    for repo in "${OCA_REPOS[@]}"; do
        addons="$addons,$OCA_DIR/$repo"
    done

    cat > "$HOME/.odoorc" << EOF
[options]
addons_path = $addons
data_dir = $HOME/.local/share/Odoo
db_host = False
db_port = False
db_user = $USER
logfile = False
EOF

    ok "Odoo config written → ~/.odoorc"
}

# ── 8. Install FMS database ───────────────────────────────────────
install_database() {
    local odoo_cmd="$VENV/bin/python $ODOO_DIR/odoo-bin"
    local addons
    addons="$ODOO_DIR/addons,$HOME"
    for repo in "${OCA_REPOS[@]}"; do
        addons="$addons,$OCA_DIR/$repo"
    done

    log "Creating database '$DB_NAME' and installing FMS..."
    $odoo_cmd -d "$DB_NAME" \
        -i fms,fms_accounting \
        --addons-path="$addons" \
        --stop-after-init --without-demo=all \
        --load-language=en_US
    ok "FMS installed on '$DB_NAME'"

    if [ "$SEED" = "true" ]; then
        log "Seeding demo data..."
        $odoo_cmd shell -d "$DB_NAME" \
            --addons-path="$addons" --no-http \
            < "$FMS_DIR/scripts/seed_e2e.py"
        ok "Demo data seeded"
    fi
}

# ── 9. Desktop shortcut (WSL only) ───────────────────────────────
create_wsl_shortcut() {
    [ "$IS_WSL" = "true" ] || return 0

    local desktop
    desktop=$(powershell.exe -Command \
        "[Environment]::GetFolderPath('Desktop')" 2>/dev/null \
        | tr -d '\r' \
        | sed 's|\\|/|g; s|^\([A-Za-z]\):|/mnt/\L\1|')

    [ -n "$desktop" ] && [ -d "$desktop" ] || return 0

    cat > "$desktop/FMS - Start.bat" << 'BAT'
@echo off
title FMS - Forecourt Management System
start "" wsl.exe -e bash -lc "cd ~/fms && make run 2>&1 | tee /tmp/fms_server.log"
timeout /t 20 /nobreak >nul
start "" "http://localhost:8070/web"
BAT

    cat > "$desktop/FMS - Stop.bat" << 'BAT'
@echo off
title FMS - Stop
wsl.exe -e bash -lc "fuser -k 8070/tcp 2>/dev/null; echo Stopped"
timeout /t 2 /nobreak >nul
BAT

    ok "Desktop shortcuts created"
}

# ── Main ──────────────────────────────────────────────────────────
main() {
    detect_os
    print_banner

    install_system_packages
    setup_postgres
    install_odoo
    setup_venv
    install_oca
    install_fms
    write_odoo_config
    install_database
    create_wsl_shortcut

    echo ""
    echo -e "${GREEN}  ╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}  ║  Installation Complete!                      ║${NC}"
    echo -e "${GREEN}  ╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Start:    cd ~/fms && make run"
    echo "  Browser:  http://localhost:8070"
    echo "  Login:    admin / admin"
    echo ""
    echo "  Load demo data next time:  FMS_SEED=true bash install.sh"
    echo ""
}

main "$@"
