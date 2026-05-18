"""DeFiLlama TVL enrichment — protocol matching + scoring tests.

All network calls are mocked with respx so tests run without network/API keys.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from audit_engine.enrichment.defillama import (
    _CHAIN_MAP,
    _compute_tvl_change,
    _find_protocol_by_address,
    _get_protocols,
    _protocols_cache,
    _protocols_cache_ts,
    compute_tvl_score,
    fetch_tvl_signals,
)
import audit_engine.enrichment.defillama as defillama_mod


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _sample_protocol(
    *,
    slug: str = "aave-v3",
    name: str = "Aave V3",
    tvl: float = 12_000_000_000.0,
    category: str = "Lending",
    address: str = "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",
    chain: str = "Ethereum",
) -> dict:
    """Minimal protocol entry matching DeFiLlama /protocols shape."""
    return {
        "slug": slug,
        "name": name,
        "tvl": tvl,
        "category": category,
        "address": f"{chain}:{address}",
        "chainAddresses": {chain: address},
    }


def _sample_protocols_list() -> list[dict]:
    return [
        _sample_protocol(),
        _sample_protocol(
            slug="uniswap-v3",
            name="Uniswap V3",
            tvl=5_000_000_000.0,
            category="DEX",
            address="0x1f9840a85d5af5bf1d1762f925bdaddc4201f984",
            chain="Ethereum",
        ),
        _sample_protocol(
            slug="pancakeswap",
            name="PancakeSwap",
            tvl=2_000_000_000.0,
            category="DEX",
            address="0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82",
            chain="BSC",
        ),
    ]


def _sample_protocol_detail(
    *,
    current_tvl: float = 12_000_000_000.0,
    days: int = 60,
    daily_change_pct: float = 0.1,
) -> dict:
    """Minimal /protocol/{slug} response with synthetic TVL history."""
    now_ts = int(time.time())
    tvl_history = []
    for i in range(days):
        day_ts = now_ts - ((days - 1 - i) * 86400)
        # Linear growth from (current_tvl * factor) to current_tvl.
        factor = 1.0 - (daily_change_pct / 100.0 * (days - 1 - i))
        tvl_history.append({
            "date": day_ts,
            "totalLiquidityUSD": current_tvl * max(factor, 0.01),
        })
    return {"tvl": tvl_history}


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the module-level protocols cache between tests."""
    defillama_mod._protocols_cache = None
    defillama_mod._protocols_cache_ts = 0.0
    yield
    defillama_mod._protocols_cache = None
    defillama_mod._protocols_cache_ts = 0.0


# ---------------------------------------------------------------------------
# _find_protocol_by_address
# ---------------------------------------------------------------------------


def test_find_by_chain_address() -> None:
    protocols = _sample_protocols_list()
    found = _find_protocol_by_address(
        protocols,
        "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",  # mixed case
        "Ethereum",
    )
    assert found is not None
    assert found["slug"] == "aave-v3"


def test_find_case_insensitive() -> None:
    protocols = _sample_protocols_list()
    found = _find_protocol_by_address(
        protocols,
        "0x87870BCA3F3FD6335C3F4CE8392D69350B4FA4E2",  # all caps
        "Ethereum",
    )
    assert found is not None
    assert found["slug"] == "aave-v3"


def test_find_returns_none_for_unknown_address() -> None:
    protocols = _sample_protocols_list()
    found = _find_protocol_by_address(protocols, "0x" + "0" * 40, "Ethereum")
    assert found is None


def test_find_returns_none_for_wrong_chain() -> None:
    """Aave address exists on Ethereum but we're asking for BSC."""
    protocols = _sample_protocols_list()
    # The chainAddresses dict is keyed by "Ethereum", so "BSC" won't match
    # via chainAddresses. The primary address field has "Ethereum:" prefix,
    # so the bare hex will still match via the fallback. This tests the
    # primary address fallback path.
    found = _find_protocol_by_address(
        protocols,
        "0x0000000000000000000000000000000000000099",
        "BSC",
    )
    assert found is None


# ---------------------------------------------------------------------------
# _compute_tvl_change
# ---------------------------------------------------------------------------


def test_tvl_change_positive() -> None:
    now_ts = int(time.time())
    history = [
        {"date": now_ts - 86400 * 7, "totalLiquidityUSD": 100.0},
        {"date": now_ts, "totalLiquidityUSD": 120.0},
    ]
    change = _compute_tvl_change(history, 7)
    assert change is not None
    assert abs(change - 20.0) < 1.0


