from __future__ import annotations

from pathlib import Path

import pytest

from audit_engine.llm import LLMRequest
from audit_engine.poc.artifacts import PoCArtifactStore
from audit_engine.poc.foundry_runner import ForgeTestResult
from audit_engine.poc.generator import PoCGenerator
from audit_engine.types import Finding, Severity


def _finding(severity: Severity = Severity.HIGH, dismissed: bool = False) -> Finding:
    return Finding(
        id="baseline:tx-origin:5",
        title="Use of tx.origin",
        description="bad auth",
        severity=severity,
        source_engine="baseline",
        line=5,
        confidence=0.7,
        dismissed=dismissed,
    )


class _ScriptedLLM:
    """Returns a queued list of canned responses."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[LLMRequest] = []

    async def complete(self, req: LLMRequest) -> str:
        self.calls.append(req)
        return self.responses.pop(0) if self.responses else "// no more responses"


class _ScriptedRunner:
    """Returns queued ForgeTestResult values, one per call."""

    def __init__(self, results: list[ForgeTestResult]) -> None:
        self.results = list(results)
        self.calls: list[dict] = []

    async def run(
        self,
        *,
        workspace: Path,
        target_source: str,
        test_source: str,
        target_filename: str = "Contract.sol",
        test_filename: str = "PoC.t.sol",
    ) -> ForgeTestResult:
        self.calls.append({"workspace": workspace, "test_source": test_source})
        # Still write the workspace skeleton like the real runner.
        workspace.mkdir(parents=True, exist_ok=True)
        return self.results.pop(0) if self.results else ForgeTestResult.not_installed()


def _ok() -> ForgeTestResult:
    return ForgeTestResult(
        installed=True,
        compiled=True,
        passed=True,
        raw_stdout="{}",
        raw_stderr="",
        test_failures=[],
        revert_reason=None,
        return_code=0,
    )


def _fail(reason: str) -> ForgeTestResult:
    return ForgeTestResult(
        installed=True,
        compiled=True,
        passed=False,
        raw_stdout="{}",
        raw_stderr="",
        test_failures=[reason],
        revert_reason=reason,
        return_code=1,
    )


@pytest.mark.asyncio
async def test_should_attempt_filters_by_severity_and_dismissed() -> None:
    gen = PoCGenerator()
    assert gen.should_attempt(_finding(Severity.CRITICAL)) is True
    assert gen.should_attempt(_finding(Severity.HIGH)) is True
    assert gen.should_attempt(_finding(Severity.MEDIUM)) is False
    assert gen.should_attempt(_finding(Severity.LOW)) is False
    assert gen.should_attempt(_finding(Severity.INFO)) is False
    assert gen.should_attempt(_finding(Severity.HIGH, dismissed=True)) is False


@pytest.mark.asyncio
async def test_first_attempt_passes(tmp_path: Path) -> None:
    llm = _ScriptedLLM(["// solid test\ncontract PoC {}"])
    runner = _ScriptedRunner([_ok()])
    store = PoCArtifactStore(root=tmp_path)

    gen = PoCGenerator(llm=llm, runner=runner, store=store, max_attempts=3)
    out = await gen.generate(
        scan_id="scan-1",
        finding=_finding(),
        target_source="contract V {}",
    )
    assert out.validated is True
    assert out.attempts == 1
    assert out.artifact_path is not None
    assert (tmp_path / "scan-1" / "baseline_tx-origin_5" / "PoC.attempt1.t.sol").exists()


@pytest.mark.asyncio
async def test_retries_until_pass(tmp_path: Path) -> None:
    llm = _ScriptedLLM(["// v1", "// v2", "// v3"])
    runner = _ScriptedRunner([_fail("revert: nothing happened"), _ok()])
    store = PoCArtifactStore(root=tmp_path)

    gen = PoCGenerator(llm=llm, runner=runner, store=store, max_attempts=3)
    out = await gen.generate(
        scan_id="scan-1",
        finding=_finding(),
        target_source="contract V {}",
    )
    assert out.validated is True
    assert out.attempts == 2
    # Second attempt should have received the failure trace.
    assert len(llm.calls) == 2
    second_user_messages = [m["content"] for m in llm.calls[1].messages if m["role"] == "user"]
    assert any("nothing happened" in m for m in second_user_messages)


@pytest.mark.asyncio
async def test_exhausts_retries(tmp_path: Path) -> None:
    llm = _ScriptedLLM(["// a", "// b", "// c"])
    runner = _ScriptedRunner([_fail("r1"), _fail("r2"), _fail("r3")])
    store = PoCArtifactStore(root=tmp_path)

    gen = PoCGenerator(llm=llm, runner=runner, store=store, max_attempts=3)
    out = await gen.generate(
        scan_id="s",
        finding=_finding(),
        target_source="contract V {}",
    )
    assert out.validated is False
    assert out.attempts == 3


@pytest.mark.asyncio
async def test_forge_missing_aborts_without_retries(tmp_path: Path) -> None:
    llm = _ScriptedLLM(["// won't matter"])
    runner = _ScriptedRunner([ForgeTestResult.not_installed()])
    store = PoCArtifactStore(root=tmp_path)

    gen = PoCGenerator(llm=llm, runner=runner, store=store, max_attempts=5)
    out = await gen.generate(
        scan_id="s",
        finding=_finding(),
        target_source="contract V {}",
    )
    assert out.validated is False
    assert out.attempts == 1
    assert "not installed" in out.diagnostic


@pytest.mark.asyncio
async def test_strips_markdown_fences_from_llm_output(tmp_path: Path) -> None:
    raw = "```solidity\ncontract PoC {}\n```"
    llm = _ScriptedLLM([raw])
    runner = _ScriptedRunner([_ok()])
    store = PoCArtifactStore(root=tmp_path)

    gen = PoCGenerator(llm=llm, runner=runner, store=store, max_attempts=2)
    await gen.generate(
        scan_id="s",
        finding=_finding(),
        target_source="contract V {}",
    )
    saved = (tmp_path / "s" / "baseline_tx-origin_5" / "PoC.attempt1.t.sol").read_text()
    assert "```" not in saved
    assert "contract PoC" in saved


@pytest.mark.asyncio
async def test_empty_source_short_circuits() -> None:
    gen = PoCGenerator(llm=_ScriptedLLM([]), runner=_ScriptedRunner([]))
    out = await gen.generate(scan_id="s", finding=_finding(), target_source="   ")
    assert out.validated is False
    assert out.attempts == 0
    assert "empty" in out.diagnostic.lower()
