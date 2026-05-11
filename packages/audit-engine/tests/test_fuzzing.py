from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit_engine.fuzzing.analyzer import CounterexampleAnalyzer
from audit_engine.fuzzing.invariant_gen import InvariantGenerator
from audit_engine.fuzzing.orchestrator import FuzzingOrchestrator
from audit_engine.fuzzing.runner import (
    FuzzEngine,
    FuzzRunner,
    _build_harness,
    _parse_counterexamples,
)
from audit_engine.fuzzing.types import Counterexample, FuzzInvariant, FuzzResult
from audit_engine.llm import LLMRequest
from audit_engine.poc.artifacts import PoCArtifactStore

# --- LLM mock ---------------------------------------------------------------


class _ScriptedLLM:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[LLMRequest] = []

    async def complete(self, req: LLMRequest) -> str:
        self.calls.append(req)
        return self.response


class _MultiResponseLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[LLMRequest] = []

    async def complete(self, req: LLMRequest) -> str:
        self.calls.append(req)
        return self.responses.pop(0) if self.responses else "{}"


# --- InvariantGenerator -----------------------------------------------------


@pytest.mark.asyncio
async def test_invariant_generator_parses_valid_json() -> None:
    raw = json.dumps(
        {
            "invariants": [
                {
                    "name": "invariant_totalSupplyEq",
                    "body": "assert(true);",
                    "rationale": "balance accounting",
                    "severity_if_broken": "high",
                },
                {
                    "name": "invariant_anotherOne",
                    "body": "assert(false);",
                    "rationale": "x",
                    "severity_if_broken": "critical",
                },
            ]
        }
    )
    gen = InvariantGenerator(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    out = await gen.generate(source="contract A {}")
    assert len(out) == 2
    assert out[0].name == "invariant_totalSupplyEq"
    assert out[1].severity_if_broken == "critical"


@pytest.mark.asyncio
async def test_invariant_generator_strips_markdown_fences() -> None:
    raw = "```json\n" + json.dumps(
        {
            "invariants": [
                {"name": "invariant_x", "body": "assert(true);", "rationale": "x"}
            ]
        }
    ) + "\n```"
    gen = InvariantGenerator(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    out = await gen.generate(source="contract A {}")
    assert len(out) == 1


@pytest.mark.asyncio
async def test_invariant_generator_rejects_non_prefix_names() -> None:
    raw = json.dumps(
        {
            "invariants": [
                {"name": "doesNotStartWithPrefix", "body": "x", "rationale": ""},
                {"name": "invariant_ok", "body": "x", "rationale": ""},
                {"name": "invariant_$$bad", "body": "x", "rationale": ""},
            ]
        }
    )
    gen = InvariantGenerator(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    out = await gen.generate(source="contract A {}")
    assert [i.name for i in out] == ["invariant_ok"]


@pytest.mark.asyncio
async def test_invariant_generator_defaults_severity_when_invalid() -> None:
    raw = json.dumps(
        {
            "invariants": [
                {
                    "name": "invariant_x",
                    "body": "x",
                    "rationale": "",
                    "severity_if_broken": "WHATEVER",
                }
            ]
        }
    )
    gen = InvariantGenerator(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    out = await gen.generate(source="contract A {}")
    assert out[0].severity_if_broken == "high"


@pytest.mark.asyncio
async def test_invariant_generator_empty_source() -> None:
    gen = InvariantGenerator(llm=_ScriptedLLM("{}"))  # type: ignore[arg-type]
    out = await gen.generate(source="   ")
    assert out == []


# --- Harness construction ---------------------------------------------------


def test_harness_contains_invariants_and_imports() -> None:
    invs = [
        FuzzInvariant(
            name="invariant_a", body="assert(true);", rationale="ok"
        ),
        FuzzInvariant(
            name="invariant_b", body="uint x = 1;\nassert(x == 1);", rationale="x"
        ),
    ]
    src = _build_harness(invs)
    assert "import \"forge-std/Test.sol\";" in src
    assert "function invariant_a() public" in src
    assert "function invariant_b() public" in src
    assert "uint x = 1;" in src


# --- Counterexample parsing -------------------------------------------------


def test_parse_forge_failure_block() -> None:
    output = (
        "Running 2 tests for test/Invariant.t.sol:InvariantHarness\n"
        "[FAIL. Reason: Assertion failed.] invariant_totalSupplyEq()\n"
        " [Sequence]\n"
        "  sender=0x..\n"
        " ↪ MaliciousMint(...) at line 42\n"
        "Test result: FAILED. 1 passed; 1 failed\n"
    )
    ces = _parse_counterexamples(engine=FuzzEngine.FORGE, stdout=output, stderr="")
    assert len(ces) == 1
    assert ces[0].invariant_name == "invariant_totalSupplyEq"
    assert "Sequence" in ces[0].call_trace or "MaliciousMint" in ces[0].call_trace


def test_parse_medusa_failure_block() -> None:
    output = (
        "[*] fuzzing contract InvariantHarness\n"
        "  invariant \"invariant_balanceConsistency\" failed after 17 runs\n"
        "    call_sequence:\n"
        "      - withdraw(1000)\n"
        "      - deposit(0)\n"
        "[!] 1 of 3 invariants broken\n"
    )
    ces = _parse_counterexamples(engine=FuzzEngine.MEDUSA, stdout=output, stderr="")
    assert len(ces) == 1
    assert ces[0].invariant_name == "invariant_balanceConsistency"


def test_parse_no_failures() -> None:
    output = "[PASS] invariant_a() (runs: 256, calls: 8192)\n"
    ces = _parse_counterexamples(engine=FuzzEngine.FORGE, stdout=output, stderr="")
    assert ces == []


# --- FuzzRunner -------------------------------------------------------------


@pytest.mark.asyncio
async def test_fuzz_runner_returns_not_installed_when_no_binaries(tmp_path: Path) -> None:
    runner = FuzzRunner(
        medusa_bin="missing-binary-wr3-medusa",
        forge_bin="missing-binary-wr3-forge",
    )
    invs = [FuzzInvariant(name="invariant_x", body="assert(true);", rationale="ok")]
    out = await runner.run(
        workspace=tmp_path,
        target_source="contract X {}",
        invariants=invs,
    )
    assert out.installed is False
    assert (tmp_path / "test" / "Invariant.t.sol").exists()


@pytest.mark.asyncio
async def test_fuzz_runner_short_circuits_without_invariants(tmp_path: Path) -> None:
    runner = FuzzRunner(medusa_bin="x", forge_bin="x")
    out = await runner.run(workspace=tmp_path, target_source="X", invariants=[])
    assert out.installed is False
    assert out.engine == "no-invariants"


# --- CounterexampleAnalyzer -------------------------------------------------


@pytest.mark.asyncio
async def test_counterexample_analyzer_real_verdict() -> None:
    raw = json.dumps(
        {
            "verdicts": [
                {
                    "invariant": "invariant_x",
                    "verdict": "real",
                    "title": "Reward double-claim",
                    "description": "claim() does not zero balance.",
                    "rationale": "trace shows two claims of same epoch",
                }
            ]
        }
    )
    analyzer = CounterexampleAnalyzer(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    invs = [FuzzInvariant(name="invariant_x", body="x", rationale="ok")]
    ces = [
        Counterexample(invariant_name="invariant_x", call_trace="trace", reason="r")
    ]
    out = await analyzer.analyze(source="contract X {}", invariants=invs, counterexamples=ces)
    assert len(out) == 1
    assert out[0].verdict == "real"
    assert "double-claim" in out[0].title


@pytest.mark.asyncio
async def test_counterexample_analyzer_artifact_verdict_filtered() -> None:
    raw = json.dumps(
        {
            "verdicts": [
                {
                    "invariant": "invariant_x",
                    "verdict": "artifact",
                    "title": "",
                    "description": "",
                    "rationale": "invariant assumed wrong",
                }
            ]
        }
    )
    analyzer = CounterexampleAnalyzer(llm=_ScriptedLLM(raw))  # type: ignore[arg-type]
    invs = [FuzzInvariant(name="invariant_x", body="x", rationale="ok")]
    ces = [Counterexample(invariant_name="invariant_x", call_trace="t")]
    out = await analyzer.analyze(source="contract X {}", invariants=invs, counterexamples=ces)
    assert out[0].verdict == "artifact"


@pytest.mark.asyncio
async def test_counterexample_analyzer_llm_failure_falls_back_to_unclear() -> None:
    class _BrokenLLM:
        async def complete(self, req: LLMRequest) -> str:
            raise RuntimeError("nope")

    analyzer = CounterexampleAnalyzer(llm=_BrokenLLM())  # type: ignore[arg-type]
    invs = [FuzzInvariant(name="invariant_x", body="x", rationale="ok")]
    ces = [Counterexample(invariant_name="invariant_x", call_trace="t")]
    out = await analyzer.analyze(source="x", invariants=invs, counterexamples=ces)
    assert out[0].verdict == "unclear"


@pytest.mark.asyncio
async def test_counterexample_analyzer_empty_counterexamples() -> None:
    analyzer = CounterexampleAnalyzer(llm=_ScriptedLLM("{}"))  # type: ignore[arg-type]
    out = await analyzer.analyze(source="x", invariants=[], counterexamples=[])
    assert out == []


# --- FuzzingOrchestrator ----------------------------------------------------


class _FakeRunner:
    def __init__(self, result: FuzzResult) -> None:
        self.result = result
        self.last_call: dict | None = None

    async def run(self, **kwargs) -> FuzzResult:
        self.last_call = kwargs
        return self.result


@pytest.mark.asyncio
async def test_orchestrator_emits_finding_for_real_counterexample(tmp_path: Path) -> None:
    gen_resp = json.dumps(
        {
            "invariants": [
                {
                    "name": "invariant_x",
                    "body": "assert(true);",
                    "rationale": "ok",
                    "severity_if_broken": "critical",
                }
            ]
        }
    )
    analyzer_resp = json.dumps(
        {
            "verdicts": [
                {
                    "invariant": "invariant_x",
                    "verdict": "real",
                    "title": "Balance drained via reentry",
                    "description": "withdraw() updates state after send()",
                    "rationale": "trace shows recursion",
                }
            ]
        }
    )
    runner_result = FuzzResult(
        installed=True,
        engine="medusa",
        runs=128,
        duration_seconds=1.5,
        counterexamples=[
            Counterexample(invariant_name="invariant_x", call_trace="t", reason="bad")
        ],
        raw_stdout="",
        raw_stderr="",
    )

    orch = FuzzingOrchestrator(
        generator=InvariantGenerator(llm=_ScriptedLLM(gen_resp)),  # type: ignore[arg-type]
        runner=_FakeRunner(runner_result),  # type: ignore[arg-type]
        analyzer=CounterexampleAnalyzer(llm=_ScriptedLLM(analyzer_resp)),  # type: ignore[arg-type]
        store=PoCArtifactStore(root=tmp_path),
    )
    out = await orch.run(scan_id="s1", source="contract X {}")
    assert len(out.new_findings) == 1
    f = out.new_findings[0]
    assert f.severity.value == "critical"
    assert f.source_engine == "llm-fuzz-invariant"
    assert "Balance drained" in f.title


@pytest.mark.asyncio
async def test_orchestrator_skips_when_no_invariants(tmp_path: Path) -> None:
    orch = FuzzingOrchestrator(
        generator=InvariantGenerator(llm=_ScriptedLLM("{}")),  # type: ignore[arg-type]
        runner=_FakeRunner(FuzzResult.not_installed()),  # type: ignore[arg-type]
        analyzer=CounterexampleAnalyzer(llm=_ScriptedLLM("{}")),  # type: ignore[arg-type]
        store=PoCArtifactStore(root=tmp_path),
    )
    out = await orch.run(scan_id="s1", source="contract X {}")
    assert out.invariants == []
    assert out.new_findings == []
    assert "no invariants" in out.diagnostic


@pytest.mark.asyncio
async def test_orchestrator_skips_when_runner_not_installed(tmp_path: Path) -> None:
    gen_resp = json.dumps(
        {"invariants": [{"name": "invariant_x", "body": "assert(true);", "rationale": "x"}]}
    )
    orch = FuzzingOrchestrator(
        generator=InvariantGenerator(llm=_ScriptedLLM(gen_resp)),  # type: ignore[arg-type]
        runner=_FakeRunner(FuzzResult.not_installed()),  # type: ignore[arg-type]
        analyzer=CounterexampleAnalyzer(llm=_ScriptedLLM("{}")),  # type: ignore[arg-type]
        store=PoCArtifactStore(root=tmp_path),
    )
    out = await orch.run(scan_id="s1", source="contract X {}")
    assert out.new_findings == []
    assert "not available" in out.diagnostic


@pytest.mark.asyncio
async def test_orchestrator_drops_artifact_verdicts(tmp_path: Path) -> None:
    gen_resp = json.dumps(
        {"invariants": [{"name": "invariant_x", "body": "x", "rationale": ""}]}
    )
    analyzer_resp = json.dumps(
        {
            "verdicts": [
                {"invariant": "invariant_x", "verdict": "artifact", "title": "x",
                 "description": "", "rationale": "bad invariant"}
            ]
        }
    )
    runner_result = FuzzResult(
        installed=True,
        engine="forge-invariant",
        runs=64,
        duration_seconds=1.0,
        counterexamples=[Counterexample(invariant_name="invariant_x", call_trace="t")],
    )
    orch = FuzzingOrchestrator(
        generator=InvariantGenerator(llm=_ScriptedLLM(gen_resp)),  # type: ignore[arg-type]
        runner=_FakeRunner(runner_result),  # type: ignore[arg-type]
        analyzer=CounterexampleAnalyzer(llm=_ScriptedLLM(analyzer_resp)),  # type: ignore[arg-type]
        store=PoCArtifactStore(root=tmp_path),
    )
    out = await orch.run(scan_id="s1", source="contract X {}")
    assert out.new_findings == []
    assert "0/1 confirmed" in out.diagnostic
