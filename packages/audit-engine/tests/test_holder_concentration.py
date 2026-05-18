"""Token holder concentration enrichment — Etherscan V2 tokenholderlist.

We mock the Etherscan API with respx so tests run without network.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from audit_engine.enrichment.holder_concentration import (
    _parse_share,
    compute_concentration_score,
    fetch_holder_signals,
)


_BASE = "https://api.etherscan.io/v2/api"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _holder_row(addr: str, share: str) -> dict:
    """Build one Etherscan tokenholderlist result row."""
    return {
        "TokenHolderAddress": addr,
        "TokenHolderQuantity": "1000000",
        "Share": share,
    }


def _success_payload(holders: list[dict]) -> dict:
    return {
        "status": "1",
        "message": "OK",
        "result": holders,
    }


def _well_distributed_holders() -> list[dict]:
    """10 holders totalling ~25 % — well distributed."""
    return [
        _holder_row(f"0x{'a' * 39}{i}", f"{2.5}%")
        for i in range(10)
    ]


def _concentrated_holders() -> list[dict]:
    """Top holder 55 %, rest small — critical."""
    rows = [_holder_row("0x" + "b" * 40, "55.0000%")]
    for i in range(9):
        rows.append(_holder_row(f"0x{'c' * 39}{i}", "2.0%"))
    return rows


def _high_concentration_holders() -> list[dict]:
    """Top-10 total ~60 % — high concentration."""
    return [
        _holder_row(f"0x{'d' * 39}{i}", "6.0%")
        for i in range(10)
    ]


def _moderate_concentration_holders() -> list[dict]:
    """Top-10 total ~40 % — moderate."""
    return [
        _holder_row(f"0x{'e' * 39}{i}", "4.0%")
        for i in range(10)
    ]


# ---------------------------------------------------------------------------
# _parse_share unit tests
# ---------------------------------------------------------------------------


class TestParseShare:
    def test_normal(self) -> None:
        assert _parse_share("12.3456%") == pytest.approx(12.3456)

    def test_no_percent_sign(self) -> None:
        assert _parse_share("5.5") == pytest.approx(5.5)

    def test_with_spaces(self) -> None:
        assert _parse_share("  7.0%  ") == pytest.approx(7.0)

    def test_none(self) -> None:
        assert _parse_share(None) == 0.0

    def test_empty(self) -> None:
        assert _parse_share("") == 0.0

    def test_garbage(self) -> None:
        assert _parse_share("not-a-number") == 0.0


# ---------------------------------------------------------------------------
# fetch_holder_signals tests
# ---------------------------------------------------------------------------


async def test_returns_none_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    result = await fetch_holder_signals("0xabc", "ethereum")
    assert result is None


async def test_returns_none_for_solana(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    result = await fetch_holder_signals(
        "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4", "solana"
    )
    assert result is None


async def test_returns_none_for_non_hex_address(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    result = await fetch_holder_signals("not-an-address", "ethereum")
    assert result is None


async def test_well_distributed_token(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json=_success_payload(_well_distributed_holders())
            )
        )
        signals = await fetch_holder_signals("0x" + "a" * 40, "ethereum")

    assert signals is not None
    assert signals["top10_pct"] == pytest.approx(25.0, abs=0.1)
    assert signals["top1_pct"] == pytest.approx(2.5, abs=0.1)
    assert signals["concentration_risk"] == "low"
    assert signals["deployer_is_top_holder"] is False


async def test_critical_concentration(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json=_success_payload(_concentrated_holders())
            )
        )
        signals = await fetch_holder_signals("0x" + "b" * 40, "ethereum")

    assert signals is not None
    assert signals["top1_pct"] == pytest.approx(55.0, abs=0.1)
    assert signals["concentration_risk"] == "critical"


async def test_high_concentration(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json=_success_payload(_high_concentration_holders())
            )
        )
        signals = await fetch_holder_signals("0x" + "d" * 40, "ethereum")

    assert signals is not None
    assert signals["top10_pct"] == pytest.approx(60.0, abs=0.1)
    assert signals["concentration_risk"] == "high"


async def test_moderate_concentration(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json=_success_payload(_moderate_concentration_holders())
            )
        )
        signals = await fetch_holder_signals("0x" + "e" * 40, "ethereum")

    assert signals is not None
    assert signals["top10_pct"] == pytest.approx(40.0, abs=0.1)
    assert signals["concentration_risk"] == "medium"


async def test_deployer_detected_in_top_holders(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    deployer = "0x" + "b" * 40
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json=_success_payload(_concentrated_holders())
            )
        )
        signals = await fetch_holder_signals(
            "0x" + "f" * 40, "ethereum", deployer_address=deployer
        )

    assert signals is not None
    assert signals["deployer_is_top_holder"] is True


async def test_returns_none_on_etherscan_miss(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(
            return_value=httpx.Response(
                200, json={"status": "0", "message": "No data", "result": ""}
            )
        )
        result = await fetch_holder_signals("0x" + "0" * 40, "ethereum")
    assert result is None


async def test_returns_none_on_http_error(monkeypatch) -> None:
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    with respx.mock(base_url="https://api.etherscan.io") as mock:
        mock.get("/v2/api").mock(return_value=httpx.Response(500))
        result = await fetch_holder_signals("0x" + "a" * 40, "ethereum")
    assert result is None


async def test_chain_id_mapping(monkeypatch) -> None:
    """All supported chains produce a valid request (not None early-return)."""
    monkeypatch.setenv("ETHERSCAN_API_KEY", "k")
    for network in ("ethereum", "bsc", "polygon", "base", "arbitrum"):
        with respx.mock(base_url="https://api.etherscan.io") as mock:
            mock.get("/v2/api").mock(
                return_value=httpx.Response(
                    200, json=_success_payload(_well_distributed_holders())
                )
            )
            signals = await fetch_holder_signals("0x" + "a" * 40, network)
        assert signals is not None, f"Expected signals for {network}"


# ---------------------------------------------------------------------------
# compute_concentration_score tests
# ---------------------------------------------------------------------------


class TestConcentrationScore:
    def test_none_signals_returns_neutral(self) -> None:
        score, rationale = compute_concentration_score(None)
        assert score == 50.0
        assert "unavailable" in rationale

    def test_well_distributed(self) -> None:
        signals = {
            "top10_pct": 25.0,
            "top1_pct": 3.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "low",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 90.0
        assert "well distributed" in rationale

    def test_moderate_concentration(self) -> None:
        signals = {
            "top10_pct": 40.0,
            "top1_pct": 8.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "medium",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 70.0
        assert "moderate" in rationale

    def test_high_concentration(self) -> None:
        signals = {
            "top10_pct": 60.0,
            "top1_pct": 15.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "high",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 45.0
        assert "high concentration" in rationale

    def test_critical_concentration(self) -> None:
        signals = {
            "top10_pct": 80.0,
            "top1_pct": 25.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "critical",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 20.0
        assert "critical" in rationale

    def test_top1_over_50_floors_to_15(self) -> None:
        signals = {
            "top10_pct": 60.0,
            "top1_pct": 55.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "critical",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 15.0
        assert "top holder alone" in rationale

    def test_deployer_penalty(self) -> None:
        signals = {
            "top10_pct": 25.0,
            "top1_pct": 5.0,
            "deployer_is_top_holder": True,
            "concentration_risk": "low",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 75.0  # 90 - 15
        assert "deployer" in rationale

    def test_deployer_penalty_plus_top1_override(self) -> None:
        """Top1 override + deployer penalty stack: min(45, 15) - 15 = 0."""
        signals = {
            "top10_pct": 60.0,
            "top1_pct": 55.0,
            "deployer_is_top_holder": True,
            "concentration_risk": "critical",
        }
        score, rationale = compute_concentration_score(signals)
        assert score == 0.0

    def test_score_never_exceeds_bounds(self) -> None:
        """Edge case: score stays in [0, 100] regardless of inputs."""
        signals = {
            "top10_pct": 5.0,
            "top1_pct": 1.0,
            "deployer_is_top_holder": False,
            "concentration_risk": "low",
        }
        score, _ = compute_concentration_score(signals)
        assert 0.0 <= score <= 100.0

    def test_band_boundary_30(self) -> None:
        """top10=30 is moderate, top10=29.9 is well distributed."""
        low = {"top10_pct": 29.9, "top1_pct": 5.0, "deployer_is_top_holder": False, "concentration_risk": "low"}
        mid = {"top10_pct": 30.0, "top1_pct": 5.0, "deployer_is_top_holder": False, "concentration_risk": "medium"}
        assert compute_concentration_score(low)[0] == 90.0
        assert compute_concentration_score(mid)[0] == 70.0

    def test_band_boundary_50(self) -> None:
        """top10=50 is moderate, top10=50.1 is high."""
        mid = {"top10_pct": 50.0, "top1_pct": 10.0, "deployer_is_top_holder": False, "concentration_risk": "medium"}
        high = {"top10_pct": 50.1, "top1_pct": 10.0, "deployer_is_top_holder": False, "concentration_risk": "high"}
        assert compute_concentration_score(mid)[0] == 70.0
        assert compute_concentration_score(high)[0] == 45.0

    def test_band_boundary_70(self) -> None:
        """top10=70 is high, top10=70.1 is critical."""
        high = {"top10_pct": 70.0, "top1_pct": 15.0, "deployer_is_top_holder": False, "concentration_risk": "high"}
        crit = {"top10_pct": 70.1, "top1_pct": 15.0, "deployer_is_top_holder": False, "concentration_risk": "critical"}
        assert compute_concentration_score(high)[0] == 45.0
        assert compute_concentration_score(crit)[0] == 20.0
