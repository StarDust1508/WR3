#!/usr/bin/env bash
# Wire @KitronBot to a deployed Mini App URL.
#
# Usage:
#   bash scripts/tg-connect-mini-app.sh <web-url> <api-url>
#
# <web-url> — the deployed Mini App, e.g.
#             https://wr3.bigmandmitriy777.workers.dev
# <api-url> — the FastAPI tunnel for the webhook, e.g.
#             https://0ae335bd75b195e3-72-56-101-252.serveousercontent.com
#
# Reads TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET from apps/api/.env.
#
# Does three things, idempotent:
#   1. Re-registers /v1/tg/webhook against <api-url>
#   2. Sets the bot menu button to open <web-url>/tg
#   3. Smoke-tests the webhook with a synthetic /start update

set -euo pipefail

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
NC=$'\033[0m'

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/apps/api/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "${RED}ERROR:${NC} $ENV_FILE missing" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <web-url> <api-url>" >&2
  echo "  e.g. $0 https://wr3.bigmandmitriy777.workers.dev https://xxx.serveousercontent.com" >&2
  exit 2
fi

WEB_URL="${1%/}"
API_URL="${2%/}"

[ -z "${TELEGRAM_BOT_TOKEN:-}" ] && { echo "${RED}TELEGRAM_BOT_TOKEN missing${NC}" >&2; exit 1; }
[ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ] && { echo "${RED}TELEGRAM_WEBHOOK_SECRET missing${NC}" >&2; exit 1; }

BOT="https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN"

step() { echo; echo "${GREEN}==>${NC} $*"; }

step "Probing API tunnel ($API_URL/v1/health)"
if ! curl -sf "$API_URL/v1/health" >/dev/null; then
  echo "${RED}API tunnel not reachable${NC}" >&2
  exit 1
fi
echo "ok"

step "Probing Mini App URL ($WEB_URL/tg)"
status=$(curl -s -o /dev/null -w "%{http_code}" "$WEB_URL/tg" || true)
if [ "$status" != "200" ] && [ "$status" != "304" ]; then
  echo "${RED}Mini App URL returned HTTP $status${NC} — Worker may still be deploying" >&2
  exit 1
fi
echo "HTTP $status"

step "Registering webhook → $API_URL/v1/tg/webhook"
curl -s "$BOT/setWebhook" \
  --data-urlencode "url=$API_URL/v1/tg/webhook" \
  --data-urlencode "secret_token=$TELEGRAM_WEBHOOK_SECRET" \
  --data-urlencode "drop_pending_updates=true" | python3 -m json.tool

step "Setting menu button → $WEB_URL/tg"
curl -s -X POST "$BOT/setChatMenuButton" \
  -H "Content-Type: application/json" \
  -d "{\"menu_button\":{\"type\":\"web_app\",\"text\":\"wr3 audit\",\"web_app\":{\"url\":\"$WEB_URL/tg\"}}}" | python3 -m json.tool

step "Refreshing bot commands"
curl -s -X POST "$BOT/setMyCommands" \
  -H "Content-Type: application/json" \
  -d '{"commands":[{"command":"start","description":"Open wr3"},{"command":"scan","description":"Scan 0x... base"},{"command":"help","description":"How wr3 works"}]}' | python3 -m json.tool

step "Webhook info (should show new url, last_error: none)"
curl -s "$BOT/getWebhookInfo" | python3 -c "
import json, sys
d = json.load(sys.stdin)['result']
print(f'  url:        {d[\"url\"]}')
print(f'  pending:    {d[\"pending_update_count\"]}')
print(f'  last_error: {d.get(\"last_error_message\", \"none\")}')
"

step "Smoke test: synthetic /start to webhook"
curl -s -X POST "$API_URL/v1/tg/webhook" \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET" \
  -d '{"update_id":4242,"message":{"message_id":1,"from":{"id":42,"is_bot":false,"first_name":"smoke"},"chat":{"id":42,"type":"private"},"date":1700000000,"text":"/start"}}' | python3 -m json.tool

echo
echo "${GREEN}DONE.${NC} Open @KitronBot in Telegram, tap '/start' or the 'wr3 audit' menu button."
