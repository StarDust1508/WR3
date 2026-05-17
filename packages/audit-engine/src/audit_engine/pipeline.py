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

from audit_engine.agents import MultiAgentTriage, TriageOrchestrator
from audit_engine.analyzers import StaticAnalyzerRegistry
from audit_engine.fuzzing import FuzzingOrchestrator
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
    multi_agent_triage: bool = True
    poc_enabled: bool = True
    fuzzing_enabled: bool = True
    _report: AuditReport | None = None
    _triage: TriageOrchestrator | MultiAgentTriage | None = None
    _poc: PoCGenerator | None = None
    _fuzzing: FuzzingOrchestrator | None = None

    def __post_init__(self) -> None:
        if self.triage_enabled and self._triage is None:
            self._triage = (
                MultiAgentTriage() if self.multi_agent_triage else TriageOrchestrator()
            )
        if self.poc_enabled and self._poc is None:
            self._poc = PoCGenerator()
        if self.fuzzing_enabled and self._fuzzing is None:
            self._fuzzing = FuzzingOrchestrator()

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
            # Skip PoC for LLM-proposed findings — they're abstract claims
            # (e.g. "this contract might have business-logic flaw X") with
            # no concrete file/line for forge test to target. Attempting
            # them burns LLM tokens producing unprovable PoCs.
            targets = [
                f for f in self.findings
                if self._poc.should_attempt(f)
                and not f.source_engine.startswith("llm-")
                and f.line is not None
            ]
            log.info("pipeline.poc.targets", count=len(targets))
            # Index findings by id ONCE; per-finding update is now O(1)
            # instead of rewalking the whole findings list each iteration.
            # On a scan with 20 findings and 5 PoC targets the old code
            # did 100 model_copy() calls; this does 5.
            findings_by_id = {f.id: f for f in self.findings}
            for idx, finding in enumerate(targets):
                outcome = await self._poc.generate(
                    scan_id=self.scan_id or "ad-hoc",
                    finding=finding,
                    target_source=source_code,
                )
                original = findings_by_id.get(finding.id)
                if original is not None:
                    findings_by_id[finding.id] = original.model_copy(
                        update={
                            "poc_path": outcome.artifact_path,
                            "poc_validated": outcome.validated,
                            "metadata": {
                                **original.metadata,
                                "poc_attempts": outcome.attempts,
                                "poc_diagnostic": outcome.diagnostic,
                            },
                        }
                    )
                # Mid-stage progress nudges so UI doesn't sit still on long PoCs.
                yield PipelineEvent(
                    stage="poc",
                    progress=60 + int(20 * (idx + 1) / max(len(targets), 1)),
                    message=f"PoC {idx + 1}/{len(targets)}: {finding.title[:60]}",
                )
            # Materialize back into a list — preserves the original ordering
            # because dict insertion order is guaranteed in Python 3.7+ and
            # we built findings_by_id from the original list.
            self.findings = list(findings_by_id.values())

        # Stage 5 — AI-fuzzing with LLM-generated invariants.
        yield PipelineEvent(stage="fuzzing", progress=80, message="AI-fuzzing invariants")
        if self._fuzzing is not None:
            outcome = await self._fuzzing.run(
                scan_id=self.scan_id or "ad-hoc",
                source=source_code,
            )
            if outcome.new_findings:
                self.findings.extend(outcome.new_findings)
                log.info(
                    "pipeline.fuzzing.added",
                    count=len(outcome.new_findings),
                    invariants=len(outcome.invariants),
                    engine=outcome.fuzz_result.engine,
                )
            else:
                log.info(
                    "pipeline.fuzzing.no_findings",
                    diagnostic=outcome.diagnostic,
                    invariants=len(outcome.invariants),
                )
            yield PipelineEvent(
                stage="fuzzing",
                progress=88,
                message=outcome.diagnostic,
            )

        # Stage 6 — Formal verification — premium only, skip in MVP

        # Stage 7 — Scoring
        yield PipelineEvent(stage="scoring", progress=95, message="Computing score")
        self._report = compute_score(
            address=address,
            network=self.network,
            findings=self.findings,
        )

        # Chain-metadata enrichment. For Solana programs we pull
        # executable / upgrade-authority / last-upgrade-slot via public RPC
        # — works even when source code was pasted by the user, because
        # this reads on-chain state, not source. Failure is logged but
        # never blocks the report.
        if self.network == "solana":
            try:
                from audit_engine.ingestion.solana_metadata import SolanaMetadataFetcher
                meta = await SolanaMetadataFetcher().fetch(address)
                if meta is not None:
                    self._report.chain_metadata = meta.to_dict()
            except Exception as e:
                log.warning("pipeline.solana_metadata_failed", error=str(e))
        else:
            # EVM Tokenomics axis: enrich via GoPlus Security. Free public
            # API, no key required at our request volume. The scoring
            # module then promotes the axis from weight=0 to its target
            # weight ON THIS SCAN only — other axes stay pending until
            # they get their own real signal source.
            try:
                from audit_engine.enrichment.goplus import (
                    compute_liquidity_score,
                    compute_tokenomics_score,
                    fetch_token_security,
                )

                ts = await fetch_token_security(
                    address=address, network=self.network
                )
                if ts is not None:
                    self._report.chain_metadata = {
                        **(self._report.chain_metadata or {}),
                        "token_security": ts.to_dict(),
                    }

                    from audit_engine.scoring import AXIS_WEIGHTS_TARGET
                    from audit_engine.types import ScoreAxis

                    # Tokenomics — always activated (only requires the
                    # owner/proxy/mint flags from GoPlus).
                    tk_score, tk_rationale = compute_tokenomics_score(ts)
                    # Liquidity — requires holder_count, which GoPlus may
                    # omit for non-token contracts. compute_liquidity_score
                    # returns None in that case → axis stays pending.
                    liq = compute_liquidity_score(ts)

                    new_axes: list[ScoreAxis] = []
                    for axis in self._report.axes:
                        if axis.name == "Tokenomics / Centralization":
                            new_axes.append(ScoreAxis(
                                name=axis.name,
                                weight=AXIS_WEIGHTS_TARGET[axis.name],
                                score=tk_score,
                                rationale=tk_rationale,
                            ))
                        elif axis.name == "Liquidity Risk" and liq is not None:
                            liq_score, liq_rationale = liq
                            new_axes.append(ScoreAxis(
                                name=axis.name,
                                weight=AXIS_WEIGHTS_TARGET[axis.name],
                                score=liq_score,
                                rationale=liq_rationale,
                            ))
                        else:
                            new_axes.append(axis)
                    self._report.axes = new_axes
                    # Re-compute the weighted total since active axes
                    # changed — keep severity overrides intact.
                    self._report = _recompute_weighted_score(self._report)
            except Exception as e:
                log.warning("pipeline.goplus_failed", error=str(e))

        yield PipelineEvent(
            stage="done",
            progress=100,
            data={"score": self._report.score, "tier": self._report.tier},
        )

    def result(self) -> dict[str, Any]:
        if self._report is None:
            return {"status": "incomplete"}
        return self._report.model_dump(mode="json")


