"""DexScreener liquidity enrichment — fetch + scoring tests against
recorded pair data. Doesn't hit the network in CI.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from audit_engine.enrichment.dexscreener import (
    compute_liquidity_score,
    fetch_liquidity_signals,
)


def _single_pair_payload() -> list[dict]:
    """Minimal but realistic DexScreener pair shape (one WETH/TOKEN pair)."""
    return [
        {
            "chainId": "ethereum",
            "dexId": "uniswap",
            "pairAddress": "0xpair1",
            "baseToken": {"symbol": "TOKEN", "address": "0xtoken"},
            "quoteToken": {"symbol": "WETH", "address": "0xweth"},
            "priceUsd": "1.25",
            "liquidity": {"usd": 250_000},
            "volume": {"h24": 1_200_000},
            "priceChange": {"h24": -2.5},
            "fdv": 50_000_000,
        }
    ]


def _multi_pair_payload() -> list[dict]:
    """Two pairs — the scoring should sum liquidity across both."""
    return [
        {
            "chainId": "ethereum",
            "dexId": "uniswap",
            "pairAddress": "0xpair1",
            "baseToken": {"symbol": "TOKEN", "address": "0xtoken"},
            "quoteToken": {"symbol": "WETH", "address": "0xweth"},
            "priceUsd": "1.25",
            "liquidity": {"usd": 800_000},
            "volume": {"h24": 500_000},
            "priceChange": {"h24": 5.0},
            "fdv": 50_000_000,
        },
        {
            "chainId": "ethereum",
            "dexId": "sushiswap",
            "pairAddress": "0xpair2",
            "baseToken": {"symbol": "TOKEN", "address": "0xtoken"},
            "quoteToken": {"symbol": "USDC", "address": "0xusdc"},
            "priceUsd": "1.24",
            "liquidity": {"usd": 300_000},
            "volume": {"h24": 100_000},
            "priceChange": {"h24": 4.8},
            "fdv": 50_000_000,
        },
    ]


# ---------------------------------------------------------------------------
# fetch_liquidity_signals
# ---------------------------------------------------------------------------


async def test_fetch_parses_single_pair() -> None:
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/ethereum/0xtoken").mock(
            return_value=httpx.Response(200, json=_single_pair_payload())
        )
        result = await fetch_liquidity_signals("0xtoken", "ethereum")

    assert result is not None
    assert result["pair_count"] == 1
    assert result["total_liquidity_usd"] == 250_000
    assert result["top_pair_name"] == "TOKEN / WETH"
    assert result["top_pair_dex"] == "uniswap"
    assert result["price_usd"] == 1.25
    assert result["volume_24h_usd"] == 1_200_000
    assert result["price_change_24h_pct"] == -2.5
    assert result["fdv_usd"] == 50_000_000


async def test_fetch_sums_liquidity_across_pairs() -> None:
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/ethereum/0xtoken").mock(
            return_value=httpx.Response(200, json=_multi_pair_payload())
        )
        result = await fetch_liquidity_signals("0xtoken", "ethereum")

    assert result is not None
    assert result["pair_count"] == 2
    assert result["total_liquidity_usd"] == 1_100_000  # 800k + 300k
    assert result["volume_24h_usd"] == 600_000  # 500k + 100k
    # Top pair is the one with highest liquidity (uniswap, 800k).
    assert result["top_pair_dex"] == "uniswap"


async def test_fetch_returns_none_for_unsupported_network() -> None:
    result = await fetch_liquidity_signals("0xabc", "polygon")
    assert result is None


async def test_fetch_returns_none_for_empty_pairs() -> None:
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/ethereum/0xtoken").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await fetch_liquidity_signals("0xtoken", "ethereum")
    assert result is None


async def test_fetch_returns_none_on_http_error() -> None:
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/ethereum/0xtoken").mock(
            return_value=httpx.Response(500, json={})
        )
        result = await fetch_liquidity_signals("0xtoken", "ethereum")
    assert result is None


async def test_fetch_returns_none_on_non_list_response() -> None:
    """DexScreener might return an error object instead of an array."""
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/ethereum/0xtoken").mock(
            return_value=httpx.Response(200, json={"error": "not found"})
        )
        result = await fetch_liquidity_signals("0xtoken", "ethereum")
    assert result is None


async def test_fetch_works_for_solana() -> None:
    payload = [
        {
            "chainId": "solana",
            "dexId": "raydium",
            "pairAddress": "SolPair1",
            "baseToken": {"symbol": "JUP", "address": "JUPaddr"},
            "quoteToken": {"symbol": "SOL", "address": "SOLaddr"},
            "priceUsd": "0.85",
            "liquidity": {"usd": 5_000_000},
            "volume": {"h24": 20_000_000},
            "priceChange": {"h24": 12.3},
            "fdv": 1_000_000_000,
        }
    ]
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/solana/JUPaddr").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await fetch_liquidity_signals("JUPaddr", "solana")

    assert result is not None
    assert result["top_pair_dex"] == "raydium"
    assert result["total_liquidity_usd"] == 5_000_000


async def test_fetch_bsc_chain_slug() -> None:
    """Ensure BSC maps to the correct DexScreener slug."""
    with respx.mock(base_url="https://api.dexscreener.com") as mock:
        mock.get("/tokens/v1/bsc/0xcake").mock(
            return_value=httpx.Response(200, json=[])
        )
        result = await fetch_liquidity_signals("0xcake", "bsc")
    assert result is None  # empty pairs, but the URL was correct


# ---------------------------------------------------------------------------
# compute_liquidity_score
# ---------------------------------------------------------------------------


async def test_score_none_signals() -> None:
    score, rationale = await compute_liquidity_score(None)
    assert score == 20.0
    assert "no DEX pairs found" in rationale


async def test_score_high_liquidity() -> None:
    signals = {
        "total_liquidity_usd": 2_000_000,
        "pair_count": 3,
        "volume_24h_usd": 500_000,
        "price_change_24h_pct": 1.5,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 85.0
    assert "$2,000,000" in rationale


async def test_score_very_deep_liquidity_bonus() -> None:
    """Liquidity >$10M gets +5 bonus on top of base 85."""
    signals = {
        "total_liquidity_usd": 15_000_000,
        "pair_count": 5,
        "volume_24h_usd": 1_000_000,
        "price_change_24h_pct": 0.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 90.0
    assert "deep liquidity" in rationale


async def test_score_medium_liquidity() -> None:
    signals = {
        "total_liquidity_usd": 150_000,
        "pair_count": 1,
        "volume_24h_usd": 50_000,
        "price_change_24h_pct": -3.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 65.0


async def test_score_low_liquidity() -> None:
    signals = {
        "total_liquidity_usd": 30_000,
        "pair_count": 1,
        "volume_24h_usd": 5_000,
        "price_change_24h_pct": 0.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 45.0


async def test_score_very_low_liquidity() -> None:
    signals = {
        "total_liquidity_usd": 5_000,
        "pair_count": 1,
        "volume_24h_usd": 200,
        "price_change_24h_pct": 0.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 25.0


async def test_score_volume_liquidity_bonus() -> None:
    """V/L ratio > 5 grants +10 bonus."""
    signals = {
        "total_liquidity_usd": 200_000,
        "pair_count": 2,
        "volume_24h_usd": 1_500_000,  # V/L = 7.5
        "price_change_24h_pct": 0.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 75.0  # 65 base + 10 bonus
    assert "active trading" in rationale


async def test_score_price_crash_caps_at_30() -> None:
    """24h price drop > 50% caps score at 30 regardless of liquidity."""
    signals = {
        "total_liquidity_usd": 5_000_000,
        "pair_count": 4,
        "volume_24h_usd": 2_000_000,
        "price_change_24h_pct": -65.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 30.0
    assert "crashed" in rationale


async def test_score_capped_at_100() -> None:
    """Even with all bonuses, score cannot exceed 100."""
    signals = {
        "total_liquidity_usd": 50_000_000,
        "pair_count": 10,
        "volume_24h_usd": 500_000_000,  # V/L = 10 → +10 bonus
        "price_change_24h_pct": 20.0,
    }
    score, rationale = await compute_liquidity_score(signals)
    assert score == 100.0
