FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    ODOO_VERSION=18.0 \
    LANG=en_US.UTF-8

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python3-dev \
    postgresql-client libpq-dev \
    git curl wget gnupg2 \
    libxml2-dev libxslt1-dev libldap2-dev libsasl2-dev \
    libjpeg-dev libpng-dev libfreetype6-dev \
    node-less npm \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# ── Odoo 18 source ────────────────────────────────────────────────────────────
RUN git clone --depth=1 --branch 18.0 \
    https://github.com/odoo/odoo.git /opt/odoo18

# ── Python venv + Odoo requirements ──────────────────────────────────────────
RUN python3 -m venv /opt/odoo-venv \
    && /opt/odoo-venv/bin/pip install --upgrade pip \
    && /opt/odoo-venv/bin/pip install -r /opt/odoo18/requirements.txt \
    && /opt/odoo-venv/bin/pip install openupgradelib cairosvg

# ── OCA modules ───────────────────────────────────────────────────────────────
WORKDIR /opt/oca
RUN for repo in \
        account-financial-reporting \
        account-financial-tools \
        account-reconcile \
        credit-control \
        web \
        server-ux \
        reporting-engine \
        server-tools \
        mis-builder; do \
    git clone --depth=1 --branch 18.0 \
        https://github.com/OCA/$repo.git /opt/oca/$repo 2>/dev/null || \
    git clone --depth=1 --branch 17.0 \
        https://github.com/OCA/$repo.git /opt/oca/$repo; \
done \
    && /opt/odoo-venv/bin/pip install \
        -r /opt/oca/reporting-engine/requirements.txt \
        -r /opt/oca/mis-builder/requirements.txt \
        2>/dev/null || true

# ── FMS modules ───────────────────────────────────────────────────────────────
RUN git clone https://github.com/niiniyare/fms.git /opt/fms \
    && git clone https://github.com/niiniyare/fms_accounting.git /opt/fms_accounting

# ── Odoo config ───────────────────────────────────────────────────────────────
RUN mkdir -p /var/lib/odoo /var/log/odoo /etc/odoo
COPY docker/odoo.conf /etc/odoo/odoo.conf

# ── Entrypoint ────────────────────────────────────────────────────────────────
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8069
VOLUME ["/var/lib/odoo"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
