"""GoPlus Security API client — multi-chain token risk metadata.

API: https://api.gopluslabs.io/api/v1/token_security/{chainId}
Docs: https://docs.gopluslabs.io/reference/api-overview

Why this exists: the Tokenomics / Centralization scoring axis in TZ.md §8.1
needs structured signals about (a) owner privileges, (b) proxy/upgrade
authority, (c) mint authority, (d) holder concentration, (e) honeypot
flags. GoPlus aggregates all of these across Ethereum / BSC / Base /
Arbitrum / Polygon / Solana behind one free public endpoint (~30 req/min
keyless, ~100 with free key).

This module is pure I/O — it fetches and normalises. Conversion to score
points lives in `audit_engine.scoring`. Keeping concerns separate so we
can A/B different scoring formulas without touching the fetcher.

Free tier: no key required at <30 req/min. With a free API key, ~100 req/min.
We pass GOPLUS_API_KEY when present but never block on its absence.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


# Chain ID mapping for GoPlus's URL path component. Their `1` = Ethereum
# mainnet, matching EIP-155. We only emit chains wr3 already audits.
_CHAIN_ID: dict[str, str] = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "base": "8453",
    # Solana is supported via a different endpoint
    # (token_security_solana) — handled separately, not in this module.
}

_BASE_URL = "https://api.gopluslabs.io/api/v1/token_security"


@dataclass
class TokenSecurity:
    """Normalised subset of GoPlus's response. Adds typed access vs the
    untyped JSON shape — easier to feed into scoring + reporting code."""

    address: str
    network: str

    # Basic identity
    token_name: str | None
    token_symbol: str | None

    # Centralization-related flags (all bool-ish: GoPlus returns "0"/"1"/None)
    is_open_source: bool | None
    is_proxy: bool | None
    is_mintable: bool | None
    can_take_back_ownership: bool | None
    owner_change_balance: bool | None
    hidden_owner: bool | None
    selfdestruct: bool | None
    external_call: bool | None

    # Honeypot / trading
    is_honeypot: bool | None
    honeypot_with_same_creator: bool | None
    buy_tax: float | None
    sell_tax: float | None
    transfer_tax: float | None
    cannot_buy: bool | None
    cannot_sell_all: bool | None
    slippage_modifiable: bool | None

    # Liquidity
    holder_count: int | None
    total_supply: float | None
    creator_address: str | None
    creator_percent: float | None  # top-creator holding as fraction of supply

    # Raw payload for the audit trail — never read by business code.
    raw: dict

    def to_dict(self) -> dict:
        """Stable serialization for storing in `Scan.report.token_security`."""
        return {
            "address": self.address,
            "network": self.network,
            "token_name": self.token_name,
            "token_symbol": self.token_symbol,
            "is_open_source": self.is_open_source,
            "is_proxy": self.is_proxy,
            "is_mintable": self.is_mintable,
            "can_take_back_ownership": self.can_take_back_ownership,
            "owner_change_balance": self.owner_change_balance,
            "hidden_owner": self.hidden_owner,
            "selfdestruct": self.selfdestruct,
            "external_call": self.external_call,
            "is_honeypot": self.is_honeypot,
            "honeypot_with_same_creator": self.honeypot_with_same_creator,
            "buy_tax": self.buy_tax,
            "sell_tax": self.sell_tax,
            "transfer_tax": self.transfer_tax,
            "cannot_buy": self.cannot_buy,
            "cannot_sell_all": self.cannot_sell_all,
            "slippage_modifiable": self.slippage_modifiable,
            "holder_count": self.holder_count,
            "total_supply": self.total_supply,
            "creator_address": self.creator_address,
            "creator_percent": self.creator_percent,
        }


def _to_bool(value) -> bool | None:
    """GoPlus uses string "0"/"1" / int 0/1 / None for boolean flags.
    Normalise to Python bool — None means "not evaluated by GoPlus".
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        return value == "1"
    return None


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    f = _to_float(value)
    return int(f) if f is not None else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def fetch_token_security(
    *, address: str, network: str, timeout: float = 15.0
) -> TokenSecurity | None:
    """Return GoPlus's risk profile for an EVM contract, or None if:
      - the network isn't supported by GoPlus (Solana — different endpoint)
      - GoPlus returns no result for this address (not a recognised token)
      - the upstream API errors out after retries

    Failure is silent at the audit-pipeline level — the scoring axis falls
    back to "pending evaluation" rather than blocking the scan.
    """
    chain_id = _CHAIN_ID.get(network)
    if chain_id is None:
        return None
    if not address.startswith("0x"):
        return None

    url = f"{_BASE_URL}/{chain_id}"
    params = {"contract_addresses": address.lower()}
    headers = {}
    if api_key := os.getenv("GOPLUS_API_KEY", "").strip():
        # Free-tier keys go in the Authorization header per GoPlus docs.
        headers["Authorization"] = api_key

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, params=params, headers=headers)
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPError as e:
        logger.warning("goplus.http_error", network=network, error=str(e))
        return None

    if payload.get("code") != 1:
        # GoPlus uses `code=1` for success. Anything else (typically
        # `code=4010` for "no data") means we have nothing useful.
        logger.info(
            "goplus.empty_or_error",
            network=network,
            code=payload.get("code"),
            message=payload.get("message"),
        )
        return None

    result = payload.get("result") or {}
    # The response is keyed by lower-cased address.
    record = result.get(address.lower()) or (next(iter(result.values()), None) if result else None)
    if not isinstance(record, dict):
        return None

    return TokenSecurity(
        address=address,
        network=network,
        token_name=record.get("token_name") or None,
        token_symbol=record.get("token_symbol") or None,
        is_open_source=_to_bool(record.get("is_open_source")),
        is_proxy=_to_bool(record.get("is_proxy")),
        is_mintable=_to_bool(record.get("is_mintable")),
        can_take_back_ownership=_to_bool(record.get("can_take_back_ownership")),
        owner_change_balance=_to_bool(record.get("owner_change_balance")),
        hidden_owner=_to_bool(record.get("hidden_owner")),
        selfdestruct=_to_bool(record.get("selfdestruct")),
        external_call=_to_bool(record.get("external_call")),
        is_honeypot=_to_bool(record.get("is_honeypot")),
        honeypot_with_same_creator=_to_bool(record.get("honeypot_with_same_creator")),
        buy_tax=_to_float(record.get("buy_tax")),
        sell_tax=_to_float(record.get("sell_tax")),
        transfer_tax=_to_float(record.get("transfer_tax")),
        cannot_buy=_to_bool(record.get("cannot_buy")),
        cannot_sell_all=_to_bool(record.get("cannot_sell_all")),
        slippage_modifiable=_to_bool(record.get("slippage_modifiable")),
        holder_count=_to_int(record.get("holder_count")),
        total_supply=_to_float(record.get("total_supply")),
        creator_address=record.get("creator_address") or None,
        creator_percent=_to_float(record.get("creator_percent")),
        raw=record,
    )


