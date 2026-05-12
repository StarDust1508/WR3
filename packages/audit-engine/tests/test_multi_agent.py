from __future__ import annotations

import json

import pytest

from audit_engine.agents.multi_agent import (
    AgentDecision,
    AgentReport,
    MultiAgentTriage,
    ProposedFinding,
    _consensus_merge,
)
from audit_engine.llm import LLMRequest
from audit_engine.types import Finding, Severity


def _finding(
    fid: str = "baseline:tx-origin:5",
    severity: Severity = Severity.HIGH,
    *,
    confidence: float = 0.7,
    dismissed: bool = False,
) -> Finding:
    return Finding(
        id=fid,
        title="Use of tx.origin",
        description="tx.origin used for auth",
        severity=severity,
        source_engine="baseline",
        line=5,
        confidence=confidence,
        dismissed=dismissed,
    )


# --- Consensus rules (unit) --------------------------------------------------


def test_consensus_reclassify_wins_from_severity_agent() -> None:
    f = _finding(severity=Severity.HIGH)
    reports = [
        AgentReport(
            agent="severity",
            decisions=[
                AgentDecision(
                    finding_id=f.id,
                    action="reclassify",
                    new_severity=Severity.CRITICAL,
                    rationale="reachable from public function with no gate",
                )
            ],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert out[0].severity == Severity.CRITICAL
    assert "no gate" in out[0].metadata.get("sev_rationale", "")


def test_consensus_fp_dismisses_when_severity_also_lowers() -> None:
    f = _finding()
    reports = [
        AgentReport(
            agent="severity",
            decisions=[
                AgentDecision(
                    finding_id=f.id,
                    action="reclassify",
                    new_severity=Severity.INFO,
                )
            ],
        ),
        AgentReport(
            agent="fp",
            decisions=[
                AgentDecision(
                    finding_id=f.id,
                    action="dismiss",
                    rationale="onlyOwner upstream",
                )
            ],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert out[0].dismissed is True
    assert "onlyOwner" in (out[0].dismissed_reason or "")


def test_consensus_confirm_blocks_fp_dismissal() -> None:
    """When business or cross agents confirm, FP cannot dismiss."""
    f = _finding()
    reports = [
        AgentReport(
            agent="fp",
            decisions=[
                AgentDecision(finding_id=f.id, action="dismiss", rationale="looks safe"),
            ],
        ),
        AgentReport(
            agent="business",
            decisions=[
                AgentDecision(
                    finding_id=f.id,
                    action="confirm",
                    rationale="reachable via batchExecute()",
                )
            ],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert out[0].dismissed is False


def test_consensus_confirm_bumps_severity_one_tier() -> None:
    f = _finding(severity=Severity.MEDIUM)
    reports = [
        AgentReport(
            agent="cross",
            decisions=[
                AgentDecision(
                    finding_id=f.id, action="confirm", rationale="proxy upgrade path"
                )
            ],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert out[0].severity == Severity.HIGH


def test_consensus_proposed_findings_appended() -> None:
    f = _finding()
    reports = [
        AgentReport(
            agent="business",
            proposed=[
                ProposedFinding(
                    title="Reward double-claim",
                    description="claim() does not zero balance",
                    severity=Severity.HIGH,
                    line=42,
                    rationale="lastClaimed not updated",
                ),
            ],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert len(out) == 2
    new = next(x for x in out if x.id != f.id)
    assert new.severity == Severity.HIGH
    assert new.line == 42
    assert new.source_engine == "llm-business"


def test_consensus_failed_agent_has_no_veto() -> None:
    f = _finding()
    reports = [
        AgentReport(
            agent="severity",
            decisions=[
                AgentDecision(
                    finding_id=f.id,
                    action="reclassify",
                    new_severity=Severity.CRITICAL,
                )
            ],
        ),
        AgentReport(agent="fp", failed=True, error="parse failed"),
        AgentReport(agent="business", failed=True, error="timeout"),
        AgentReport(agent="cross", failed=True, error="network down"),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    assert out[0].severity == Severity.CRITICAL
    assert out[0].dismissed is False


def test_consensus_confidence_bumps_per_agent_touch() -> None:
    f = _finding(confidence=0.5)
    reports = [
        AgentReport(
            agent="severity",
            decisions=[AgentDecision(finding_id=f.id, action="keep")],
        ),
        AgentReport(
            agent="fp",
            decisions=[AgentDecision(finding_id=f.id, action="keep")],
        ),
        AgentReport(
            agent="business",
            decisions=[AgentDecision(finding_id=f.id, action="confirm")],
        ),
    ]
    out = _consensus_merge(originals=[f], reports=reports)
    # 3 touches → +0.3 → 0.8
    assert 0.79 < out[0].confidence < 0.81


# --- End-to-end with mocked LLM ---------------------------------------------


class _ScriptedLLM:
    """Returns a different canned response per agent based on the system prompt fingerprint."""

    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[LLMRequest] = []

    async def complete(self, req: LLMRequest) -> str:
        self.calls.append(req)
        system = req.messages[0]["content"]
        for marker, body in self.responses.items():
            if marker in system:
                return body
        return '{"decisions": [], "proposed": []}'


@pytest.mark.asyncio
async def test_multi_agent_runs_all_four_in_parallel() -> None:
    f = _finding()
    llm = _ScriptedLLM(
        {
            "normalize severity": json.dumps(
                {"decisions": [{"id": f.id, "action": "keep", "rationale": "ok"}]}
            ),
            "flag false positives": json.dumps(
                {"decisions": [{"id": f.id, "action": "keep", "rationale": "real"}]}
            ),
            "business-logic flaws": json.dumps(
                {
                    "decisions": [
                        {"id": f.id, "action": "confirm", "rationale": "reachable"}
                    ],
                    "proposed": [],
                }
            ),
            "cross-contract risks": json.dumps(
                {"decisions": [], "proposed": []}
            ),
        }
    )
    orch = MultiAgentTriage(llm=llm)  # type: ignore[arg-type]
    out = await orch.run([f], source="contract X {}")

    # 4 LLM calls, one per sub-agent.
    assert len(llm.calls) == 4
    # Confirm from business should bump severity HIGH -> CRITICAL.
    assert out[0].severity == Severity.CRITICAL
    assert out[0].dismissed is False


@pytest.mark.asyncio
async def test_multi_agent_dismisses_when_severity_and_fp_agree() -> None:
    f = _finding()
    llm = _ScriptedLLM(
        {
            "normalize severity": json.dumps(
                {
                    "decisions": [
                        {
                            "id": f.id,
                            "action": "reclassify",
                            "new_severity": "info",
                            "rationale": "test contract only",
                        }
                    ]
                }
            ),
            "flag false positives": json.dumps(
                {
                    "decisions": [
                        {
                            "id": f.id,
                            "action": "dismiss",
                            "rationale": "modifier protects upstream",
                        }
                    ]
                }
            ),
            "business-logic flaws": json.dumps({"decisions": [], "proposed": []}),
            "cross-contract risks": json.dumps({"decisions": [], "proposed": []}),
        }
    )
    orch = MultiAgentTriage(llm=llm)  # type: ignore[arg-type]
    out = await orch.run([f], source="contract X {}")
    assert out[0].dismissed is True


@pytest.mark.asyncio
async def test_multi_agent_appends_new_findings_from_business_and_cross() -> None:
    f = _finding()
    llm = _ScriptedLLM(
        {
            "normalize severity": '{"decisions": []}',
            "flag false positives": '{"decisions": []}',
            "business-logic flaws": json.dumps(
                {
                    "decisions": [],
                    "proposed": [
                        {
                            "title": "Oracle staleness",
                            "severity": "high",
                            "line": 17,
                            "description": "latestRoundData() not checked",
                            "rationale": "stale price risk",
                        }
                    ],
                }
            ),
            "cross-contract risks": json.dumps(
                {
                    "decisions": [],
                    "proposed": [
                        {
                            "title": "Unverified delegatecall target",
                            "severity": "critical",
                            "description": "target loaded from user input",
                            "rationale": "no allowlist",
                        }
                    ],
                }
            ),
        }
    )
    orch = MultiAgentTriage(llm=llm)  # type: ignore[arg-type]
    out = await orch.run([f], source="contract X {}")

    titles = [x.title for x in out]
    assert "Oracle staleness" in titles
    assert "Unverified delegatecall target" in titles
    engines = [x.source_engine for x in out if x.id != f.id]
    assert {"llm-business", "llm-cross"} <= set(engines)


@pytest.mark.asyncio
async def test_multi_agent_resilient_to_broken_llm() -> None:
    """One broken response shouldn't poison the rest."""
    f = _finding()
    llm = _ScriptedLLM(
        {
            "normalize severity": "not even json",
            "flag false positives": '{"decisions": [{"id": "' + f.id + '", "action": "dismiss", "rationale": "ok"}]}',
            "business-logic flaws": '{"decisions": [], "proposed": []}',
            "cross-contract risks": '{"decisions": [], "proposed": []}',
        }
    )
    orch = MultiAgentTriage(llm=llm)  # type: ignore[arg-type]
    out = await orch.run([f], source="contract X {}")
    # severity report failed -> dismissal still happens because no confirms
    # and FP can dismiss even without low-severity agreement when sev is unknown.
    assert out[0].dismissed is True


@pytest.mark.asyncio
async def test_multi_agent_skips_when_only_info_findings() -> None:
    f = _finding(severity=Severity.INFO)
    llm = _ScriptedLLM({})
    orch = MultiAgentTriage(llm=llm)  # type: ignore[arg-type]
    out = await orch.run([f], source="")
    # No source, no triageable findings - returned untouched, no LLM calls.
    assert out == [f]
    assert llm.calls == []
