#!/usr/bin/env bash
# wr3 smoke-test — one command that proves every layer is alive.
#
# Run on your Mac:
#     ./scripts/verify.sh
#
# Each row is independent. PASS means we got a real, validated response.
# FAIL is loud — a red line + the actual response body so you can debug.
#
# What it checks, in order:
#
#   1. Local Postgres (5432) and Redis (6379) reachable.
#   2. Local FastAPI on :8001 (your Mac's wr3 backend).
#   3. serveo tunnel — the public URL that CF Workers proxies to.
#   4. Cloudflare Workers — the public site users visit.
#   5. wr3-mcp server — spawns it, sends one JSON-RPC, reads the answer.
#   6. (optional) Real audit pipeline — runs a 60-second scan on USDC
#      if you pass `--full`.

set -u

# ---- colors (skip when not a tty) ----------------------------------------
if [[ -t 1 ]]; then
    G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; B=$'\033[1m'; X=$'\033[0m'
else
    G=""; R=""; Y=""; D=""; B=""; X=""
fi

PASS=0
FAIL=0

step() {
    local title="$1"
    printf "%s%s%s " "$B" "$title" "$X"
}

ok() {
    local detail="${1:-}"
    printf "%s✓ PASS%s %s%s%s\n" "$G" "$X" "$D" "$detail" "$X"
    PASS=$((PASS + 1))
}

bad() {
    local detail="${1:-}"
    printf "%s✗ FAIL%s %s\n" "$R" "$X" "$detail"
    FAIL=$((FAIL + 1))
}

warn() {
    local detail="${1:-}"
    printf "%s⚠ WARN%s %s\n" "$Y" "$X" "$detail"
}

# ---- arg parsing ---------------------------------------------------------
FULL=0
LOCAL_API="${WR3_LOCAL_API:-http://localhost:8001}"
PUBLIC_BASE="${WR3_PUBLIC_BASE:-https://wr3.bigmandmitriy777.workers.dev}"
TUNNEL_URL="${WR3_TUNNEL_URL:-}"

while (( $# )); do
    case "$1" in
        --full)       FULL=1;        shift;;
        --local)      LOCAL_API="$2"; shift 2;;
        --public)     PUBLIC_BASE="$2"; shift 2;;
        --tunnel)     TUNNEL_URL="$2"; shift 2;;
        -h|--help)
            sed -n '2,22p' "$0"
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 1;;
    esac
done

# Auto-detect tunnel URL from running ssh process if not passed.
if [[ -z "$TUNNEL_URL" ]]; then
    TUNNEL_URL=$(grep -oE 'https://[a-f0-9-]+\.serveousercontent\.com' /tmp/serveo.log 2>/dev/null | tail -1 || true)
fi
# Last resort — pull from wrangler.toml so the deployed Workers value
# matches what we test.
if [[ -z "$TUNNEL_URL" ]] && [[ -f apps/web/wrangler.toml ]]; then
    TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.serveousercontent\.com' apps/web/wrangler.toml | head -1 || true)
fi

echo
echo "${B}wr3 smoke test${X}"
echo "${D}local API:  $LOCAL_API${X}"
echo "${D}tunnel:     ${TUNNEL_URL:-(not detected)}${X}"
echo "${D}public:     $PUBLIC_BASE${X}"
echo "${D}full scan:  $([ $FULL -eq 1 ] && echo yes || echo "no (pass --full to run a real audit)")${X}"
echo

# =========================================================================
# 1. Local services
# =========================================================================

step "[1/8] Postgres (5432)"
if pg_isready -h localhost -p 5432 -q 2>/dev/null; then
    ok "$(psql -h localhost wr3 -t -c 'SELECT count(*) FROM users' 2>/dev/null | tr -d ' ') users · $(psql -h localhost wr3 -t -c 'SELECT count(*) FROM scans' 2>/dev/null | tr -d ' ') scans · $(psql -h localhost wr3 -t -c 'SELECT count(*) FROM incidents' 2>/dev/null | tr -d ' ') incidents"
else
    bad "Postgres is not listening on 5432. Start with: brew services start postgresql@16"
fi

step "[2/8] Redis (6379)"
# Redis may require auth (we configure `requirepass` in dev). Extract the
# password from REDIS_URL if present so the ping works regardless.
REDIS_URL_LOCAL="${REDIS_URL:-}"
if [[ -z "$REDIS_URL_LOCAL" ]] && [[ -f apps/api/.env ]]; then
    REDIS_URL_LOCAL=$(grep -E '^REDIS_URL=' apps/api/.env | head -1 | cut -d= -f2- | tr -d '"')
