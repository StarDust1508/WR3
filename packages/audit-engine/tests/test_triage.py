from __future__ import annotations

import json

import pytest

from audit_engine.agents.triage import TriageOrchestrator
from audit_engine.llm import LLMRequest
from audit_engine.types import Finding, Severity


class _FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_request: LLMRequest | None = None

    async def complete(self, req: LLMRequest) -> str:
        self.last_request = req
        return self.response


def _fixture_findings() -> list[Finding]:
    return [
        Finding(
            id="baseline:tx-origin:5",
            title="Use of tx.origin",
            description="tx.origin used for auth",
            severity=Severity.HIGH,
            source_engine="baseline",
            line=5,
            confidence=0.7,
        ),
        Finding(
            id="baseline:floating-pragma:1",
            title="Floating pragma",
            description="^0.8",
            severity=Severity.INFO,
            source_engine="baseline",
            line=1,
            confidence=0.85,
        ),
        Finding(
            id="baseline:delegatecall:12",
            title="delegatecall to user input",
            description="",
            severity=Severity.CRITICAL,
            source_engine="baseline",
            line=12,
            confidence=0.6,
        ),
    ]


@pytest.mark.asyncio
async def test_dismiss_decision_marks_finding_dismissed() -> None:
    llm_response = json.dumps(
        {
            "decisions": [
                {
                    "id": "baseline:tx-origin:5",
                    "action": "dismiss",
                    "rationale": "Function is protected by onlyOwner modifier upstream",
                }
            ]
        }
    )
    orch = TriageOrchestrator(llm=_FakeLLM(llm_response))  # type: ignore[arg-type]
    out = await orch.run(_fixture_findings(), source="contract A {}")

    tx_origin = next(f for f in out if f.id == "baseline:tx-origin:5")
    assert tx_origin.dismissed is True
    assert "onlyOwner" in (tx_origin.dismissed_reason or "")


@pytest.mark.asyncio
async def test_reclassify_changes_severity() -> None:
    llm_response = json.dumps(
        {
            "decisions": [
                {
                    "id": "baseline:delegatecall:12",
                    "action": "reclassify",
                    "new_severity": "high",
                    "rationale": "Target is admin-only via require",
                }
            ]
        }
    )
    orch = TriageOrchestrator(llm=_FakeLLM(llm_response))  # type: ignore[arg-type]
    out = await orch.run(_fixture_findings(), source="contract A {}")

    dlg = next(f for f in out if f.id == "baseline:delegatecall:12")
    assert dlg.severity == Severity.HIGH
    assert dlg.metadata.get("triage_rationale", "").startswith("Target")


@pytest.mark.asyncio
async def test_info_finding_skips_triage() -> None:
    """INFO severity must not even be sent to the LLM."""
    llm = _FakeLLM('{"decisions": []}')
    orch = TriageOrchestrator(llm=llm)  # type: ignore[arg-type]

    out = await orch.run(_fixture_findings(), source="contract A {}")
    assert llm.last_request is not None
    user_prompt = llm.last_request.messages[1]["content"]
    assert "floating-pragma" not in user_prompt
    # The INFO finding is preserved untouched.
    assert any(f.id == "baseline:floating-pragma:1" for f in out)


@pytest.mark.asyncio
async def test_malformed_response_does_not_crash() -> None:
    orch = TriageOrchestrator(llm=_FakeLLM("not json at all"))  # type: ignore[arg-type]
    findings = _fixture_findings()
    out = await orch.run(findings, source="contract A {}")
    # All findings returned unchanged.
    assert [f.id for f in out] == [f.id for f in findings]


@pytest.mark.asyncio
async def test_json_in_markdown_fence_is_parsed() -> None:
    llm_response = (
        "```json\n"
        + json.dumps({"decisions": [{"id": "baseline:tx-origin:5", "action": "keep", "rationale": "ok"}]})
        + "\n```"
    )
    orch = TriageOrchestrator(llm=_FakeLLM(llm_response))  # type: ignore[arg-type]
    out = await orch.run(_fixture_findings(), source="contract A {}")
    tx_origin = next(f for f in out if f.id == "baseline:tx-origin:5")
    assert tx_origin.dismissed is False
    assert tx_origin.confidence > 0.7  # bumped because LLM kept it


@pytest.mark.asyncio
async def test_llm_exception_returns_findings_unchanged() -> None:
    class _BrokenLLM:
        async def complete(self, req: LLMRequest) -> str:
            raise RuntimeError("network down")

    orch = TriageOrchestrator(llm=_BrokenLLM())  # type: ignore[arg-type]
    findings = _fixture_findings()
    out = await orch.run(findings, source="contract A {}")
    assert [f.id for f in out] == [f.id for f in findings]
    assert all(not f.dismissed for f in out)
