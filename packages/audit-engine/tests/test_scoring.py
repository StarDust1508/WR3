from audit_engine.scoring import AXIS_WEIGHTS_TARGET, MVP_ACTIVE_WEIGHTS, compute_score
from audit_engine.types import Finding, Severity


def test_target_axis_weights_sum_to_one() -> None:
    """Documented design (TZ §8.1) — 5 axes, total weight 1.0."""
    assert abs(sum(AXIS_WEIGHTS_TARGET.values()) - 1.0) < 1e-9


def test_active_weights_sum_to_one() -> None:
    """Honest scoring policy: ACTIVE axes alone span the 0-100 scale.
    Inactive axes have weight=0 in the report so they don't pad."""
    assert abs(sum(MVP_ACTIVE_WEIGHTS.values()) - 1.0) < 1e-9


def test_clean_contract_scores_high() -> None:
    """Honest scoring: clean code = 100, not the previous padded ~85.
    The active Code Security axis dominates because it's the only one
    with weight > 0 until enrichment promotes others."""
    report = compute_score(address="0xabc", network="base", findings=[])
    assert report.score == 100.0
    assert report.tier == "blue"


def test_critical_finding_kills_score() -> None:
    findings = [
        Finding(
            id="t:1",
            title="Reentrancy",
            description="external call before state update",
            severity=Severity.CRITICAL,
            source_engine="test",
        )
    ]
    report = compute_score(address="0xabc", network="base", findings=findings)
    assert report.tier == "yellow" or report.tier == "red"


def test_dismissed_findings_excluded() -> None:
    findings = [
        Finding(
            id="t:1",
            title="Reentrancy",
            description="",
            severity=Severity.CRITICAL,
            source_engine="test",
            dismissed=True,
            dismissed_reason="protected by nonReentrant",
        )
    ]
    report = compute_score(address="0xabc", network="base", findings=findings)
    assert report.findings == []
