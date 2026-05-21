"""Scoring policy regression: pending axes don't pad the final score.

Background: previously all 5 axes had hardcoded score=80 for the four
unevaluated ones. That meant every scan got `80 * 0.65 = 52` of free score
no matter how bad the code was — a critical-only contract still showed
~62/100 because four axes were padding it. This locks in the honest
policy that only active axes (weight > 0 and score != None) contribute.
"""

from __future__ import annotations

from audit_engine.scoring import (
    AXIS_WEIGHTS_TARGET,
    MVP_ACTIVE_WEIGHTS,
    compute_score,
)
from audit_engine.types import Finding, Severity


def _f(severity: Severity, source_engine: str = "baseline") -> Finding:
    return Finding(
        id=f"x-{severity.value}",
        title=f"some {severity.value}",
        description="",
        severity=severity,
        source_engine=source_engine,
    )


def test_clean_contract_scores_100() -> None:
    report = compute_score(address="0xabc", network="ethereum", findings=[])
    assert report.score == 100.0
    assert report.tier == "blue"


def test_critical_caps_at_red_with_penalty() -> None:
    """A single CRITICAL must produce score <= 39.9 and tier=red, even though
    in the old broken scoring four other axes would've padded the result."""
    report = compute_score(
        address="0xabc",
        network="ethereum",
        findings=[_f(Severity.CRITICAL)],
    )
    assert report.score <= 39.9
    assert report.tier == "red"


def test_only_code_security_axis_is_active() -> None:
    """The other four axes exist in the report (for transparency) but have
    weight=0 so they don't move the number — and score=None so the renderer
    knows to show 'pending' instead of a misleading numeric value."""
    report = compute_score(address="0xabc", network="ethereum", findings=[])
    active = [a for a in report.axes if a.weight > 0]
    assert len(active) == 1
    assert active[0].name == "Code Security"
    assert sum(a.weight for a in active) == 1.0

    inactive = [a for a in report.axes if a.weight == 0]
    assert len(inactive) == 4
    for a in inactive:
        assert a.score is None
        assert "pending" in a.rationale.lower()


def test_pending_axes_announce_planned_weight() -> None:
    """The rationale tells users what weight the axis WILL have once active
    — so the methodology stays transparent."""
    report = compute_score(address="0xabc", network="ethereum", findings=[])
    for axis in report.axes:
        if axis.weight == 0:
            expected = int(AXIS_WEIGHTS_TARGET[axis.name] * 100)
            assert f"{expected}%" in axis.rationale


def test_active_weights_must_sum_to_one() -> None:
    """Invariant: the weights of active axes sum to 1.0 so weighted score
    is on a clean 0-100 scale. Add a guard so future axes can't drift."""
    assert sum(MVP_ACTIVE_WEIGHTS.values()) == 1.0


def test_medium_findings_only_score_is_not_padded() -> None:
    """5 DISTINCT medium findings → 5 unique issues × 7 = 35 penalty → score 65.
    Duplicate findings (same title+severity) are grouped and penalized once."""
    findings = [
        Finding(
            id=f"x-med-{i}",
            title=f"medium issue {i}",
            description="",
            severity=Severity.MEDIUM,
            source_engine="baseline",
        )
        for i in range(5)
    ]
    report = compute_score(address="0xabc", network="ethereum", findings=findings)
    # 100 - 5*7 = 65
    assert report.score == 65.0
    assert report.tier == "yellow"


def test_duplicate_findings_penalized_once() -> None:
    """10 findings with the same title+severity = 1 unique issue, single penalty."""
    findings = [
        Finding(
            id=f"dup-{i}",
            title="Zero-address check missing",
            description="",
            severity=Severity.LOW,
            source_engine="baseline",
        )
        for i in range(10)
    ]
    report = compute_score(address="0xabc", network="ethereum", findings=findings)
    # 1 unique LOW issue → penalty=2 → score=98
    assert report.score == 98.0
    assert report.tier == "blue"
