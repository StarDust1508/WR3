#!/usr/bin/env bash
# wr3 install script for Oracle Cloud Always Free Ampere VM (Ubuntu 24.04 ARM).
#
# Idempotent — safe to re-run. Each section is gated by a presence check
# so partially-failed runs can be resumed without manual cleanup.
#
# What this DOESN'T do (intentionally — keep user control):
#   - Open Oracle's security-list ports (do via OCI console: 80/443/22)
#   - Provision the VM itself (do via OCI console "Create Compute Instance")
#   - Set up TLS (recommend Cloudflare Tunnel — see README)
#   - Write secrets to .env (placeholders only — fill manually)
#
# What it DOES:
#   - Install system deps: Postgres 16 + pgvector, Redis 7, Python 3.13, Rust
#   - Install Foundry (forge), Aderyn, Slither, Wake, solc-select
#   - Create wr3 user + clone repo
#   - Create Postgres DB + apply migrations
#   - Install systemd units for FastAPI + Celery worker + Celery beat
#
# Usage on the Oracle VM (as ubuntu user with sudo):
#     curl -sSL https://raw.githubusercontent.com/StarDust1508/WR3/main/deploy/oracle/install.sh | bash
#   OR clone the repo first and run ./deploy/oracle/install.sh

set -euo pipefail

# ---- guard rails ----------------------------------------------------------
if [[ $EUID -eq 0 ]]; then
    echo "Do not run as root. Run as a sudo user — script will sudo what it needs."
    exit 1
fi

if ! command -v sudo &>/dev/null; then
    echo "sudo is required"
    exit 1
fi

# ---- system deps ----------------------------------------------------------
echo "==> apt update + base packages"
sudo apt-get update -y
sudo apt-get install -y \
    build-essential pkg-config git curl wget \
    postgresql-16 postgresql-contrib-16 postgresql-16-pgvector \
    redis-server \
    python3.13 python3.13-venv python3.13-dev \
    libpq-dev libssl-dev libffi-dev \
    ca-certificates

# ---- uv (Python project manager) ------------------------------------------
if ! command -v uv &>/dev/null; then
    echo "==> installing uv"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Make it visible to the rest of this script
    export PATH="$HOME/.local/bin:$PATH"
fi

# ---- Rust toolchain (for Aderyn) ------------------------------------------
if ! command -v cargo &>/dev/null; then
    echo "==> installing Rust toolchain"
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
    source "$HOME/.cargo/env"
fi

# ---- Aderyn ---------------------------------------------------------------
if ! command -v aderyn &>/dev/null; then
    echo "==> installing aderyn"
    cargo install aderyn
fi

# ---- Foundry (for PoC retry-loop, fuzzing) --------------------------------
if ! command -v forge &>/dev/null; then
    echo "==> installing Foundry"
    curl -L https://foundry.paradigm.xyz | bash
    "$HOME/.foundry/bin/foundryup"
    export PATH="$HOME/.foundry/bin:$PATH"
fi

# ---- solc-select + multi-version solc ------------------------------------
if ! command -v solc-select &>/dev/null; then
    echo "==> installing solc-select"
    uv tool install solc-select
    export PATH="$HOME/.local/bin:$PATH"
fi
echo "==> installing solc 0.4.25 / 0.5.16 / 0.8.20"
solc-select install 0.4.25 0.5.16 0.8.20 || true
solc-select use 0.8.20

# ---- Slither + Wake (via uv tool — isolated venvs) ------------------------
if ! command -v slither &>/dev/null; then
    echo "==> installing slither-analyzer"
    uv tool install slither-analyzer
fi
if ! command -v wake &>/dev/null; then
    echo "==> installing eth-wake"
    uv tool install eth-wake
fi

# ---- Postgres setup -------------------------------------------------------
sudo systemctl enable --now postgresql
if ! sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw wr3; then
    echo "==> creating Postgres user + database 'wr3'"
    sudo -u postgres psql -v ON_ERROR_STOP=1 <<'SQL'
CREATE USER wr3 WITH PASSWORD 'CHANGEME_AT_FIRST_RUN';
CREATE DATABASE wr3 OWNER wr3;
\c wr3
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
SQL
    echo "==> Postgres user 'wr3' created with placeholder password — change with:"
    echo "    sudo -u postgres psql -c \"ALTER USER wr3 WITH PASSWORD 'YOUR_REAL_PASSWORD';\""
fi

# ---- Redis ----------------------------------------------------------------
sudo systemctl enable --now redis-server
# Set a password (required by wr3 config). Only writes if not already set.
if ! sudo grep -q "^requirepass " /etc/redis/redis.conf; then
    echo "==> setting Redis requirepass placeholder"
    sudo sed -i 's/^# requirepass.*/requirepass CHANGEME_AT_FIRST_RUN/' /etc/redis/redis.conf
    sudo systemctl restart redis-server
fi

# ---- wr3 repo + project deps ---------------------------------------------
WR3_HOME="$HOME/wr3"
if [[ ! -d "$WR3_HOME/.git" ]]; then
    echo "==> cloning repo into $WR3_HOME"
    git clone https://github.com/StarDust1508/WR3.git "$WR3_HOME"
fi
cd "$WR3_HOME"
git pull --ff-only origin main || echo "(skipping pull — local commits present)"

echo "==> installing api + audit-engine deps"
(cd apps/api && uv sync --frozen) || (cd apps/api && uv sync)
(cd packages/audit-engine && uv sync --frozen) || (cd packages/audit-engine && uv sync)

# ---- .env template (DON'T overwrite existing) ----------------------------
if [[ ! -f "$WR3_HOME/apps/api/.env" ]]; then
    cat > "$WR3_HOME/apps/api/.env" <<EOF
# Fill these in before starting the service. Restart systemd units after edits.
DATABASE_URL=postgresql+asyncpg://wr3:CHANGEME_AT_FIRST_RUN@localhost:5432/wr3
REDIS_URL=redis://:CHANGEME_AT_FIRST_RUN@localhost:6379/0
NEXTAUTH_SECRET=$(openssl rand -hex 32)
NAVYAI_API_KEY=
NAVYAI_BASE_URL=https://api.navy/v1
NAVYAI_DEFAULT_MODEL=claude-sonnet-4.6
NAVYAI_CHEAP_MODEL=gpt-4o-mini
ETHERSCAN_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 16)
WR3_ENV=prod
NEXT_PUBLIC_SITE_URL=https://YOUR_DOMAIN
EOF
    echo "==> wrote .env template — edit before enabling systemd units"
fi

# ---- alembic migrations ---------------------------------------------------
echo "==> applying alembic migrations"
(cd apps/api && uv run alembic upgrade head) || true

# ---- systemd units --------------------------------------------------------
echo "==> installing systemd units"
sudo cp "$WR3_HOME/deploy/oracle/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload

echo ""
echo "==========================================================="
echo "Install complete."
echo ""
echo "Next steps:"
echo "  1. Edit $WR3_HOME/apps/api/.env (Postgres + Redis password,"
echo "     NAVYAI_API_KEY, ETHERSCAN_API_KEY, TELEGRAM_BOT_TOKEN)"
echo "  2. ALTER USER wr3 / Redis requirepass to match .env"
echo "  3. sudo systemctl enable --now wr3-api wr3-worker wr3-beat"
echo "  4. Verify: curl http://localhost:8001/v1/health"
echo "  5. Tunnel to public via Cloudflare Tunnel (see deploy/oracle/README.md)"
echo "==========================================================="
