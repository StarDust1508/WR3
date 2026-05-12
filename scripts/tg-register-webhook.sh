#!/usr/bin/env bash
# Register the @KitronBot webhook against a public tunnel URL.
# Usage: bash scripts/tg-register-webhook.sh https://something.trycloudflare.com
#
# Reads TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET from apps/api/.env.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/apps/api/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: $ENV_FILE missing. Run scripts/native-setup.sh first." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_WEBHOOK_SECRET missing in env" >&2
  exit 1
fi

BASE_URL="${1:-}"
if [ -z "$BASE_URL" ]; then
  echo "Usage: $0 <public-base-url>" >&2
  echo "  e.g. $0 https://wr3.trycloudflare.com" >&2
  exit 2
fi
BASE_URL="${BASE_URL%/}"  # strip trailing slash

WEBHOOK_URL="$BASE_URL/v1/tg/webhook"

echo "Registering webhook for @KitronBot:"
echo "  $WEBHOOK_URL"
echo

response=$(curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  --data-urlencode "url=$WEBHOOK_URL" \
  --data-urlencode "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  --data-urlencode "drop_pending_updates=true")

echo "Telegram response:"
echo "$response" | python3 -m json.tool

echo
echo "Verify:"
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo" | python3 -m json.tool
