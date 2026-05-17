#!/usr/bin/env bash
# Daily Postgres backup → Cloudflare R2 (or local disk fallback).
#
# Closes TZ §10.1 "Backups: Postgres → daily snapshot in R2 (encrypted),
# 30-day retention."
#
# Usage: ./deploy/backups/backup.sh
#
# Required env (typically loaded from apps/api/.env via direnv or
# explicitly):
#   DATABASE_URL          postgresql://[user[:pass]@]host[:port]/db
#                         (asyncpg flavour also accepted — we re-parse)
#
# Optional env (when set, dump is uploaded to R2; otherwise kept local):
#   R2_ACCOUNT_ID         CF R2 account id
#   R2_ACCESS_KEY_ID      R2 access key
#   R2_SECRET_ACCESS_KEY  R2 secret
#   R2_BUCKET             default: wr3-backups
#
# Optional:
#   BACKUP_DIR            local fallback dir (default: $HOME/wr3-backups)
#   BACKUP_RETENTION_DAYS purge dumps older than N days (default: 30)
#   BACKUP_GPG_RECIPIENT  if set, gpg --encrypt --recipient $val before upload
#
# Exit codes:
#   0 — backup written (and uploaded when R2 creds present)
#   1 — bad config
#   2 — pg_dump failed
#   3 — upload failed (but local copy was kept)
#
# Pair with cron (Mac launchd or Oracle VM crontab):
#   0 3 * * * /Users/bubble3/Desktop/wr3/deploy/backups/backup.sh >>$HOME/wr3-backups/cron.log 2>&1

set -euo pipefail

# ---- config --------------------------------------------------------------

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERR: DATABASE_URL not set" >&2
    exit 1
fi

BACKUP_DIR="${BACKUP_DIR:-$HOME/wr3-backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
R2_BUCKET="${R2_BUCKET:-wr3-backups}"

mkdir -p "$BACKUP_DIR"

# Normalise the URL — `pg_dump` doesn't accept the asyncpg variant
# (`postgresql+asyncpg://...`). Strip the dialect suffix if present.
PG_URL="${DATABASE_URL/postgresql+asyncpg:/postgresql:}"

# ---- dump ----------------------------------------------------------------

TS=$(date -u +%Y%m%d-%H%M%S)
DB_NAME=$(printf '%s' "$PG_URL" | sed -E 's|.*/([^/?]+).*|\1|')
FILE="$BACKUP_DIR/wr3-${DB_NAME}-${TS}.sql.gz"

echo "==> Dumping $DB_NAME → $FILE"
if ! pg_dump --no-owner --no-privileges --format=plain "$PG_URL" | gzip -9 > "$FILE.tmp"; then
    echo "ERR: pg_dump failed" >&2
    rm -f "$FILE.tmp"
    exit 2
fi
mv "$FILE.tmp" "$FILE"
SIZE=$(du -h "$FILE" | awk '{print $1}')
echo "    OK ($SIZE)"

# ---- optional encryption -------------------------------------------------

if [[ -n "${BACKUP_GPG_RECIPIENT:-}" ]]; then
    if ! command -v gpg >/dev/null; then
        echo "WARN: BACKUP_GPG_RECIPIENT set but gpg not installed; skipping" >&2
    else
        echo "==> Encrypting for $BACKUP_GPG_RECIPIENT"
        gpg --batch --yes --trust-model always --recipient "$BACKUP_GPG_RECIPIENT" \
            --output "$FILE.gpg" --encrypt "$FILE"
        rm -f "$FILE"
        FILE="$FILE.gpg"
        echo "    OK ($(du -h "$FILE" | awk '{print $1}'))"
    fi
fi

# ---- optional R2 upload --------------------------------------------------

if [[ -n "${R2_ACCOUNT_ID:-}" && -n "${R2_ACCESS_KEY_ID:-}" && -n "${R2_SECRET_ACCESS_KEY:-}" ]]; then
    if ! command -v aws >/dev/null; then
        echo "WARN: aws CLI not found — backup kept locally, install awscli to enable R2 upload" >&2
    else
        # CF R2 is S3-compatible; aws CLI works with custom endpoint.
        echo "==> Uploading to R2 bucket $R2_BUCKET"
        if AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID" \
           AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY" \
           aws s3 cp "$FILE" "s3://$R2_BUCKET/$(basename "$FILE")" \
               --endpoint-url "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
               --no-progress; then
            echo "    OK"
        else
            echo "ERR: R2 upload failed (local copy preserved)" >&2
            exit 3
        fi
    fi
else
    echo "    R2 creds not set — backup kept locally only."
fi

# ---- retention -----------------------------------------------------------

# Local cleanup — drop dumps older than retention.
echo "==> Pruning local backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -name 'wr3-*.sql.gz*' -mtime "+$RETENTION_DAYS" -print -delete || true

echo "==> Done."
