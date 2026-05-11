from audit_engine.scoring import AXIS_WEIGHTS, compute_score
from audit_engine.types import Finding, Severity


def test_score_weights_sum_to_one() -> None:
    assert abs(sum(AXIS_WEIGHTS.values()) - 1.0) < 1e-9


def test_clean_contract_scores_high() -> None:
    report = compute_score(address="0xabc", network="base", findings=[])
    assert report.score >= 80
    assert report.tier in ("green", "blue")


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