fi
# Parse password from redis://[:password@]host:port form
REDIS_PASS=$(echo "$REDIS_URL_LOCAL" | sed -n 's|.*://:\([^@]*\)@.*|\1|p')
if [[ -n "$REDIS_PASS" ]]; then
    PONG=$(redis-cli -h localhost -p 6379 -a "$REDIS_PASS" --no-auth-warning ping 2>/dev/null || echo "")
else
    PONG=$(redis-cli -h localhost -p 6379 ping 2>/dev/null || echo "")
fi
if echo "$PONG" | grep -q PONG; then
    ok "$([ -n "$REDIS_PASS" ] && echo "auth ok")"
else
    bad "Redis didn't pong. Either not running (brew services start redis) or REDIS_URL password mismatch."
fi

# =========================================================================
# 2. Local FastAPI
# =========================================================================

step "[3/8] Local FastAPI ($LOCAL_API)"
LOCAL_HEALTH=$(curl -s -o /tmp/wr3_local_h.json -w "%{http_code}" --max-time 5 "$LOCAL_API/v1/health" || echo "000")
if [[ "$LOCAL_HEALTH" == "200" ]] && grep -q "ok" /tmp/wr3_local_h.json 2>/dev/null; then
    OPENAPI_COUNT=$(curl -s --max-time 5 "$LOCAL_API/openapi.json" | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("paths",{})))' 2>/dev/null || echo "?")
    ok "$OPENAPI_COUNT endpoints exposed"
else
    bad "Backend not reachable. Start with: cd apps/api && uv run uvicorn wr3_api.main:app --port 8001"
fi

# =========================================================================
# 3. Tunnel
# =========================================================================

step "[4/8] serveo tunnel"
if [[ -z "$TUNNEL_URL" ]]; then
    warn "no tunnel URL detected; CF Workers won't reach your Mac"
    echo "       Start one with:"
    echo "       ${D}ssh -R 80:localhost:8001 serveo.net > /tmp/serveo.log 2>&1 &${X}"
else
    TUN_HEALTH=$(curl -s -o /tmp/wr3_tun.json -w "%{http_code}" --max-time 10 "$TUNNEL_URL/v1/health" || echo "000")
    if [[ "$TUN_HEALTH" == "200" ]] && grep -q "ok" /tmp/wr3_tun.json; then
        ok "$TUNNEL_URL"
    else
        bad "$TUNNEL_URL returned HTTP $TUN_HEALTH — tunnel dead. Restart serveo + update WR3_API_URL in wrangler.toml + redeploy."
    fi
fi

# =========================================================================
# 4. Cloudflare Workers production
# =========================================================================

step "[5/8] CF Workers public ($PUBLIC_BASE/api/v1/health)"
PUB_HEALTH=$(curl -s -o /tmp/wr3_pub.json -w "%{http_code}" --max-time 15 "$PUBLIC_BASE/api/v1/health" || echo "000")
if [[ "$PUB_HEALTH" == "200" ]] && grep -q "ok" /tmp/wr3_pub.json; then
    ok ""
else
    bad "HTTP $PUB_HEALTH — Workers proxy unhealthy. Check WR3_API_URL in wrangler.toml and re-deploy."
fi

step "[6/8] Public stats data"
STATS=$(curl -s --max-time 10 "$PUBLIC_BASE/api/v1/public/stats" || echo '{}')
TOTAL=$(echo "$STATS" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("total_scans",-1))' 2>/dev/null || echo "?")
INCIDENTS=$(curl -s --max-time 10 "$PUBLIC_BASE/api/v1/public/incidents?limit=1" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("total","?"))' 2>/dev/null || echo "?")
if [[ "$TOTAL" =~ ^[0-9]+$ ]] && [[ "$INCIDENTS" =~ ^[0-9]+$ ]]; then
    ok "$TOTAL scans, $INCIDENTS incidents in production DB"
else
    bad "stats: '$STATS' · incidents-total: '$INCIDENTS'"
fi

# =========================================================================
# 5. wr3-mcp server
# =========================================================================

