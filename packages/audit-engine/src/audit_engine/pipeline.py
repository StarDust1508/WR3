"""Audit pipeline orchestrator.

7-layer pipeline as specified in TZ.md §4.1:
    1. Ingestion (source pull / AST)
    2. Multi-engine static analysis
    3. LLM triage (multi-agent, Trident Arena pattern)
    4. Foundry PoC generation (retry loop)
    5. AI fuzzing with generated invariants
    6. Formal verification (optional, premium)
    7. Scoring + reporting
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import structlog

from audit_engine.agents import TriageOrchestrator
from audit_engine.analyzers import StaticAnalyzerRegistry
from audit_engine.ingestion import SourceBundle, fetch_source
from audit_engine.poc import PoCGenerator
from audit_engine.scoring import compute_score
from audit_engine.types import AuditReport, Finding, Network

logger = structlog.get_logger()


@dataclass
class PipelineEvent:
    stage: str
    progress: int  # 0..100
    message: str | None = None
    data: dict[str, Any] | None = None


@dataclass
class AuditPipeline:
    """Orchestrates the audit pipeline for a single contract."""

    network: Network
    scan_id: str | None = None
    findings: list[Finding] = field(default_factory=list)
    triage_enabled: bool = True
    poc_enabled: bool = True
    _report: AuditReport | None = None
    _triage: TriageOrchestrator | None = None
    _poc: PoCGenerator | None = None

    def __post_init__(self) -> None:
        if self.triage_enabled and self._triage is None:
            self._triage = TriageOrchestrator()
        if self.poc_enabled and self._poc is None:
            self._poc = PoCGenerator()

    async def run(
        self,
        *,
        address: str,
        source: str | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        """Yield PipelineEvent at each stage transition.

        Caller (Celery worker) translates events into Redis progress updates
        consumed by the SSE endpoint.
        """
        log = logger.bind(address=address, network=self.network)

        # Stage 1 — Ingestion
        yield PipelineEvent(stage="queued", progress=2, message="Preparing")

        bundle: SourceBundle | None = None
        if source:
            source_code = source
        else:
            yield PipelineEvent(
                stage="queued", progress=5, message="Pulling verified source from explorer"
            )
            bundle = await fetch_source(address=address, network=self.network)
            if bundle is None or not bundle.primary_source:
                yield PipelineEvent(
                    stage="error",
                    progress=0,
                    message=(
                        "Could not fetch verified source. Contract may be unverified, "
                        "or the network is not yet supported. Paste source manually."
                    ),
                )
                return
            source_code = bundle.primary_source
            if bundle.proxy and bundle.implementation:
                logger.info(
                    "pipeline.proxy_detected",
                    proxy=address,
                    implementation=bundle.implementation,
                )

        # Stage 2 — Static analysis (parallel)
        yield PipelineEvent(stage="static", progress=15, message="Running static analyzers")
        static_findings = await StaticAnalyzerRegistry.run_all(
            source=source_code, network=self.network
        )
        self.findings.extend(static_findings)
        log.info("pipeline.static.done", count=len(static_findings))

        # Stage 3 — LLM triage (multi-agent, single-call for cost)
        yield PipelineEvent(stage="triage", progress=40, message="LLM triage filtering FP")
        if self._triage is not None and self.findings:
            self.findings = await self._triage.run(self.findings, source=source_code)
            log.info(
                "pipeline.triage.done",
                count=len(self.findings),
                dismissed=sum(1 for f in self.findings if f.dismissed),
            )

        # Stage 4 — Foundry PoC generation for HIGH/CRITICAL findings.
        yield PipelineEvent(stage="poc", progress=60, message="Generating PoCs for high-severity")
        if self._poc is not None:
            targets = [f for f in self.findings if self._poc.should_attempt(f)]
            log.info("pipeline.poc.targets", count=len(targets))
            for idx, finding in enumerate(targets):
                outcome = await self._poc.generate(
                    scan_id=self.scan_id or "ad-hoc",
                    finding=finding,
                    target_source=source_code,
                )
                self.findings = [
                    f.model_copy(
                        update={
                            "poc_path": outcome.artifact_path,
                            "poc_validated": outcome.validated,
                            "metadata": {
                                **f.metadata,
                                "poc_attempts": outcome.attempts,
                                "poc_diagnostic": outcome.diagnostic,
                            },
                        }
                    )
                    if f.id == finding.id
                    else f
                    for f in self.findings
                ]
                # Mid-stage progress nudges so UI doesn't sit still on long PoCs.
                yield PipelineEvent(
                    stage="poc",
                    progress=60 + int(20 * (idx + 1) / max(len(targets), 1)),
                    message=f"PoC {idx + 1}/{len(targets)}: {finding.title[:60]}",
                )

        # Stage 5 — AI-fuzzing (TODO)
        yield PipelineEvent(stage="fuzzing", progress=80, message="AI-fuzzing invariants")

        # Stage 6 — Formal verification — premium only, skip in MVP

        # Stage 7 — Scoring
        yield PipelineEvent(stage="scoring", progress=95, message="Computing score")
        self._report = compute_score(
            address=address,
            network=self.network,
            findings=self.findings,
        )

        yield PipelineEvent(
            stage="done",
            progress=100,
            data={"score": self._report.score, "tier": self._report.tier},
        )

    def result(self) -> dict[str, Any]:
        if self._report is None:
            return {"status": "incomplete"}
        return self._report.model_dump(mode="json")