def compute_tokenomics_score(ts: TokenSecurity) -> tuple[float, str]:
    """Map a GoPlus profile to a 0-100 Tokenomics / Centralization score
    plus a human-readable rationale.

    Heuristic — calibrated to be conservative (we'd rather flag a benign
    contract than miss a real rug). Each red flag deducts from base 100:

        is_honeypot=True            => floor to 0     (terminal)
        cannot_sell_all=True        => floor to 0     (terminal)
        hidden_owner=True           => -30            (severe)
        can_take_back_ownership     => -25
        owner_change_balance        => -20
        is_mintable + not safe      => -15
        is_proxy (upgradeable)      => -10            (info, not always bad)
        selfdestruct present        => -15
        not is_open_source          => -10
        buy/sell tax > 10%          => -10 each
        creator_percent > 30%       => -10
    """
    # Honeypot or cannot-sell-all is a kill switch.
    if ts.is_honeypot or ts.cannot_sell_all:
        reasons = []
        if ts.is_honeypot:
            reasons.append("honeypot detected")
        if ts.cannot_sell_all:
            reasons.append("cannot sell all (likely scam)")
        return 0.0, "GoPlus: " + ", ".join(reasons)

    score = 100.0
    rationale_parts: list[str] = []

    def deduct(amount: float, reason: str) -> None:
        nonlocal score
        score -= amount
        rationale_parts.append(reason)

    if ts.hidden_owner:
        deduct(30, "hidden owner")
    if ts.can_take_back_ownership:
        deduct(25, "ownership can be reclaimed")
    if ts.owner_change_balance:
        deduct(20, "owner can change balances")
    if ts.is_mintable and not ts.hidden_owner:
        deduct(15, "mintable")
    if ts.is_proxy:
        deduct(10, "upgradeable proxy")
    if ts.selfdestruct:
        deduct(15, "selfdestruct present")
    if ts.is_open_source is False:
        deduct(10, "source not verified")
    if ts.buy_tax is not None and ts.buy_tax > 0.10:
        deduct(10, f"buy tax {int(ts.buy_tax * 100)}%")
    if ts.sell_tax is not None and ts.sell_tax > 0.10:
        deduct(10, f"sell tax {int(ts.sell_tax * 100)}%")
    if ts.creator_percent is not None and ts.creator_percent > 0.30:
        deduct(10, f"creator holds {int(ts.creator_percent * 100)}% of supply")

    score = max(0.0, min(100.0, score))
    rationale = (
        "GoPlus: " + "; ".join(rationale_parts)
        if rationale_parts
        else "GoPlus: no centralization red flags"
    )
    return round(score, 1), rationale