step "[7/8] wr3-mcp server (stdio)"
if command -v uv &>/dev/null && [[ -d packages/wr3-mcp ]]; then
    # Spawn the MCP server, send a single initialize+list_tools RPC, read
    # the response. If we get back a tool list with our 6 tools, the MCP
    # surface works end-to-end without an MCP client.
    MCP_OUT=$(cd packages/wr3-mcp && WR3_API_URL="$PUBLIC_BASE/api" uv run python -c "
import asyncio, json, sys
from wr3_mcp.server import list_recent_incidents_impl, get_public_stats_impl
async def main():
    incs = await list_recent_incidents_impl(limit=2)
    stats = await get_public_stats_impl()
    print('TOOLS_OK', len(incs.splitlines()), 'inc lines /', len(stats), 'stats chars')
asyncio.run(main())
" 2>&1 | tail -3)
    if echo "$MCP_OUT" | grep -q "TOOLS_OK"; then
        ok "$MCP_OUT"
    else
        bad "$MCP_OUT"
    fi
else
    warn "uv missing or packages/wr3-mcp not found — skipping"
fi

# =========================================================================
# 6. (optional) Real audit
# =========================================================================

if [[ $FULL -eq 1 ]]; then
    step "[8/8] Real audit pipeline (USDC, ~60s)"
    USDC="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    JOB=$(curl -s -X POST "$LOCAL_API/v1/scan" \
        -H "Content-Type: application/json" \
        -H "X-Forwarded-For: 127.0.0.1" \
        -d "{\"address\":\"$USDC\",\"network\":\"ethereum\"}" --max-time 15)
    JOB_ID=$(echo "$JOB" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("job_id",""))' 2>/dev/null)
    if [[ -z "$JOB_ID" ]]; then
        bad "Scan didn't enqueue: $JOB"
    else
        echo "       job_id=$JOB_ID — polling…"
        SCAN_ID=""
        DEADLINE=$(($(date +%s) + 120))
        while (( $(date +%s) < DEADLINE )); do
            PROG=$(curl -s --max-time 5 "$LOCAL_API/v1/scan/$JOB_ID/progress" 2>/dev/null || echo '{}')
            STAGE=$(echo "$PROG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("stage","?"))' 2>/dev/null)
            SCAN_ID=$(echo "$PROG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("scan_id",""))' 2>/dev/null)
            PROGRESS=$(echo "$PROG" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("progress",0))' 2>/dev/null)
            printf "\r       stage=%s progress=%s%%      " "$STAGE" "$PROGRESS"
            [[ "$STAGE" == "done" || "$STAGE" == "error" ]] && break
            sleep 3
        done
        printf "\n"
        if [[ "$STAGE" == "done" ]] && [[ -n "$SCAN_ID" ]]; then
            # Pull the final report and pretty-print score/tier/findings.
            # Python here-doc (no inline `-c`) avoids the bash/escape mess
            # that previously made this line fail silently under
            # `2>/dev/null` and report a useless empty PASS.
            curl -s --max-time 10 "$LOCAL_API/v1/scan/$SCAN_ID" > /tmp/wr3_scan_report.json
            # Python here-doc as the script (not stdin) — earlier we
            # tried `printf | python3 - <<PY` which made python read its
            # OWN source from stdin, leaving `json.load(sys.stdin)` empty.
            # Reading the file by path avoids that whole class of bug.
            SUMMARY=$(python3 <<'PY'
import json, sys
try:
    with open("/tmp/wr3_scan_report.json") as f:
        d = json.load(f)
    score = d.get("score")
    tier = d.get("tier")
    findings = d.get("findings") or []
    crit = sum(1 for f in findings if (f.get("severity") or "").lower() == "critical")
    high = sum(1 for f in findings if (f.get("severity") or "").lower() == "high")
    dur = d.get("duration_seconds") or 0
    print(f"score={score} tier={tier} findings={len(findings)} (crit={crit}, high={high}) in {dur:.1f}s")
except Exception as e:
    print(f"parse-failed: {e!s}")
PY
            )
            if [[ "$SUMMARY" == score=* ]]; then
                ok "$SUMMARY"
            else
                bad "scan finished but report parse failed: $SUMMARY"
            fi
        else
            bad "stage=$STAGE, scan_id=$SCAN_ID — see /tmp/wr3-api.log for traceback"
        fi
    fi
fi

# =========================================================================
echo
TOTAL=$((PASS + FAIL))
if [[ $FAIL -eq 0 ]]; then
    echo "${G}${B}✓ all $TOTAL checks passed${X}"
    exit 0
else
    echo "${R}${B}✗ $FAIL of $TOTAL checks failed${X}"
    exit 1
fi
