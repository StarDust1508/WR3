"""Team / KYC axis enrichment tests.

Mock MetaMask phishing list + Etherscan tx count via respx.
"""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from audit_engine.enrichment.team_kyc import (
    TeamKYCSignals,
    _PHISHING_LIST_URL,
    compute_team_kyc_score,
    fetch_team_kyc_signals,
)


_PHISHING_CONFIG = {
    "blacklist": [
        "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        "phishing-domain.com",
        "0xbadactor0000000000000000000000000000dead",
    ],
    "whitelist": [],
    "fuzzylist": [],
    "tolerance": 2,
}


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear the module-level phishing cache between tests."""
    import audit_engine.enrichment.team_kyc as mod

    mod._phishing_cache = None
    yield
    mod._phishing_cache = None


@respx.mock
async def test_deployer_on_phishing_list(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(200, json=_PHISHING_CONFIG))
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=Response(200, json={"result": "0x5"})
    )

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer="0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        source_verified=True,
    )
    assert signals is not None
    assert signals.deployer_on_phishing_list is True
    score, rationale = compute_team_kyc_score(signals)
    assert score == 0.0
    assert "фишинг" in rationale


@respx.mock
async def test_clean_deployer_high_tx_count(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(200, json=_PHISHING_CONFIG))
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=Response(200, json={"result": "0x1F4"})
    )

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer="0xgoodactor00000000000000000000000000000001",
        source_verified=True,
    )
    assert signals is not None
    assert signals.deployer_on_phishing_list is False
    assert signals.deployer_tx_count == 500
    score, rationale = compute_team_kyc_score(signals)
    assert score == 100.0


@respx.mock
async def test_burner_wallet_low_tx_count(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(200, json=_PHISHING_CONFIG))
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=Response(200, json={"result": "0x2"})
    )

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer="0xnewwallet000000000000000000000000000000001",
        source_verified=True,
    )
    assert signals is not None
    assert signals.deployer_tx_count == 2
    score, _ = compute_team_kyc_score(signals)
    assert score == 80.0


@respx.mock
async def test_unverified_source_penalty(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(200, json=_PHISHING_CONFIG))
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=Response(200, json={"result": "0x64"})
    )

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer="0xgoodactor00000000000000000000000000000001",
        source_verified=False,
    )
    assert signals is not None
    score, rationale = compute_team_kyc_score(signals)
    assert score == 75.0
    assert "не верифицирован" in rationale


async def test_solana_returns_none() -> None:
    result = await fetch_team_kyc_signals(
        address="SomeProgramAddress",
        network="solana",
        deployer=None,
        source_verified=True,
    )
    assert result is None


@respx.mock
async def test_no_deployer_info(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(200, json=_PHISHING_CONFIG))

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer=None,
        source_verified=True,
    )
    assert signals is not None
    assert signals.deployer_on_phishing_list is False
    score, rationale = compute_team_kyc_score(signals)
    assert score == 85.0
    assert "неизвестен" in rationale


@respx.mock
async def test_phishing_list_fetch_failure(monkeypatch) -> None:
    """If the phishing list fails, we don't crash — just skip that check."""
    monkeypatch.setenv("ETHERSCAN_API_KEY", "test-key")
    respx.get(_PHISHING_LIST_URL).mock(return_value=Response(500))
    respx.get("https://api.etherscan.io/v2/api").mock(
        return_value=Response(200, json={"result": "0x64"})
    )

    signals = await fetch_team_kyc_signals(
        address="0xcontract",
        network="ethereum",
        deployer="0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
        source_verified=True,
    )
    assert signals is not None
    assert signals.deployer_on_phishing_list is False


def test_score_bands_directly() -> None:
    """Direct unit test of compute_team_kyc_score boundary conditions."""
    # Perfect case
    s = TeamKYCSignals(
        deployer_on_phishing_list=False,
        deployer_address="0xabc",
        source_verified=True,
        deployer_tx_count=200,
    )
    score, _ = compute_team_kyc_score(s)
    assert score == 100.0

    # Low activity deployer
    s2 = TeamKYCSignals(
        deployer_on_phishing_list=False,
        deployer_address="0xabc",
        source_verified=True,
        deployer_tx_count=10,
    )
    score2, _ = compute_team_kyc_score(s2)
    assert score2 == 90.0

    # Worst non-phishing case: unverified + burner + no deployer
    s3 = TeamKYCSignals(
        deployer_on_phishing_list=False,
        deployer_address="0xabc",
        source_verified=False,
        deployer_tx_count=1,
    )
    score3, _ = compute_team_kyc_score(s3)
    assert score3 == 55.0
