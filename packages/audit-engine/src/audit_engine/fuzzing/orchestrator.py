"""End-to-end orchestrator for stage 5: generate -> fuzz -> analyze -> emit."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from audit_engine.fuzzing.analyzer import CounterexampleAnalyzer
from audit_engine.fuzzing.invariant_gen import InvariantGenerator
from audit_engine.fuzzing.runner import FuzzEngine, FuzzRunner
from audit_engine.fuzzing.types import FuzzInvariant, FuzzResult
from audit_engine.poc.artifacts import PoCArtifactStore
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


@dataclass
class FuzzingOutcome:
    invariants: list[FuzzInvariant]
    fuzz_result: FuzzResult
    new_findings: list[Finding]
    diagnostic: str


class FuzzingOrchestrator:
    """Stage 5 driver. Skips entirely if generator yields no invariants or
    no fuzz engine is installed."""

    def __init__(
        self,
        *,
        generator: InvariantGenerator | None = None,
        runner: FuzzRunner | None = None,
        analyzer: CounterexampleAnalyzer | None = None,
        store: PoCArtifactStore | None = None,
        engine: FuzzEngine = FuzzEngine.AUTO,
    ) -> None:
        self.generator = generator or InvariantGenerator()
        self.runner = runner or FuzzRunner(engine=engine)
        self.analyzer = analyzer or CounterexampleAnalyzer()
        # Re-use PoC artifact root for fuzz workspaces; they share the same
        # per-scan namespace.
        self.store = store or PoCArtifactStore()

    async def run(
        self,
        *,
        scan_id: str,
        source: str,
        existing_findings: list[Finding] | None = None,
    ) -> FuzzingOutcome:
        if not source.strip():
            return _empty("empty source")

        # Pass existing findings to guide invariant generation — the LLM
        # will write invariants specifically targeting known issues.
        active_findings = [f for f in (existing_findings or []) if not f.dismissed]
        invariants = await self.generator.generate(
            source=source,
            existing_findings=active_findings or None,
        )
        if not invariants:
            return _empty("no invariants generated")

        workspace = self.store.workspace_for(
            scan_id=scan_id, finding_id="fuzz-invariants"
        )
        fuzz_result = await self.runner.run(
            workspace=workspace,
            target_source=source,
            invariants=invariants,
        )
        if not fuzz_result.installed:
            return FuzzingOutcome(
                invariants=invariants,
                fuzz_result=fuzz_result,
                new_findings=[],
                diagnostic="fuzz engine not available",
            )

        if not fuzz_result.counterexamples:
            logger.info("fuzzing.no_counterexamples", invariants=len(invariants))
            return FuzzingOutcome(
                invariants=invariants,
                fuzz_result=fuzz_result,
                new_findings=[],
                diagnostic=f"{fuzz_result.engine}: 0 counterexamples in {fuzz_result.duration_seconds:.1f}s",
            )

        verdicts = await self.analyzer.analyze(
            source=source,
            invariants=invariants,
            counterexamples=fuzz_result.counterexamples,
        )

        # Build a map: invariant name -> severity_if_broken
        sev_lookup = {i.name: i.severity_if_broken for i in invariants}

        findings: list[Finding] = []
        for verdict in verdicts:
            if verdict.verdict == "artifact":
                continue
            sev_str = sev_lookup.get(verdict.invariant_name, "high")
            try:
                sev = Severity(sev_str)
            except ValueError:
                sev = Severity.HIGH

            # Unclear -> downgrade confidence + severity.
            confidence = 0.5 if verdict.verdict == "unclear" else 0.75

            findings.append(
                Finding(
                    id=f"llm-fuzz-invariant:{verdict.invariant_name}",
                    title=verdict.title or f"Invariant {verdict.invariant_name} broke",
                    description=verdict.description or "",
                    severity=sev,
                    source_engine="llm-fuzz-invariant",
                    confidence=confidence,
                    metadata={
                        "rationale": verdict.rationale,
                        "fuzz_engine": fuzz_result.engine,
                        "fuzz_runs": fuzz_result.runs,
                    },
                )
            )

        return FuzzingOutcome(
            invariants=invariants,
            fuzz_result=fuzz_result,
            new_findings=findings,
            diagnostic=f"{fuzz_result.engine}: {len(findings)}/{len(verdicts)} confirmed",
        )


def _empty(reason: str) -> FuzzingOutcome:
    return FuzzingOutcome(
        invariants=[],
        fuzz_result=FuzzResult.not_installed("skipped"),
        new_findings=[],
        diagnostic=reason,
    )
