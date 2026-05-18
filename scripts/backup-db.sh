#!/usr/bin/env bash
# ---------------------------------------------------------------
# backup-db.sh — pg_dump backup for the wr3 database
#
# Reads DATABASE_URL from apps/api/.env (or environment).
# Handles the SQLAlchemy "postgresql+asyncpg://" prefix.
# Saves compressed custom-format dumps; keeps the last 7.
# ---------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups"
ENV_FILE="$PROJECT_ROOT/apps/api/.env"
KEEP_COUNT=7

# ----- helpers --------------------------------------------------

log()  { printf '[backup] %s\n' "$*"; }
fail() { printf '[backup] ERROR: %s\n' "$*" >&2; exit 1; }

# ----- resolve DATABASE_URL ------------------------------------

if [[ -z "${DATABASE_URL:-}" ]]; then
    if [[ -f "$ENV_FILE" ]]; then
        DATABASE_URL="$(grep -E '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d'=' -f2-)"
    fi
fi

[[ -z "${DATABASE_URL:-}" ]] && fail "DATABASE_URL is not set and not found in $ENV_FILE"

log "Raw DATABASE_URL detected (credentials hidden)"

# ----- normalise URL -------------------------------------------
# SQLAlchemy uses postgresql+asyncpg:// but pg_dump needs postgresql://
DB_URL="${DATABASE_URL/postgresql+asyncpg:\/\//postgresql:\/\/}"

# ----- parse URL -----------------------------------------------
# Format: postgresql://[user[:password]@]host[:port]/dbname

# Strip scheme
remainder="${DB_URL#postgresql://}"

# Split dbname (everything after the last /)
PG_DB="${remainder##*/}"
authority="${remainder%/*}"

# Separate userinfo and hostinfo
if [[ "$authority" == *@* ]]; then
    userinfo="${authority%@*}"
    hostinfo="${authority##*@}"
else
    userinfo=""
    hostinfo="$authority"
fi

# Parse user / password
if [[ -n "$userinfo" ]]; then
    if [[ "$userinfo" == *:* ]]; then
        PG_USER="${userinfo%%:*}"
        PG_PASS="${userinfo#*:}"
    else
        PG_USER="$userinfo"
        PG_PASS=""
    fi
else
    PG_USER=""
    PG_PASS=""
fi

# Parse host / port
if [[ "$hostinfo" == *:* ]]; then
    PG_HOST="${hostinfo%%:*}"
    PG_PORT="${hostinfo##*:}"
else
    PG_HOST="$hostinfo"
    PG_PORT="5432"
fi

# Default host to localhost if empty (e.g. postgresql://:5432/wr3)
PG_HOST="${PG_HOST:-localhost}"

log "Host=$PG_HOST  Port=$PG_PORT  User=${PG_USER:-<peer>}  DB=$PG_DB"

# ----- validate ------------------------------------------------

[[ -z "$PG_DB" ]] && fail "Could not parse database name from DATABASE_URL"
command -v pg_dump >/dev/null 2>&1 || fail "pg_dump not found — install PostgreSQL client tools"

# ----- prepare backup dir --------------------------------------

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y-%m-%d-%H%M%S)"
DUMP_FILE="$BACKUP_DIR/wr3-${TIMESTAMP}.dump"

# ----- run pg_dump ---------------------------------------------

log "Starting pg_dump → $DUMP_FILE"

DUMP_ARGS=(
    --format=custom
    --host="$PG_HOST"
    --port="$PG_PORT"
    --dbname="$PG_DB"
    --file="$DUMP_FILE"
)

[[ -n "$PG_USER" ]] && DUMP_ARGS+=(--username="$PG_USER")

# Export password if present
if [[ -n "${PG_PASS:-}" ]]; then
    export PGPASSWORD="$PG_PASS"
fi

if pg_dump "${DUMP_ARGS[@]}"; then
    SIZE="$(du -h "$DUMP_FILE" | cut -f1)"
    log "Backup complete: $DUMP_FILE ($SIZE)"
else
    rm -f "$DUMP_FILE"
    fail "pg_dump failed"
fi

# ----- prune old backups ---------------------------------------

BACKUP_COUNT="$(find "$BACKUP_DIR" -maxdepth 1 -name 'wr3-*.dump' -type f | wc -l | tr -d ' ')"

if (( BACKUP_COUNT > KEEP_COUNT )); then
    REMOVE_COUNT=$(( BACKUP_COUNT - KEEP_COUNT ))
    log "Pruning $REMOVE_COUNT old backup(s) (keeping last $KEEP_COUNT)"
    # shellcheck disable=SC2012
    ls -1t "$BACKUP_DIR"/wr3-*.dump | tail -n "$REMOVE_COUNT" | while read -r old; do
        log "  Removing $(basename "$old")"
        rm -f "$old"
    done
fi

log "Done. $KEEP_COUNT most recent backups retained."
