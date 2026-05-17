"""Etherscan contract-creation enrichment + On-chain Behavior axis.

We mock the Etherscan API with respx so tests run without network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from audit_engine.enrichment.etherscan_meta import (
    ContractCreation,
    compute_onchain_behavior_score,
    fetch_contract_creation,
)


_BASE = "https://api.etherscan.io/v2/api"


def _real_usdc_payload(years_ago: float = 7.0) -> dict:
    """Shape that matches Etherscan V2 — verified against the live
    response on USDC. `years_ago` lets us control the age for band tests."""
    ts = int((datetime.now(UTC) - timedelta(days=int(years_ago * 365))).timestamp())
    return {
        "status": "1",
        "message": "OK",
        "result": [
            {
                "contractAddress": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
                "contractCreator": "0x95ba4cf87d6723ad9c0db21737d862be80e93911",
                "txHash": "0xe7e0fe390354509cd08c9a0168536938600ddc552b3f7cb96030ebef62e75895",
                "blockNumber": "6082465",
                "timestamp": str(ts),
            }
        ],
    }


async def test_fetch_returns_none_without_api_key(monkeypatch) -> None:
    """Free-tier free: no key means we silently skip the enricher.
    Pipeline keeps running; the axis stays pending."""
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    result = await fetch_contract_creation(address="0xabc", network="ethereum")
    assert result is None


async def test_fetch_returns_none_for_unsupported_network(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    result = await fetch_contract_creation(
        address="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", network="solana"
    )
    assert result is None


async def test_fetch_returns_none_for_non_hex_address(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    result = await fetch_contract_creation(address="not-an-address", network="ethereum")
    assert result is None


async def test_fetch_parses_real_etherscan_response(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(200, json=_real_usdc_payload(years_ago=7.0))
        )
        c = await fetch_contract_creation(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", network="ethereum"
        )
    assert c is not None
    assert c.creator.startswith("0x95ba4cf")
    assert c.block_number == 6082465
    # 7 years ≈ 2555 days, within rounding tolerance for the test moment.
    assert 2540 <= c.age_days <= 2570


async def test_fetch_returns_none_on_etherscan_miss(monkeypatch) -> None:
    """Etherscan returns `status:0` for missing contracts."""
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json={"status": "0", "message": "No data", "result": ""}
            )
        )
        c = await fetch_contract_creation(address="0x" + "0" * 40, network="ethereum")
    assert c is None


async def test_fetch_returns_none_on_http_error(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(return_value=httpx.Response(500))
        c = await fetch_contract_creation(address="0xabc" + "0" * 37, network="ethereum")
    assert c is None


# --- score band tests ------------------------------------------------------


def _creation(age_days: int) -> ContractCreation:
    return ContractCreation(
        address="0xabc",
        network="ethereum",
        creator="0xcreator",
        tx_hash="0xtx",
        block_number=1,
        timestamp=datetime.now(UTC) - timedelta(days=age_days),
        age_days=age_days,
    )


def test_score_mature_contract() -> None:
    score, _ = compute_onchain_behavior_score(_creation(age_days=2000))
    assert score == 100.0


def test_score_established() -> None:
    score, rationale = compute_onchain_behavior_score(_creation(age_days=180))
    assert score == 80.0
    assert "180 дней" in rationale


def test_score_young() -> None:
    score, _ = compute_onchain_behavior_score(_creation(age_days=60))
    assert score == 60.0


def test_score_very_young() -> None:
    score, _ = compute_onchain_behavior_score(_creation(age_days=20))
    assert score == 35.0


def test_score_brand_new_max_risk() -> None:
    """Contracts <7 days old are the highest-risk band before fraud signal
    — many rugs deploy and pull within their first week."""
    score, rationale = compute_onchain_behavior_score(_creation(age_days=3))
    assert score == 15.0
    assert "наивысший риск" in rationale
    # Zero-day contract is the most extreme:
    score, _ = compute_onchain_behavior_score(_creation(age_days=0))
    assert score == 15.0


def test_band_boundaries_inclusive_on_lower_edge() -> None:
    """Lock the exact band edges so heuristic tuning is deliberate."""
    assert compute_onchain_behavior_score(_creation(366))[0] == 100.0
    assert compute_onchain_behavior_score(_creation(365))[0] == 80.0
    assert compute_onchain_behavior_score(_creation(91))[0] == 80.0
    assert compute_onchain_behavior_score(_creation(90))[0] == 60.0
    assert compute_onchain_behavior_score(_creation(31))[0] == 60.0
    assert compute_onchain_behavior_score(_creation(30))[0] == 35.0
    assert compute_onchain_behavior_score(_creation(8))[0] == 35.0
    assert compute_onchain_behavior_score(_creation(7))[0] == 15.0
