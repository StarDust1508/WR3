"""Token holder concentration analysis via Etherscan V2 API.

Complements GoPlus's holder_count / creator_percent with the actual
top-10 holder breakdown from Etherscan's ``tokenholderlist`` endpoint.
This gives a much sharper rug-pull signal: if 3 wallets control 80 %
of supply, that's critical regardless of how many dust-amount holders
GoPlus counts.

Endpoint (free tier, same key as etherscan_meta):
    GET https://api.etherscan.io/v2/api
        ?chainid={chainId}
        &module=token
        &action=tokenholderlist
        &contractaddress={address}
        &page=1&offset=10
        &apikey={key}

Returns top-10 holders with ``TokenHolderAddress``, ``TokenHolderQuantity``,
and ``Share`` (percentage string like ``"12.3456%"``).

Solana is unsupported (Etherscan doesn't cover it).
"""

from __future__ import annotations

import os

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

_holder_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _holder_client
    if _holder_client is None:
        _holder_client = httpx.AsyncClient(timeout=15.0)
    return _holder_client


_ETHERSCAN_V2 = "https://api.etherscan.io/v2/api"

_CHAIN_IDS: dict[str, int] = {
    "ethereum": 1,
    "bsc": 56,
    "polygon": 137,
    "base": 8453,
    "arbitrum": 42161,
}


def _parse_share(raw: str | None) -> float:
    """Parse Etherscan share string like ``"12.3456%"`` into a float 12.3456.

    Returns 0.0 on any parse failure so callers never crash.
    """
    if not raw:
        return 0.0
    try:
        cleaned = raw.strip().rstrip("%").strip()
        return float(cleaned)
    except (TypeError, ValueError):
        return 0.0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def fetch_holder_signals(
    address: str,
    network: str,
    *,
    deployer_address: str | None = None,
) -> dict | None:
    """Fetch top-10 token holders from Etherscan V2.

    Returns a dict with:
        top10_pct           – float, combined percentage held by top 10
        top1_pct            – float, largest single holder percentage
        deployer_is_top_holder – bool, True if deployer_address is among top 10
        holders             – list of {address, share_pct} dicts (raw data)
        concentration_risk  – "low" | "medium" | "high" | "critical"

    Returns ``None`` when:
        - network is Solana or otherwise unsupported
        - address doesn't look like an EVM hex address
        - ETHERSCAN_API_KEY is missing
        - Etherscan returns an error / no data (token not ERC-20, etc.)
    """
    chain_id = _CHAIN_IDS.get(network)
    if chain_id is None or not address.startswith("0x"):
        return None

    api_key = os.getenv("ETHERSCAN_API_KEY", "").strip()
    if not api_key:
        logger.info("holder_concentration.no_api_key")
        return None

    params = {
        "chainid": chain_id,
        "module": "token",
        "action": "tokenholderlist",
        "contractaddress": address.lower(),
        "page": 1,
        "offset": 10,
        "apikey": api_key,
    }

    try:
        client = _get_client()
        r = await client.get(_ETHERSCAN_V2, params=params)
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPError as exc:
        logger.warning("holder_concentration.http_error", error=str(exc))
        return None

    if data.get("status") != "1":
        logger.info(
            "holder_concentration.empty",
            message=data.get("message"),
            result=data.get("result"),
        )
        return None

    rows = data.get("result")
    if not isinstance(rows, list) or not rows:
        return None

    holders: list[dict] = []
    for row in rows:
        share = _parse_share(row.get("Share"))
        holders.append(
            {
                "address": (row.get("TokenHolderAddress") or "").lower(),
                "share_pct": share,
            }
        )

    top10_pct = sum(h["share_pct"] for h in holders)
    top1_pct = holders[0]["share_pct"] if holders else 0.0

    deployer_is_top = False
    if deployer_address:
        deployer_lower = deployer_address.lower()
        deployer_is_top = any(h["address"] == deployer_lower for h in holders)

    # Classify risk
    if top10_pct > 70 or top1_pct > 50:
        risk = "critical"
    elif top10_pct > 50:
        risk = "high"
    elif top10_pct > 30:
        risk = "medium"
    else:
        risk = "low"

    return {
        "top10_pct": round(top10_pct, 4),
        "top1_pct": round(top1_pct, 4),
        "deployer_is_top_holder": deployer_is_top,
        "holders": holders,
        "concentration_risk": risk,
    }


def compute_concentration_score(signals: dict | None) -> tuple[float, str]:
    """Score 0-100 for the Tokenomics axis enhancement based on holder concentration.

    Bands (top-10 combined percentage):
        < 30 %    -> 90  (well distributed)
        30-50 %   -> 70  (moderate concentration)
        50-70 %   -> 45  (high concentration, rug risk)
        > 70 %    -> 20  (critical concentration)

    Overrides:
        top1 > 50 % -> floor at 15 (single entity controls majority)
        deployer is top holder -> penalty -15

    Returns ``(score, rationale_string)``.
    When ``signals`` is ``None`` (Solana, API failure, etc.), returns a
    neutral ``(50.0, ...)`` so the axis doesn't tank or inflate unfairly.
    """
    if signals is None:
        return 50.0, "Holder concentration: data unavailable, neutral score"

    top10 = signals["top10_pct"]
    top1 = signals["top1_pct"]
    deployer_top = signals["deployer_is_top_holder"]
    risk = signals["concentration_risk"]

    # Base score from top-10 band
    if top10 < 30:
        score = 90.0
        rationale = f"Top-10 holders own {top10:.1f}% (well distributed)"
    elif top10 <= 50:
        score = 70.0
        rationale = f"Top-10 holders own {top10:.1f}% (moderate concentration)"
    elif top10 <= 70:
        score = 45.0
        rationale = f"Top-10 holders own {top10:.1f}% (high concentration)"
    else:
        score = 20.0
        rationale = f"Top-10 holders own {top10:.1f}% (critical concentration)"

    # Single-entity override
    if top1 > 50:
        score = min(score, 15.0)
        rationale += f"; top holder alone owns {top1:.1f}%"

    # Deployer penalty
    if deployer_top:
        score = max(0.0, score - 15.0)
        rationale += "; deployer is a top holder (-15)"

    score = max(0.0, min(100.0, score))
    return round(score, 1), f"Holder concentration: {rationale} [risk={risk}]"
