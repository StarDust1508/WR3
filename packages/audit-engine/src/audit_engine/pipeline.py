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

from audit_engine.analyzers import StaticAnalyzerRegistry
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
    findings: list[Finding] = field(default_factory=list)
    _report: AuditReport | None = None

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

        source_code = source or await self._fetch_verified_source(address)
        if not source_code:
            yield PipelineEvent(
                stage="error",
                progress=0,
                message="Could not fetch verified source. Paste source manually or contact support.",
            )
            return

        # Stage 2 — Static analysis (parallel)
        yield PipelineEvent(stage="static", progress=15, message="Running static analyzers")
        static_findings = await StaticAnalyzerRegistry.run_all(
            source=source_code, network=self.network
        )
        self.findings.extend(static_findings)
        log.info("pipeline.static.done", count=len(static_findings))

        # Stage 3 — LLM triage (TODO: wire to audit_engine.agents)
        yield PipelineEvent(stage="triage", progress=40, message="LLM triage filtering FP")
        # await TriageOrchestrator().run(self.findings, source=source_code)

        # Stage 4 — Foundry PoC retry loop (TODO: wire to audit_engine.poc)
        yield PipelineEvent(stage="poc", progress=60, message="Generating PoCs for high-severity")
        # await PocGenerator().run(self.findings, source=source_code)

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
        return self._report.model_dump()

    async def _fetch_verified_source(self, address: str) -> str | None:
        """Pull verified source from explorer.

        Stub: returns None. Real impl in audit_engine.ingestion (TODO).
        """
        logger.warning("ingestion.fetch.stub", address=address)
        return None
