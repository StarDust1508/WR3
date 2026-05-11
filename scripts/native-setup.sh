#!/usr/bin/env bash
# wr3 — native macOS bootstrap (Homebrew Postgres + Redis).
# Idempotent: safe to re-run.

set -euo pipefail

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

say()  { echo "${GREEN}==>${NC} $*"; }
warn() { echo "${YELLOW}!! ${NC} $*"; }
die()  { echo "${RED}xx${NC} $*" >&2; exit 1; }

# --- Preflight ---
say "Checking prerequisites"
command -v psql >/dev/null      || die "psql not found. Install: brew install postgresql@16"
command -v redis-cli >/dev/null || die "redis-cli not found. Install: brew install redis"

# --- Services ---
say "Ensuring Postgres + Redis are running"
if ! brew services list 2>/dev/null | awk '$1=="postgresql@16" && $2=="started"' | grep -q .; then
  brew services start postgresql@16
fi
if ! brew services list 2>/dev/null | awk '$1=="redis" && $2=="started"' | grep -q .; then
  brew services start redis
fi

# --- Database ---
say "Creating wr3 database (if missing)"
if ! psql -lqt 2>/dev/null | cut -d'|' -f1 | awk '{$1=$1};1' | grep -qx wr3; then
  createdb wr3
  say "  created"
else
  warn "  wr3 DB already exists, skipping create"
fi

say "Installing extensions"
psql -d wr3 -v ON_ERROR_STOP=1 <<'SQL'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL

# --- Smoke ---
say "Smoke checks"
psql -d wr3 -tAc "SELECT version();" | head -1
redis-cli ping

# --- .env.local ---
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$ROOT/.env.local" ]; then
  say "Creating .env.local from template"
  cp "$ROOT/.env.example" "$ROOT/.env.local"
  warn "Fill in API keys in $ROOT/.env.local (see docs/ONBOARDING.md)"
else
  warn ".env.local exists — not overwriting"
fi

if [ ! -f "$ROOT/apps/api/.env" ]; then
  cp "$ROOT/apps/api/.env.example" "$ROOT/apps/api/.env"
  say "Created apps/api/.env"
fi

say "Done. Postgres: $(psql -d wr3 -tAc "SELECT current_database()") · Redis: $(redis-cli ping)"
