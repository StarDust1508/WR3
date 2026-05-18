"""DeFiLlama TVL enrichment — free API, no auth required.

The On-chain Behavior scoring axis (TZ SS8.1) benefits from TVL data:
a protocol with $50M locked that has been stable for months is fundamentally
different from one whose TVL just dropped 80% overnight.

DeFiLlama exposes two free endpoints we use:
    GET https://api.llama.fi/protocols   — full list (~2MB), cached 1 hour
    GET https://api.llama.fi/protocol/{slug} — per-protocol TVL history

Matching strategy: the /protocols list includes chain-level address mappings.
We match our contract address against those (case-insensitive) to find the
protocol slug, then pull the detailed TVL history for 7d/30d change analysis.

No API key required. Rate limits are generous for read-only access.
"""

from __future__ import annotations

import time

import httpx
import structlog

logger = structlog.get_logger()

_defillama_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _defillama_client
    if _defillama_client is None:
        _defillama_client = httpx.AsyncClient(timeout=20.0)
    return _defillama_client


_BASE_URL = "https://api.llama.fi"

# DeFiLlama uses title-case chain names; our pipeline uses lowercase.
_CHAIN_MAP: dict[str, str] = {
    "ethereum": "Ethereum",
    "bsc": "BSC",
    "arbitrum": "Arbitrum",
    "base": "Base",
    "solana": "Solana",
    "polygon": "Polygon",
    "avalanche": "Avalanche",
    "optimism": "Optimism",
}

# --- protocols list cache (1 hour TTL) ------------------------------------

_protocols_cache: list[dict] | None = None
_protocols_cache_ts: float = 0.0
_CACHE_TTL_SECONDS = 3600  # 1 hour


async def _get_protocols() -> list[dict]:
    """Fetch and cache the full protocols list from DeFiLlama.

    The list is ~2MB and rarely changes, so we cache it for 1 hour.
    Returns an empty list on any failure (graceful degradation).
    """
    global _protocols_cache, _protocols_cache_ts

    now = time.monotonic()
    if _protocols_cache is not None and (now - _protocols_cache_ts) < _CACHE_TTL_SECONDS:
        return _protocols_cache

    try:
        client = _get_client()
        r = await client.get(f"{_BASE_URL}/protocols")
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
        logger.warning("defillama.protocols_fetch_error", error=str(e))
        # Return stale cache if available, otherwise empty.
        return _protocols_cache if _protocols_cache is not None else []

    if not isinstance(data, list):
        logger.warning("defillama.protocols_unexpected_shape", type=type(data).__name__)
        return _protocols_cache if _protocols_cache is not None else []

    _protocols_cache = data
    _protocols_cache_ts = now
    logger.info("defillama.protocols_cached", count=len(data))
    return _protocols_cache


def _find_protocol_by_address(
    protocols: list[dict], address: str, chain: str
) -> dict | None:
    """Match a contract address to a DeFiLlama protocol entry.

    DeFiLlama stores chain-specific addresses in the protocol object under
    the key ``address`` (primary) and ``chainAddresses`` (per-chain overrides).
    Format varies: sometimes bare hex, sometimes ``chain:0xABC``.

    We do case-insensitive matching because EVM addresses are case-insensitive.
    """
    addr_lower = address.lower()

    for protocol in protocols:
        # Check chainAddresses first (more specific).
        chain_addrs = protocol.get("chainAddresses") or {}
        chain_addr = chain_addrs.get(chain) or chain_addrs.get(chain.lower())
        if chain_addr and addr_lower in chain_addr.lower():
            return protocol

        # Check the primary ``address`` field.
        primary = protocol.get("address") or ""
        if primary and addr_lower in primary.lower():
            return protocol

    return None


async def _fetch_protocol_detail(slug: str) -> dict | None:
    """Fetch detailed protocol data including TVL history."""
    try:
        client = _get_client()
        r = await client.get(f"{_BASE_URL}/protocol/{slug}")
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, httpx.TimeoutException, ValueError) as e:
        logger.warning("defillama.protocol_detail_error", slug=slug, error=str(e))
        return None

    if not isinstance(data, dict):
        return None
    return data


def _compute_tvl_change(tvl_history: list[dict], days: int) -> float | None:
    """Compute TVL % change over the last N days from the TVL history.

    Each entry in tvl_history is ``{"date": unix_ts, "totalLiquidityUSD": float}``.
    Returns None if insufficient data.
    """
    if not tvl_history or len(tvl_history) < 2:
        return None

    current_tvl = tvl_history[-1].get("totalLiquidityUSD")
    if current_tvl is None or current_tvl == 0:
        return None

    # Find the entry closest to N days ago.
    target_ts = tvl_history[-1]["date"] - (days * 86400)
    best_entry = None
    best_diff = float("inf")
    for entry in tvl_history:
        diff = abs(entry["date"] - target_ts)
        if diff < best_diff:
            best_diff = diff
            best_entry = entry

    if best_entry is None:
        return None

    past_tvl = best_entry.get("totalLiquidityUSD")
    if past_tvl is None or past_tvl == 0:
        return None

    return ((current_tvl - past_tvl) / past_tvl) * 100.0


