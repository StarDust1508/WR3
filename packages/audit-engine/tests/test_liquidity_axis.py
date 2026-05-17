"""Liquidity Risk axis — built on the GoPlus holder data we already fetch.

Tests pin the heuristics so accidental refactors don't silently shift
the score band for known reference points (USDC ≈ 100, ape token ≈ 40).
"""

from __future__ import annotations

from audit_engine.enrichment.goplus import (
    TokenSecurity,
    compute_liquidity_score,
)


def _ts(**overrides) -> TokenSecurity:
    """Baseline: clean token, fully distributed, no taxes."""
    base = dict(
        address="0xabc",
        network="ethereum",
        token_name="Test",
        token_symbol="TST",
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
        holder_count=100_000,
        total_supply=1_000_000.0,
        creator_address="0xdead",
        creator_percent=0.005,
        raw={},
    )
    base.update(overrides)
    return TokenSecurity(**base)


def test_no_holder_count_returns_none() -> None:
    """Some GoPlus responses lack holder_count for non-token contracts —
    in that case the axis stays pending honestly rather than guess."""
    assert compute_liquidity_score(_ts(holder_count=None)) is None


def test_widely_distributed_token_scores_near_perfect() -> None:
    """USDC-tier distribution (100k+ holders, <1% creator) — no deductions."""
    result = compute_liquidity_score(_ts())
    assert result is not None
    score, rationale = result
    assert score == 100.0
    assert "distributed holder base" in rationale


def test_honeypot_is_terminal() -> None:
    """Honeypot or cannot-sell-all → 0, regardless of holders."""
    score, rationale = compute_liquidity_score(_ts(is_honeypot=True))
    assert score == 0.0
    assert "honeypot" in rationale
    score, rationale = compute_liquidity_score(_ts(cannot_sell_all=True))
    assert score == 0.0


def test_few_holders_heavy_penalty() -> None:
    """An ape token with <50 holders is barely tradeable — exit-liquidity
    trap. Calibrated to keep score in the 'red' band before other axes
    save the contract."""
    score, rationale = compute_liquidity_score(_ts(holder_count=30))
    assert score == 60.0  # 100 - 40
    assert "30 holders" in rationale


def test_holder_count_bands() -> None:
    """Pin the band thresholds so heuristic changes are deliberate."""
    assert compute_liquidity_score(_ts(holder_count=49))[0] == 60.0   # -40
    assert compute_liquidity_score(_ts(holder_count=150))[0] == 75.0  # -25
    assert compute_liquidity_score(_ts(holder_count=500))[0] == 85.0  # -15
    assert compute_liquidity_score(_ts(holder_count=5_000))[0] == 95.0  # -5
    assert compute_liquidity_score(_ts(holder_count=20_000))[0] == 100.0  # -0


def test_creator_concentration_deducts() -> None:
    """Top-creator holding >30% is a centralization-of-supply flag."""
    s, r = compute_liquidity_score(_ts(creator_percent=0.35))
    assert s == 80.0  # 100 - 20
    assert "35% of supply" in r
    s, r = compute_liquidity_score(_ts(creator_percent=0.55))
    assert s == 65.0  # 100 - 35
    assert "55% of supply" in r


def test_sell_tax_restricts_exits() -> None:
    """High sell tax effectively reduces liquidity — even if holders are
    diverse, they can't get out without paying."""
    s, r = compute_liquidity_score(_ts(sell_tax=0.20))
    assert s == 85.0  # 100 - 15
    assert "sell tax 20% restricts exits" in r
    # Mid-band tax — small deduction
    s, _ = compute_liquidity_score(_ts(sell_tax=0.08))
    assert s == 95.0


def test_combined_deductions_compound() -> None:
    """Multiple red flags stack, floor at 0."""
    s, _ = compute_liquidity_score(
        _ts(
            holder_count=30,           # -40
            creator_percent=0.50,      # -35
            sell_tax=0.20,             # -15
        )
    )
    assert s == 10.0  # 100 - 40 - 35 - 15
