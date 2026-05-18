"""DexScreener liquidity enrichment — free API, no auth.

API: GET https://api.dexscreener.com/tokens/v1/{chainId}/{tokenAddress}
Docs: https://docs.dexscreener.com/api/reference

Why this exists: the Liquidity scoring axis in TZ.md §8.1 needs on-chain
DEX pair data — total pooled liquidity, 24h volume, price movement, and
pair count. DexScreener aggregates across all major DEXes (Uniswap,
SushiSwap, PancakeSwap, Raydium, etc.) behind one free endpoint with
~300 req/min rate limit, no auth required.

This module is pure I/O — it fetches and normalises. The
`compute_liquidity_score` helper converts signals to a 0-100 axis score,
but the canonical scoring pipeline lives in `audit_engine.scoring`.
"""

from __future__ import annotations

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

_dexscreener_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _dexscreener_client
    if _dexscreener_client is None:
        _dexscreener_client = httpx.AsyncClient(timeout=15.0)
    return _dexscreener_client


# DexScreener uses human-readable chain slugs in URLs.
_CHAIN_SLUG: dict[str, str] = {
    "ethereum": "ethereum",
    "base": "base",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
    "solana": "solana",
}

_BASE_URL = "https://api.dexscreener.com/tokens/v1"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def fetch_liquidity_signals(address: str, network: str) -> dict | None:
    """Fetch DEX pair data for a token/contract address.

    Returns a dict with:
        - total_liquidity_usd: float  (sum across all pairs)
        - pair_count: int
        - top_pair_name: str          (e.g. "WETH / TOKEN")
        - top_pair_dex: str           (e.g. "uniswap")
        - price_usd: float | None
        - volume_24h_usd: float
        - price_change_24h_pct: float
        - fdv_usd: float | None       (fully diluted valuation)

    Returns None if:
        - network is not supported by DexScreener
        - no pairs found for this address
        - the upstream API errors out after retries
    """
    chain_slug = _CHAIN_SLUG.get(network)
    if chain_slug is None:
        logger.info("dexscreener.unsupported_network", network=network)
        return None

    url = f"{_BASE_URL}/{chain_slug}/{address}"

    try:
        client = _get_client()
        r = await client.get(url)
        r.raise_for_status()
        pairs = r.json()
    except httpx.HTTPError as e:
        logger.warning("dexscreener.http_error", network=network, error=str(e))
        return None

    # The API returns a JSON array of pair objects directly (not wrapped).
    if not isinstance(pairs, list) or len(pairs) == 0:
        logger.info("dexscreener.no_pairs", network=network, address=address)
        return None

    total_liquidity = 0.0
    total_volume_24h = 0.0
    top_pair = None
    top_liquidity = -1.0

    for pair in pairs:
        liq = pair.get("liquidity", {})
        pair_liq = liq.get("usd") or 0.0
        total_liquidity += pair_liq

        vol_24h = pair.get("volume", {})
        total_volume_24h += vol_24h.get("h24") or 0.0

        if pair_liq > top_liquidity:
            top_liquidity = pair_liq
            top_pair = pair

    if top_pair is None:
        return None

    # Price change: use the top pair's 24h change.
    price_change = top_pair.get("priceChange", {})
    price_change_24h = price_change.get("h24") or 0.0

    return {
        "total_liquidity_usd": total_liquidity,
        "pair_count": len(pairs),
        "top_pair_name": f"{top_pair.get('baseToken', {}).get('symbol', '?')} / {top_pair.get('quoteToken', {}).get('symbol', '?')}",
        "top_pair_dex": top_pair.get("dexId", "unknown"),
        "price_usd": _safe_float(top_pair.get("priceUsd")),
        "volume_24h_usd": total_volume_24h,
        "price_change_24h_pct": float(price_change_24h),
        "fdv_usd": _safe_float(top_pair.get("fdv")),
    }


def _safe_float(value) -> float | None:
    """Convert to float or None, never raise."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def compute_liquidity_score(signals: dict | None) -> tuple[float, str]:
    """Score 0-100 for the Liquidity axis based on DexScreener data.

    Heuristic:
        No DEX pairs found              → 20 (not tradeable = high risk)
        Total liquidity > $1M           → 85+
        Total liquidity > $100K         → 65
        Total liquidity > $10K          → 45
        Total liquidity < $10K          → 25 (exit trap)
        Volume/liquidity ratio > 5      → bonus +10 (healthy trading)
        Price drop >50% in 24h          → cap at 30
    """
    if signals is None:
        return 20.0, "DexScreener: no DEX pairs found — token may not be tradeable"

    liq = signals["total_liquidity_usd"]
    vol = signals["volume_24h_usd"]
    price_change = signals["price_change_24h_pct"]
    pair_count = signals["pair_count"]

    # Base score from total liquidity.
    if liq >= 1_000_000:
        score = 85.0
    elif liq >= 100_000:
        score = 65.0
    elif liq >= 10_000:
        score = 45.0
    else:
        score = 25.0

    rationale_parts: list[str] = []
    rationale_parts.append(f"${liq:,.0f} total liquidity across {pair_count} pair(s)")

    # Volume/liquidity ratio bonus — healthy trading activity.
    if liq > 0:
        vl_ratio = vol / liq
        if vl_ratio > 5.0:
            score += 10.0
            rationale_parts.append(f"V/L ratio {vl_ratio:.1f} (active trading)")

    # Large liquidity bonus: >$10M is very healthy.
    if liq >= 10_000_000:
        score += 5.0
        rationale_parts.append("deep liquidity (>$10M)")

    # Price crash penalty — 24h drop > 50% is a rug signal.
    if price_change <= -50.0:
        score = min(score, 30.0)
        rationale_parts.append(f"price crashed {price_change:.0f}% in 24h")

    score = max(0.0, min(100.0, score))
    rationale = "DexScreener: " + "; ".join(rationale_parts)
    return round(score, 1), rationale
