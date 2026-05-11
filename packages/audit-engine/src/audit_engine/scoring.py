"""Scoring system: 5 axes, transparent weights, 0-100 with traffic light.

Per TZ.md section 8: weights are published in README and UI methodology page.
"""

from __future__ import annotations

from typing import Literal

from audit_engine.types import AuditReport, Finding, Network, ScoreAxis, Severity

# Weights published — total = 1.0
AXIS_WEIGHTS = {
    "Code Security": 0.35,
    "Tokenomics / Centralization": 0.20,
    "Liquidity Risk": 0.15,
    "Team / KYC": 0.15,
    "On-chain Behavior": 0.15,
}

# Penalty per finding severity, applied to base 100
SEVERITY_PENALTY = {
    Severity.CRITICAL: 40,
    Severity.HIGH: 20,
    Severity.MEDIUM: 7,
    Severity.LOW: 2,
    Severity.INFO: 0,
}


def compute_score(*, address: str, network: Network, findings: list[Finding]) -> AuditReport:
    """Compute weighted score across 5 axes.

    MVP heuristics:
      - Code Security axis uses findings only.
      - Other axes start at 80 (neutral) — to be populated by signals in later stages.
    """
    active = [f for f in findings if not f.dismissed]
    penalty = sum(SEVERITY_PENALTY.get(f.severity, 0) for f in active)
    code_security_score = max(0.0, min(100.0, 100.0 - penalty))

    axes = [
        ScoreAxis(
            name="Code Security",
            weight=AXIS_WEIGHTS["Code Security"],
            score=code_security_score,
            rationale=_describe_code_findings(active),
        ),
        ScoreAxis(
            name="Tokenomics / Centralization",
            weight=AXIS_WEIGHTS["Tokenomics / Centralization"],
            score=80.0,
            rationale="Not yet evaluated — signals collection pending (W7+).",
        ),
        ScoreAxis(
            name="Liquidity Risk",
            weight=AXIS_WEIGHTS["Liquidity Risk"],
            score=80.0,
            rationale="Not yet evaluated — signals collection pending (W7+).",
        ),
        ScoreAxis(
            name="Team / KYC",
            weight=AXIS_WEIGHTS["Team / KYC"],
            score=80.0,
            rationale="Not yet evaluated — signals collection pending (W7+).",
        ),
        ScoreAxis(
            name="On-chain Behavior",
            weight=AXIS_WEIGHTS["On-chain Behavior"],
            score=80.0,
            rationale="Not yet evaluated — signals collection pending (W12+).",
        ),
    ]

    weighted = sum(a.score * a.weight for a in axes)
    score = round(weighted, 1)

    # Severity overrides: a single CRITICAL finding always means red, regardless
    # of how the weighted average comes out. HIGH caps tier at yellow at best.
    # This matches industry norm — a critical bug is automatically a red flag,
    # not something that can be "averaged out" by good tokenomics or KYC.
    has_critical = any(f.severity == Severity.CRITICAL for f in active)
    has_high = any(f.severity == Severity.HIGH for f in active)

    if has_critical:
        tier: Literal["red", "yellow", "green", "blue"] = "red"
        score = min(score, 39.9)
    elif has_high:
        tier = _tier(min(score, 69.9))
        score = min(score, 69.9)
    else:
        tier = _tier(score)

    return AuditReport(
        address=address,
        network=network,
        score=score,
        tier=tier,
        axes=axes,
        findings=active,
    )


def _tier(score: float) -> Literal["red", "yellow", "green", "blue"]:
    if score < 40:
        return "red"
    if score < 70:
        return "yellow"
    if score < 90:
        return "green"
    return "blue"


def _describe_code_findings(findings: list[Finding]) -> str:
    by_sev: dict[Severity, int] = {}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    if not by_sev:
        return "No findings from static analysis."
    parts = [
        f"{n}x {sev.value}"
        for sev, n in sorted(by_sev.items(), key=lambda kv: -SEVERITY_PENALTY.get(kv[0], 0))
    ]
    return "Findings: " + ", ".join(parts)