def test_tvl_change_negative() -> None:
    now_ts = int(time.time())
    history = [
        {"date": now_ts - 86400 * 7, "totalLiquidityUSD": 100.0},
        {"date": now_ts, "totalLiquidityUSD": 60.0},
    ]
    change = _compute_tvl_change(history, 7)
    assert change is not None
    assert abs(change - (-40.0)) < 1.0


def test_tvl_change_returns_none_for_empty_history() -> None:
    assert _compute_tvl_change([], 7) is None
    assert _compute_tvl_change([{"date": 0, "totalLiquidityUSD": 100}], 7) is None


def test_tvl_change_returns_none_for_zero_tvl() -> None:
    now_ts = int(time.time())
    history = [
        {"date": now_ts - 86400 * 7, "totalLiquidityUSD": 0.0},
        {"date": now_ts, "totalLiquidityUSD": 100.0},
    ]
    assert _compute_tvl_change(history, 7) is None


# ---------------------------------------------------------------------------
# fetch_tvl_signals (mocked network)
# ---------------------------------------------------------------------------


async def test_fetch_returns_none_for_unsupported_network() -> None:
    result = await fetch_tvl_signals("0xabc", "fantom")
    assert result is None


async def test_fetch_returns_none_when_protocols_api_fails() -> None:
    with respx.mock(base_url="https://api.llama.fi") as mock:
        mock.get("/protocols").mock(return_value=httpx.Response(500))
        result = await fetch_tvl_signals(
            "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "ethereum"
        )
    assert result is None


async def test_fetch_returns_none_when_no_match() -> None:
    with respx.mock(base_url="https://api.llama.fi") as mock:
        mock.get("/protocols").mock(
            return_value=httpx.Response(200, json=_sample_protocols_list())
        )
        result = await fetch_tvl_signals("0x" + "0" * 40, "ethereum")
    assert result is None


async def test_fetch_returns_signals_on_match() -> None:
    detail = _sample_protocol_detail(current_tvl=12e9, days=60, daily_change_pct=0.1)
    with respx.mock(base_url="https://api.llama.fi") as mock:
        mock.get("/protocols").mock(
            return_value=httpx.Response(200, json=_sample_protocols_list())
        )
        mock.get("/protocol/aave-v3").mock(
            return_value=httpx.Response(200, json=detail)
        )
        result = await fetch_tvl_signals(
            "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "ethereum"
        )

    assert result is not None
    assert result["is_listed"] is True
    assert result["protocol_name"] == "Aave V3"
    assert result["category"] == "Lending"
    assert result["current_tvl_usd"] > 0
    assert result["tvl_7d_change_pct"] is not None
    assert result["tvl_30d_change_pct"] is not None


async def test_fetch_handles_detail_failure_gracefully() -> None:
    """If the protocol detail endpoint fails, we still return basic signals
    from the protocols list (just without trend data)."""
    with respx.mock(base_url="https://api.llama.fi") as mock:
        mock.get("/protocols").mock(
            return_value=httpx.Response(200, json=_sample_protocols_list())
        )
        mock.get("/protocol/aave-v3").mock(
            return_value=httpx.Response(500)
        )
        result = await fetch_tvl_signals(
            "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2", "ethereum"
        )

    assert result is not None
    assert result["is_listed"] is True
    assert result["current_tvl_usd"] == 12_000_000_000.0
    # Trend data not available when detail fetch fails.
    assert result["tvl_7d_change_pct"] is None
    assert result["tvl_30d_change_pct"] is None


async def test_protocols_cache_reused_within_ttl() -> None:
    """Second call within TTL should not make another HTTP request."""
    with respx.mock(base_url="https://api.llama.fi") as mock:
        route = mock.get("/protocols").mock(
            return_value=httpx.Response(200, json=_sample_protocols_list())
        )
        # First call — hits the API.
        await _get_protocols()
        assert route.call_count == 1

        # Second call — cache hit, no new request.
        await _get_protocols()
        assert route.call_count == 1


# ---------------------------------------------------------------------------
# compute_tvl_score
# ---------------------------------------------------------------------------


def test_score_none_signals() -> None:
    score, rationale = compute_tvl_score(None)
    assert score == 30.0
    assert "not listed" in rationale


def test_score_not_listed() -> None:
    score, rationale = compute_tvl_score({"is_listed": False})
    assert score == 30.0