async def fetch_tvl_signals(address: str, network: str) -> dict | None:
    """Try to match the contract address to a DeFiLlama protocol and return
    TVL signals for the On-chain Behavior scoring axis.

    Returns a dict with keys:
        - current_tvl_usd: float
        - tvl_7d_change_pct: float (negative = declining)
        - tvl_30d_change_pct: float
        - protocol_name: str
        - category: str (e.g. "DEX", "Lending", "Bridge")
        - is_listed: bool (whether this address appears in DeFiLlama at all)

    Returns None if no match found or API unreachable.
    """
    chain = _CHAIN_MAP.get(network)
    if chain is None:
        logger.info("defillama.unsupported_network", network=network)
        return None

    protocols = await _get_protocols()
    if not protocols:
        return None

    protocol = _find_protocol_by_address(protocols, address, chain)
    if protocol is None:
        logger.info("defillama.no_match", address=address, network=network)
        return None

    slug = protocol.get("slug")
    if not slug:
        return None

    # Basic signals from the protocols list (no extra request needed).
    current_tvl = protocol.get("tvl") or 0.0
    category = protocol.get("category") or "Unknown"
    name = protocol.get("name") or slug

    # Fetch detailed history for trend analysis.
    detail = await _fetch_protocol_detail(slug)

    tvl_7d_change: float | None = None
    tvl_30d_change: float | None = None

    if detail is not None:
        tvl_history = detail.get("tvl") or []
        tvl_7d_change = _compute_tvl_change(tvl_history, 7)
        tvl_30d_change = _compute_tvl_change(tvl_history, 30)

        # Prefer the detail endpoint's current TVL if available.
        if tvl_history:
            latest = tvl_history[-1].get("totalLiquidityUSD")
            if latest is not None:
                current_tvl = latest

    return {
        "current_tvl_usd": float(current_tvl),
        "tvl_7d_change_pct": round(tvl_7d_change, 2) if tvl_7d_change is not None else None,
        "tvl_30d_change_pct": round(tvl_30d_change, 2) if tvl_30d_change is not None else None,
        "protocol_name": name,
        "category": category,
        "is_listed": True,
    }


def compute_tvl_score(signals: dict | None) -> tuple[float, str]:
    """Score 0-100 based on TVL signals for the On-chain Behavior axis.

    Scoring bands:
        Not listed on DeFiLlama:    30  (unknown, moderate risk)
        TVL > $10M and stable:      90+ (established protocol)
        TVL > $1M and stable:       70  (mid-tier)
        TVL > $100K:                55  (small but present)
        TVL < $100K:                40  (low liquidity risk)

    Crisis overrides (applied last, floor the score):
        TVL drop >50% in 7 days:    floor at 10
        TVL drop >30% in 7 days:    floor at 20
    """
    if signals is None or not signals.get("is_listed"):
        return 30.0, "DeFiLlama: protocol not listed (unknown TVL)"

    tvl = signals.get("current_tvl_usd") or 0.0
    name = signals.get("protocol_name", "unknown")
    category = signals.get("category", "Unknown")
    change_7d = signals.get("tvl_7d_change_pct")
    change_30d = signals.get("tvl_30d_change_pct")

    # Base score from TVL magnitude.
    if tvl >= 100_000_000:
        score = 95.0
        rationale = f"DeFiLlama: {name} ({category}) TVL ${tvl / 1e6:.1f}M — large protocol"
    elif tvl >= 10_000_000:
        score = 90.0
        rationale = f"DeFiLlama: {name} ({category}) TVL ${tvl / 1e6:.1f}M — established"
    elif tvl >= 1_000_000:
        score = 70.0
        rationale = f"DeFiLlama: {name} ({category}) TVL ${tvl / 1e6:.1f}M — mid-tier"
    elif tvl >= 100_000:
        score = 55.0
        rationale = f"DeFiLlama: {name} ({category}) TVL ${tvl / 1e3:.0f}K — small"
    else:
        score = 40.0
        rationale = f"DeFiLlama: {name} ({category}) TVL ${tvl:,.0f} — low liquidity risk"

    # Trend adjustments.
    trend_parts: list[str] = []
    if change_7d is not None:
        if change_7d > 10:
            score = min(score + 5, 100.0)
            trend_parts.append(f"7d +{change_7d:.1f}%")
        elif change_7d < -10:
            score = max(score - 10, 0.0)
            trend_parts.append(f"7d {change_7d:.1f}%")

    if change_30d is not None:
        if change_30d > 20:
            score = min(score + 5, 100.0)
            trend_parts.append(f"30d +{change_30d:.1f}%")
        elif change_30d < -20:
            score = max(score - 10, 0.0)
            trend_parts.append(f"30d {change_30d:.1f}%")

    # Crisis overrides — these floor the score regardless of magnitude.
    if change_7d is not None and change_7d <= -50:
        score = min(score, 10.0)
        trend_parts.append("CRISIS: >50% TVL drop in 7d")
    elif change_7d is not None and change_7d <= -30:
        score = min(score, 20.0)
        trend_parts.append("WARNING: >30% TVL drop in 7d")

    if trend_parts:
        rationale += " | " + ", ".join(trend_parts)

    return round(score, 1), rationale