def compute_liquidity_score(ts: TokenSecurity) -> tuple[float, str] | None:
    """Liquidity Risk axis derived from GoPlus holder data.

    Same API call as the Tokenomics axis — no extra cost. Signals:
        holder_count        — more holders = wider distribution = less
                              rug-pull leverage by any single party
        creator_percent     — top-holder concentration
        cannot_buy / honeypot — terminal red flags (treated as 0)

    Returns None when GoPlus didn't provide holder data (some chains /
    new tokens), so the axis stays `(pending)` honestly rather than
    making up a number.
    """
    # Honeypot kills any liquidity claim: even if there are holders the
    # contract won't let them exit.
    if ts.is_honeypot or ts.cannot_buy or ts.cannot_sell_all:
        reasons = []
        if ts.is_honeypot:
            reasons.append("honeypot")
        if ts.cannot_buy:
            reasons.append("cannot buy")
        if ts.cannot_sell_all:
            reasons.append("cannot sell all")
        return 0.0, "GoPlus liquidity: " + ", ".join(reasons)

    # Without holder data we can't reason about liquidity at all.
    if ts.holder_count is None:
        return None

    score = 100.0
    parts: list[str] = []

    def deduct(amount: float, reason: str) -> None:
        nonlocal score
        score -= amount
        parts.append(reason)

    # Holder distribution. Calibrated against well-known tokens:
    # USDC holder_count ≈ 7M → no deduction; Pepe-tier memecoins ≈ 100K;
    # a brand-new ape token might have <100. Anyone below 100 holders is
    # an exit-liquidity trap in practice.
    h = ts.holder_count
    if h < 50:
        deduct(40, f"only {h} holders")
    elif h < 200:
        deduct(25, f"only {h} holders")
    elif h < 1_000:
        deduct(15, f"{h:,} holders (low)")
    elif h < 10_000:
        deduct(5, f"{h:,} holders")
    # else: 10k+ holders — no deduction

    # Top-creator concentration.
    if ts.creator_percent is not None:
        cp = ts.creator_percent
        if cp >= 0.50:
            deduct(35, f"creator holds {int(cp * 100)}% of supply")
        elif cp >= 0.30:
            deduct(20, f"creator holds {int(cp * 100)}% of supply")
        elif cp >= 0.10:
            deduct(10, f"creator holds {int(cp * 100)}% of supply")

    # Tradeability — high taxes effectively reduce exit liquidity even
    # when holders are otherwise diverse.
    if ts.sell_tax is not None and ts.sell_tax > 0.15:
        deduct(15, f"sell tax {int(ts.sell_tax * 100)}% restricts exits")
    elif ts.sell_tax is not None and ts.sell_tax > 0.05:
        deduct(5, f"sell tax {int(ts.sell_tax * 100)}%")

    score = max(0.0, min(100.0, score))
    rationale = (
        "GoPlus liquidity: " + "; ".join(parts)
        if parts
        else "GoPlus liquidity: distributed holder base, low concentration"
    )
    return round(score, 1), rationale