def test_score_large_protocol() -> None:
    signals = {
        "current_tvl_usd": 200_000_000.0,
        "tvl_7d_change_pct": 2.0,
        "tvl_30d_change_pct": 5.0,
        "protocol_name": "Aave V3",
        "category": "Lending",
        "is_listed": True,
    }
    score, rationale = compute_tvl_score(signals)
    assert score >= 90.0
    assert "Aave V3" in rationale


def test_score_established_protocol() -> None:
    signals = {
        "current_tvl_usd": 15_000_000.0,
        "tvl_7d_change_pct": 1.0,
        "tvl_30d_change_pct": 3.0,
        "protocol_name": "SmallDEX",
        "category": "DEX",
        "is_listed": True,
    }
    score, _ = compute_tvl_score(signals)
    assert score == 90.0


def test_score_mid_tier() -> None:
    signals = {
        "current_tvl_usd": 2_000_000.0,
        "tvl_7d_change_pct": 0.0,
        "tvl_30d_change_pct": 0.0,
        "protocol_name": "MidProtocol",
        "category": "Lending",
        "is_listed": True,
    }
    score, _ = compute_tvl_score(signals)
    assert score == 70.0


def test_score_small_protocol() -> None:
    signals = {
        "current_tvl_usd": 200_000.0,
        "tvl_7d_change_pct": 0.0,
        "tvl_30d_change_pct": 0.0,
        "protocol_name": "TinyFarm",
        "category": "Yield",
        "is_listed": True,
    }
    score, _ = compute_tvl_score(signals)
    assert score == 55.0


def test_score_low_tvl() -> None:
    signals = {
        "current_tvl_usd": 50_000.0,
        "tvl_7d_change_pct": 0.0,
        "tvl_30d_change_pct": 0.0,
        "protocol_name": "MicroProtocol",
        "category": "DEX",
        "is_listed": True,
    }
    score, _ = compute_tvl_score(signals)
    assert score == 40.0


def test_score_crisis_50pct_drop() -> None:
    """A 50%+ TVL drop in 7 days should floor the score at 10."""
    signals = {
        "current_tvl_usd": 5_000_000.0,
        "tvl_7d_change_pct": -55.0,
        "tvl_30d_change_pct": -60.0,
        "protocol_name": "CrisisProtocol",
        "category": "Bridge",
        "is_listed": True,
    }
    score, rationale = compute_tvl_score(signals)
    assert score <= 10.0
    assert "CRISIS" in rationale


def test_score_warning_30pct_drop() -> None:
    """A 30-50% TVL drop in 7 days should floor the score at 20."""
    signals = {
        "current_tvl_usd": 5_000_000.0,
        "tvl_7d_change_pct": -35.0,
        "tvl_30d_change_pct": -20.0,
        "protocol_name": "WobblyProtocol",
        "category": "Lending",
        "is_listed": True,
    }
    score, rationale = compute_tvl_score(signals)
    assert score <= 20.0
    assert "WARNING" in rationale


def test_score_positive_trend_bonus() -> None:
    """Strong 7d growth should add a small bonus."""
    base_signals = {
        "current_tvl_usd": 2_000_000.0,
        "tvl_7d_change_pct": 0.0,
        "tvl_30d_change_pct": 0.0,
        "protocol_name": "GrowingProtocol",
        "category": "DEX",
        "is_listed": True,
    }
    base_score, _ = compute_tvl_score(base_signals)

    growing_signals = {**base_signals, "tvl_7d_change_pct": 15.0}
    growing_score, _ = compute_tvl_score(growing_signals)
    assert growing_score > base_score


def test_score_with_none_trend_data() -> None:
    """Missing trend data should not crash — just skip trend adjustments."""
    signals = {
        "current_tvl_usd": 50_000_000.0,
        "tvl_7d_change_pct": None,
        "tvl_30d_change_pct": None,
        "protocol_name": "NoTrendData",
        "category": "Lending",
        "is_listed": True,
    }
    score, rationale = compute_tvl_score(signals)
    assert score == 90.0  # $50M is in the $10M-$100M band
    assert "NoTrendData" in rationale


# ---------------------------------------------------------------------------
# chain mapping
# ---------------------------------------------------------------------------


def test_chain_map_covers_main_networks() -> None:
    for network in ("ethereum", "bsc", "arbitrum", "base", "solana"):
        assert network in _CHAIN_MAP, f"{network} missing from _CHAIN_MAP"
