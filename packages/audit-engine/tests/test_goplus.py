"""GoPlus Security integration — parser + scoring tests against recorded
USDC response. Doesn't hit the network in CI.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from audit_engine.enrichment.goplus import (
    _to_bool,
    _to_float,
    _to_int,
    compute_tokenomics_score,
    fetch_token_security,
    TokenSecurity,
)


def _real_usdc_payload() -> dict:
    """Trimmed but real shape from `https://api.gopluslabs.io/api/v1/
    token_security/1?contract_addresses=0xa0b8...eB48` (May 2026).
    Field values are the live ones — proxy=1, mint info, holders count etc.
    """
    return {
        "code": 1,
        "message": "OK",
        "result": {
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
                "token_name": "USD Coin",
                "token_symbol": "USDC",
                "is_proxy": "1",
                "is_honeypot": "0",
                "is_open_source": "1",
                "is_mintable": "1",
                "holder_count": "7015901",
                "total_supply": "54202067873.665451",
                "buy_tax": "0",
                "sell_tax": "0",
                "creator_address": "0x95ba4cf87d6723ad9c0db21737d862be80e93911",
                "creator_percent": "0.0001",
            }
        },
    }


def test_to_bool_handles_goplus_quirks() -> None:
    assert _to_bool("1") is True
    assert _to_bool("0") is False
    assert _to_bool(1) is True
    assert _to_bool(0) is False
    assert _to_bool(None) is None
    assert _to_bool("") is None
    # Unexpected strings → None, not crash
    assert _to_bool("maybe") is False  # only "1" is true


def test_to_float_lenient() -> None:
    assert _to_float("0.05") == 0.05
    assert _to_float(0.05) == 0.05
    assert _to_float(None) is None
    assert _to_float("") is None
    assert _to_float("not a number") is None


def test_to_int_via_float() -> None:
    assert _to_int("7015901") == 7015901
    assert _to_int("0") == 0
    assert _to_int(None) is None


async def test_fetch_token_security_parses_real_usdc_payload() -> None:
    with respx.mock(base_url="https://api.gopluslabs.io") as mock:
        mock.get("/api/v1/token_security/1").mock(
            return_value=httpx.Response(200, json=_real_usdc_payload())
        )
        ts = await fetch_token_security(
            address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            network="ethereum",
        )

    assert ts is not None
    assert ts.token_symbol == "USDC"
    assert ts.is_proxy is True
    assert ts.is_honeypot is False
    assert ts.is_open_source is True
    assert ts.holder_count == 7015901


async def test_fetch_returns_none_for_unsupported_network() -> None:
    # No HTTP call should be made for Solana — GoPlus has a separate endpoint
    # that we intentionally don't hit from this module.
    ts = await fetch_token_security(address="0xabc", network="solana")
    assert ts is None


async def test_fetch_returns_none_for_non_hex_address() -> None:
    ts = await fetch_token_security(
        address="JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        network="ethereum",
    )
    assert ts is None


async def test_fetch_returns_none_when_goplus_says_no_data() -> None:
    """GoPlus uses `code != 1` for "no data for this address"."""
    with respx.mock(base_url="https://api.gopluslabs.io") as mock:
        mock.get("/api/v1/token_security/1").mock(
            return_value=httpx.Response(
                200, json={"code": 4010, "message": "No data", "result": {}}
            )
        )
        ts = await fetch_token_security(address="0x000", network="ethereum")
    assert ts is None


async def test_fetch_handles_http_error() -> None:
    with respx.mock(base_url="https://api.gopluslabs.io") as mock:
        mock.get("/api/v1/token_security/1").mock(
            return_value=httpx.Response(500, json={})
        )
        ts = await fetch_token_security(
            address="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            network="ethereum",
        )
    assert ts is None


def _ts(**overrides) -> TokenSecurity:
    """Helper: clean baseline TokenSecurity with no red flags."""
    base = dict(
        address="0xabc",
        network="ethereum",
        token_name="Clean",
        token_symbol="CLN",
        is_open_source=True,
        is_proxy=False,
        is_mintable=False,
        can_take_back_ownership=False,
        owner_change_balance=False,
        hidden_owner=False,
        selfdestruct=False,
        external_call=False,
        is_honeypot=False,
        honeypot_with_same_creator=False,
        buy_tax=0.0,
        sell_tax=0.0,
        transfer_tax=0.0,
        cannot_buy=False,
        cannot_sell_all=False,
        slippage_modifiable=False,
        holder_count=1000,
        total_supply=1_000_000.0,
        creator_address="0xdead",
        creator_percent=0.01,
        raw={},
    )
    base.update(overrides)
    return TokenSecurity(**base)


def test_score_clean_token_is_100() -> None:
    score, rationale = compute_tokenomics_score(_ts())
    assert score == 100.0
    assert "no centralization red flags" in rationale


def test_score_honeypot_is_zero() -> None:
    """Honeypot is terminal — no other factors should rescue the score."""
    score, rationale = compute_tokenomics_score(_ts(is_honeypot=True))
    assert score == 0.0
    assert "honeypot" in rationale.lower()


def test_score_cannot_sell_all_is_zero() -> None:
    """Likely-scam signal even without explicit honeypot flag."""
    score, rationale = compute_tokenomics_score(_ts(cannot_sell_all=True))
    assert score == 0.0
    assert "cannot sell" in rationale.lower()


def test_score_proxy_deducts_10() -> None:
    score, _ = compute_tokenomics_score(_ts(is_proxy=True))
    assert score == 90.0


def test_score_hidden_owner_deducts_30() -> None:
    score, rationale = compute_tokenomics_score(_ts(hidden_owner=True))
    assert score == 70.0
    assert "hidden owner" in rationale


def test_score_stacks_deductions() -> None:
    """Multiple red flags compound — not capped at 100."""
    score, rationale = compute_tokenomics_score(
        _ts(
            is_proxy=True,          # -10
            is_mintable=True,       # -15
            owner_change_balance=True,  # -20
            buy_tax=0.20,           # -10
            sell_tax=0.15,          # -10
        )
    )
    # 100 - 10 - 15 - 20 - 10 - 10 = 35
    assert score == 35.0
    assert "mintable" in rationale
    assert "buy tax 20%" in rationale


def test_score_creator_concentration() -> None:
    """Creator holding >30% of supply is a centralization flag."""
    score, rationale = compute_tokenomics_score(_ts(creator_percent=0.5))
    assert score == 90.0
    assert "50%" in rationale


def test_score_floors_at_zero() -> None:
    """Stacked deductions cannot push the score negative."""
    score, _ = compute_tokenomics_score(
        _ts(
            hidden_owner=True,
            can_take_back_ownership=True,
            owner_change_balance=True,
            is_mintable=True,
            is_proxy=True,
            selfdestruct=True,
            is_open_source=False,
            buy_tax=0.5,
            sell_tax=0.5,
            creator_percent=0.5,
        )
    )
    assert score == 0.0
