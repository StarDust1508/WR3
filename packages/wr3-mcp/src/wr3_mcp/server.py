"""wr3 MCP server — exposes the audit platform as Model Context Protocol tools.

Architecture:
    Hermes / Claude Desktop / Cursor       (MCP client)
              │  stdio (json-rpc framed)
              ▼
        wr3-mcp (THIS module)
              │  HTTP
              ▼
    wr3 REST API (CF Workers → serveo → Mac FastAPI)

The server is stateless — every tool call is a fresh HTTP request to the
wr3 REST endpoint. WR3_API_URL points at the public CF Workers URL by
default; operators running their own wr3 instance can override.

Tools exposed (read-only by default; the scan tool is opt-in destructive):

    list_recent_incidents      Live exploit feed (Rekt / SlowMist / DefiLlama)
    list_public_scans          Public leaderboard
    get_public_stats           Aggregate stats
    get_scan                   Full audit report by id
    scan_contract              Start an audit (returns job_id)
    get_subscription_plans     Stars-priced plans catalog

A scan blocks the calling agent for 30-120 seconds (the pipeline is
synchronous from the client's perspective via SSE polling). The tool
description tells the calling LLM this so it can decide whether to await
or kick off and poll separately.

Authentication is OPTIONAL — public read-only tools don't need it. If the
caller has a wr3 JWT, set WR3_AUTH_TOKEN to enable owner-scoped tools.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# --- Configuration ----------------------------------------------------------

DEFAULT_API_URL = "https://wr3.bigmandmitriy777.workers.dev/api"
DEFAULT_TIMEOUT = 30.0
SCAN_POLL_INTERVAL = 2.0
SCAN_POLL_TIMEOUT = 180.0  # 3 minutes — pipelines occasionally run long


def _api_base() -> str:
    """Where wr3 REST lives. CF Workers proxies /api/v1/* to the FastAPI.

    For self-hosted setups, point straight at the FastAPI origin
    (no /api prefix). The trailing slash is stripped so the caller can
    set either form.
    """
    return os.environ.get("WR3_API_URL", DEFAULT_API_URL).rstrip("/")


def _auth_headers() -> dict[str, str]:
    """Bearer header when WR3_AUTH_TOKEN is set, otherwise empty.

    The token comes from `POST /v1/auth/tg/login` after a Telegram WebApp
    login — operators can grab one by tapping through the Mini App and
    copying out of localStorage, OR by issuing a long-lived JWT manually.
    """
    token = os.environ.get("WR3_AUTH_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


# --- HTTP shim --------------------------------------------------------------

_client: httpx.AsyncClient | None = None


def _http() -> httpx.AsyncClient:
    """Module-singleton client. One client per MCP session = pooled TLS.

    MCP stdio servers are short-lived per session, so the client doesn't
    accumulate connections across users. We close it on shutdown.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=_api_base(),
            timeout=DEFAULT_TIMEOUT,
            headers=_auth_headers(),
        )
    return _client


def _v1(path: str) -> str:
    """Build a versioned URL: handles both proxied (`/api/v1/...`) and
    direct (`/v1/...`) base URLs without forcing the caller to know which.

    If base ends with `/api`, we add `/v1/<path>`.
    Otherwise (direct FastAPI), we add `/v1/<path>`.
    Same thing — but documenting it so the path constant is obvious."""
    return f"/v1/{path.lstrip('/')}"


async def _get_json(path: str, **params: Any) -> dict | list:
    r = await _http().get(_v1(path), params=params)
    r.raise_for_status()
    return r.json()


async def _post_json(path: str, payload: dict) -> dict:
    r = await _http().post(_v1(path), json=payload)
    r.raise_for_status()
    return r.json()


# --- Tool implementations ---------------------------------------------------


async def list_recent_incidents_impl(limit: int = 10, days: int = 60) -> str:
    """Live feed of real-world DeFi exploits, deduplicated across sources."""
    data = await _get_json("public/incidents", limit=limit, days=days)
    incidents = data.get("incidents", [])
    if not incidents:
        return "No incidents in the last %d days." % days

    lines = [f"# Recent incidents ({len(incidents)} of {data.get('total', '?')} in DB)\n"]
    for i in incidents:
        loss = i.get("loss_usd")
        loss_str = f" — ${loss:,}" if loss else ""
        date = (i.get("published_at") or "")[:10]
        lines.append(f"- **{i['title']}**{loss_str}  ({i['source']}, {date})")
        if i.get("url"):
            lines.append(f"  {i['url']}")
    return "\n".join(lines)


async def list_public_scans_impl(limit: int = 20, min_score: float | None = None) -> str:
    """Public leaderboard of completed audits, sorted by score."""
    params: dict[str, Any] = {"limit": limit}
    if min_score is not None:
        params["min_score"] = min_score
    rows = await _get_json("public/scans", **params)
    if not rows:
        return "No public scans available."
    lines = ["| # | Address | Network | Score | Tier |", "|---|---|---|---:|---|"]
    for n, s in enumerate(rows, 1):
        addr = s.get("address", "")
        short = addr[:10] + "…" + addr[-6:] if len(addr) > 18 else addr
        lines.append(
            f"| {n} | `{short}` | {s.get('network', '?')} | "
            f"{s.get('score', '—')} | {s.get('tier', '—')} |"
        )
    return "\n".join(lines)


async def get_public_stats_impl() -> str:
    """Aggregate counts: total scans, average score, severity totals."""
    s = await _get_json("public/stats")
    if not isinstance(s, dict):
        return f"Unexpected response: {s!r}"
    return (
        f"**Total scans:** {s.get('total_scans', 0)}\n"
        f"**Average score:** {s.get('avg_score', '—')}\n"
        f"**Critical findings:** {s.get('critical_findings', 0)}\n"
        f"**High findings:** {s.get('high_findings', 0)}\n"
        f"**Networks observed:** {s.get('networks_count', 0)}"
    )


async def get_scan_impl(scan_id: str) -> str:
    """Full audit report for a scan_id — findings, score breakdown, metadata."""
    if not scan_id or len(scan_id) < 8:
        return "scan_id is required (UUID format)."
    s = await _get_json(f"scan/{scan_id}")
    if not isinstance(s, dict):
        return f"Unexpected response: {s!r}"

    findings = s.get("findings", [])
    active = [f for f in findings if not f.get("dismissed")]
    by_sev: dict[str, int] = {}
    for f in active:
        by_sev[f.get("severity", "info")] = by_sev.get(f.get("severity", "info"), 0) + 1

    lines = [
        f"# Scan {scan_id}",
        f"- Address: `{s.get('address')}`",
        f"- Network: {s.get('network')}",
        f"- Stage: {s.get('stage')} (progress {s.get('progress', 0)}%)",
        f"- Score: {s.get('score', '—')} / 100  ({s.get('tier', '—')})",
        f"- Duration: {s.get('duration_seconds', '—')} s",
        f"- Findings (active): {len(active)}  ({', '.join(f'{n}x {k}' for k, n in sorted(by_sev.items())) or 'none'})",
    ]

    chain_meta = (s.get("report") or {}).get("chain_metadata") or {}
    if chain_meta.get("token_security"):
        ts = chain_meta["token_security"]
        lines.append("")
        lines.append("## GoPlus Tokenomics")
        for k in (
            "is_proxy",
            "is_honeypot",
            "is_mintable",
            "is_open_source",
            "hidden_owner",
            "can_take_back_ownership",
            "holder_count",
        ):
            if k in ts and ts[k] is not None:
                lines.append(f"- {k}: {ts[k]}")
    if chain_meta.get("upgradeable") is not None:
        lines.append("")
        lines.append("## Solana on-chain metadata")
        lines.append(f"- executable: {chain_meta.get('executable')}")
        lines.append(f"- upgradeable: {chain_meta.get('upgradeable')}")
        if chain_meta.get("upgrade_authority"):
            lines.append(f"- upgrade authority: `{chain_meta['upgrade_authority']}`")
        if chain_meta.get("last_upgrade_slot"):
            lines.append(f"- last upgrade slot: {chain_meta['last_upgrade_slot']:,}")

    # Top 5 findings
    if active:
        lines.append("")
        lines.append("## Top findings")
        for f in active[:5]:
            line_str = f":{f['line']}" if f.get("line") else ""
            lines.append(
                f"- **[{f.get('severity', '?')}]** {f.get('title', '')[:80]} "
                f"(`{f.get('source_engine', '?')}{line_str}`)"
            )

    return "\n".join(lines)


async def scan_contract_impl(
    address: str,
    network: str,
    source_code: str | None = None,
    wait: bool = True,
) -> str:
    """Start an audit, optionally block until done.

    For an EVM address, source is auto-fetched from Etherscan if verified.
    For Solana, source MUST be provided (no public verified-source registry).
    """
    if not address.strip():
        return "address is required"
    valid_networks = {"ethereum", "base", "arbitrum", "bsc", "solana"}
    if network not in valid_networks:
        return f"network must be one of {sorted(valid_networks)}"

    payload: dict[str, Any] = {"address": address.strip(), "network": network}
    if source_code:
        payload["source_code"] = source_code

    job = await _post_json("scan", payload)
    job_id = job.get("job_id")
    if not job_id:
        return f"Failed to start scan: {job!r}"

    if not wait:
        return (
            f"Scan queued.\nJob id: `{job_id}`\n"
            f"Poll progress: `get_scan_progress(job_id)` or `get_scan(scan_id)` "
            f"once you have it from the SSE stream."
        )

    # Poll for completion via the job progress endpoint. We don't use SSE
    # here because MCP clients don't speak event-stream — they expect a
    # single response per tool call.
    deadline = asyncio.get_event_loop().time() + SCAN_POLL_TIMEOUT
    scan_id: str | None = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            progress = await _get_json(f"scan/{job_id}/progress")
        except httpx.HTTPStatusError:
            await asyncio.sleep(SCAN_POLL_INTERVAL)
            continue
        scan_id = scan_id or progress.get("scan_id")
        stage = progress.get("stage", "?")
        if stage == "done":
            break
        if stage == "error":
            return f"Scan failed: {progress.get('message', 'unknown error')}"
        await asyncio.sleep(SCAN_POLL_INTERVAL)
    else:
        return (
            f"Scan still running after {SCAN_POLL_TIMEOUT}s. "
            f"Job id: `{job_id}` — poll separately with `get_scan` once it lands."
        )

    if not scan_id:
        return f"Scan completed but scan_id not returned (job {job_id})."

    # Return the full report now that it's ready.
    return await get_scan_impl(scan_id)


async def get_subscription_plans_impl() -> str:
    """List the buyable plans + their Telegram Stars price."""
    data = await _get_json("subscription/plans")
    plans = data.get("plans", []) if isinstance(data, dict) else []
    if not plans:
        return "No plans available."
    lines = ["| Plan | Stars | Period |", "|---|---:|---:|"]
    period = data.get("period_days", 30) if isinstance(data, dict) else 30
    for p in plans:
        lines.append(f"| {p['plan']} | {p['stars']} ⭐ | {period} d |")
    return "\n".join(lines)


# --- MCP server wiring ------------------------------------------------------

app = Server("wr3")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Tool catalog seen by the MCP client."""
    return [
        Tool(
            name="list_recent_incidents",
            description=(
                "List recent real-world DeFi exploits and hacks. Sources: Rekt News, "
                "SlowMist, DefiLlama. Deduplicated by semantic similarity. Use this "
                "to brief on the current threat landscape or check if a contract "
                "matches a known recent exploit pattern."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    "days": {"type": "integer", "default": 60, "minimum": 1, "maximum": 365},
                },
            },
        ),
        Tool(
            name="list_public_scans",
            description=(
                "List recent public smart-contract audits, sorted by score "
                "(lowest = highest risk). Use to find known-risky deployed "
                "contracts on a given network."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    "min_score": {"type": "number", "minimum": 0, "maximum": 100},
                },
            },
        ),
        Tool(
            name="get_public_stats",
            description="Aggregate platform stats: scan count, average score, severity totals.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_scan",
            description=(
                "Fetch the full audit report for an existing scan by id. Returns "
                "score, axes breakdown, list of findings with severities and "
                "source engines, and (where applicable) GoPlus Tokenomics signals "
                "or Solana on-chain metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scan_id": {"type": "string", "description": "UUID of the scan"},
                },
                "required": ["scan_id"],
            },
        ),
        Tool(
            name="scan_contract",
            description=(
                "Start a NEW smart-contract audit. Takes 30-120 seconds end-to-end. "
                "For EVM (ethereum/base/arbitrum/bsc) the verified source is fetched "
                "from Etherscan automatically. For Solana, you MUST pass source_code. "
                "With wait=true (default) this blocks until the audit completes and "
                "returns the full report; with wait=false you get a job_id to poll."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "address": {"type": "string"},
                    "network": {
                        "type": "string",
                        "enum": ["ethereum", "base", "arbitrum", "bsc", "solana"],
                    },
                    "source_code": {
                        "type": "string",
                        "description": "Optional — only required for Solana, optional override for EVM.",
                    },
                    "wait": {"type": "boolean", "default": True},
                },
                "required": ["address", "network"],
            },
        ),
        Tool(
            name="get_subscription_plans",
            description="List buyable plans and their Telegram Stars prices.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    args = arguments or {}
    try:
        if name == "list_recent_incidents":
            text = await list_recent_incidents_impl(
                limit=int(args.get("limit", 10)),
                days=int(args.get("days", 60)),
            )
        elif name == "list_public_scans":
            text = await list_public_scans_impl(
                limit=int(args.get("limit", 20)),
                min_score=args.get("min_score"),
            )
        elif name == "get_public_stats":
            text = await get_public_stats_impl()
        elif name == "get_scan":
            text = await get_scan_impl(scan_id=str(args.get("scan_id", "")))
        elif name == "scan_contract":
            text = await scan_contract_impl(
                address=str(args.get("address", "")),
                network=str(args.get("network", "")),
                source_code=args.get("source_code"),
                wait=bool(args.get("wait", True)),
            )
        elif name == "get_subscription_plans":
            text = await get_subscription_plans_impl()
        else:
            text = f"Unknown tool: {name}"
    except httpx.HTTPStatusError as e:
        text = (
            f"wr3 API returned HTTP {e.response.status_code}: "
            f"{e.response.text[:200]}\n\nCheck WR3_API_URL = {_api_base()}"
        )
    except httpx.HTTPError as e:
        text = f"wr3 API unreachable: {e}\n\nCheck WR3_API_URL = {_api_base()}"
    except Exception as e:  # noqa: BLE001
        text = f"Tool {name} failed: {type(e).__name__}: {e}"
    return [TextContent(type="text", text=text)]


# --- Entry point ------------------------------------------------------------


async def main() -> None:
    """Run the stdio MCP server. Closes the HTTP client on shutdown."""
    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        global _client
        if _client is not None:
            await _client.aclose()
            _client = None


def run() -> None:
    """Console entry point — wired in pyproject.toml as `wr3-mcp`."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