def _recompute_weighted_score(report: AuditReport) -> AuditReport:
    """Re-derive `report.score` + `report.tier` from the current axes.

    Called after enrichment promotes an axis from inactive (weight=0) to
    active. The axes carry their TZ-target weights (Code Security 0.35,
    Tokenomics 0.20, Liquidity 0.15, ...). When only some of those are
    active their total weight is < 1.0, so we re-normalise across the
    active set — keeps the final score on a clean 0-100 scale
    independent of how many enrichers fired this scan.

    Preserves the severity-override semantics from `scoring.compute_score`:
    a CRITICAL caps the score at 39.9 (tier=red), a HIGH caps at 69.9.
    """
    from typing import Literal

    from audit_engine.scoring import _tier
    from audit_engine.types import Severity

    active = [a for a in report.axes if a.weight > 0 and a.score is not None]
    total_weight = sum(a.weight for a in active)
    if total_weight <= 0:
        # No active axis → fall back to the raw Code Security score.
        cs = next((a for a in report.axes if a.name == "Code Security"), None)
        weighted = float(cs.score) if cs and cs.score is not None else 0.0
    else:
        # Re-normalise so weights sum to 1.0 across the active set.
        weighted = sum((a.score or 0.0) * (a.weight / total_weight) for a in active)
    score = round(weighted, 1)

    has_critical = any(f.severity == Severity.CRITICAL for f in report.findings)
    has_high = any(f.severity == Severity.HIGH for f in report.findings)
    tier: Literal["red", "yellow", "green", "blue"]
    if has_critical:
        tier = "red"
        score = min(score, 39.9)
    elif has_high:
        tier = _tier(min(score, 69.9))
        score = min(score, 69.9)
    else:
        tier = _tier(score)

    return report.model_copy(update={"score": score, "tier": tier})
