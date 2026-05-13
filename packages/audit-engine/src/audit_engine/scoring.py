"""Scoring system — transparent weights, 0-100 + traffic light.

Per TZ.md §8.1 the long-term design has 5 axes:
    Code Security (35%) · Tokenomics (20%) · Liquidity (15%) ·
    Team/KYC (15%) · On-chain Behavior (15%).

MVP reality: only Code Security has a real signal pipeline.
The other four require external data sources (GoPlus / DefiLlama TVL /
MetaMask anti-phishing / Etherscan deployer history) — partly wired in
follow-up iterations. Until they produce real numbers, weighting them at
"neutral 80" silently inflates the final score by ~52 points (every scan
gets `80 * 0.65 = 52` of free score regardless of findings) — which is
misleading and lies to the user.

Decision (honest scoring policy):
    During MVP, ONLY Code Security counts toward the final score. The
    other four axes are still emitted in the report — labelled as
    "pending evaluation" with a `null` score — so the methodology page
    and the rendered axes table are consistent, but they don't pad the
    number.

When a new axis is wired with a real signal (e.g. Tokenomics from
GoPlus), set its `weight` to its TZ value and remove the
`pending_evaluation` flag — the renderer treats those uniformly.
"""

from __future__ import annotations

from typing import Literal

from audit_engine.types import AuditReport, Finding, Network, ScoreAxis, Severity

# Published weights from TZ §8.1 — kept here as documentation even though
# only Code Security is active. Switching an axis on = move its weight
# from MVP_INACTIVE_WEIGHT into MVP_ACTIVE_WEIGHTS.
AXIS_WEIGHTS_TARGET = {
    "Code Security": 0.35,
    "Tokenomics / Centralization": 0.20,
    "Liquidity Risk": 0.15,
    "Team / KYC": 0.15,
    "On-chain Behavior": 0.15,
}

# Active in current MVP — sum must equal 1.0 so the weighted sum spans 0-100.
MVP_ACTIVE_WEIGHTS = {
    "Code Security": 1.0,
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
    """Compute weighted score across the active axes."""
    active = [f for f in findings if not f.dismissed]
    penalty = sum(SEVERITY_PENALTY.get(f.severity, 0) for f in active)
    code_security_score = max(0.0, min(100.0, 100.0 - penalty))

    axes: list[ScoreAxis] = [
        ScoreAxis(
            name="Code Security",
            weight=MVP_ACTIVE_WEIGHTS["Code Security"],
            score=code_security_score,
            rationale=_describe_code_findings(active),
        ),
        # Inactive axes: weight=0 so they don't move the score, but we keep
        # them in the report so the methodology page is consistent and the
        # user can see what we're planning to add.
        ScoreAxis(
            name="Tokenomics / Centralization",
            weight=0.0,
            score=None,
            rationale=(
                "Pending: integrating GoPlus Security API (owner / mint authority / "
                f"proxy detection). Planned weight when active: {int(AXIS_WEIGHTS_TARGET['Tokenomics / Centralization'] * 100)}%."
            ),
        ),
        ScoreAxis(
            name="Liquidity Risk",
            weight=0.0,
            score=None,
            rationale=(
                "Pending: integrating DefiLlama + GoPlus (LP-lock %, top holder concentration). "
                f"Planned weight: {int(AXIS_WEIGHTS_TARGET['Liquidity Risk'] * 100)}%."
            ),
        ),
        ScoreAxis(
            name="Team / KYC",
            weight=0.0,
            score=None,
            rationale=(
                "Pending: cross-reference deployer against MetaMask anti-phishing list, "
                f"GitHub repo signals. Planned weight: {int(AXIS_WEIGHTS_TARGET['Team / KYC'] * 100)}%."
            ),
        ),
        ScoreAxis(
            name="On-chain Behavior",
            weight=0.0,
            score=None,
            rationale=(
                "Pending: TVL trend (DefiLlama), volume / age / anomaly score. "
                f"Planned weight: {int(AXIS_WEIGHTS_TARGET['On-chain Behavior'] * 100)}%."
            ),
        ),
    ]

    # Only active axes contribute to the weighted score. Inactive axes have
    # weight=0 and score=None so the multiplication is `0 * None` — we use
    # an explicit filter to avoid that arithmetic edge case.
    weighted = sum(
        (a.score or 0.0) * a.weight for a in axes if a.weight > 0 and a.score is not None
    )
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
