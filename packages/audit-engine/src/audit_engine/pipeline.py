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
from audit_engine.ingestion import SourceBundle, fetch_source_with_implementation
from audit_engine.llm.router import AllProvidersExhaustedError
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

        # Stage 1 — Ingestion (with proxy implementation fetch)
        yield PipelineEvent(stage="queued", progress=2, message="Preparing")

        bundle: SourceBundle | None = None
        source_code: str | None = None
        has_source = False
        source_truncated = False
        original_source_len = 0
        # Track which engines actually ran for coverage reporting.
        engines_ran: list[str] = []
        pre_dedup_count = 0

        if source:
            source_code = source
            has_source = True
        else:
            yield PipelineEvent(
                stage="queued", progress=5, message="Pulling verified source from explorer"
            )
            # fetch_source_with_implementation: if the contract is a proxy,
            # automatically fetches implementation source too. This is critical
            # for 70%+ of DeFi contracts which are behind proxies.
            bundle = await fetch_source_with_implementation(
                address=address, network=self.network
            )
            if bundle is not None and bundle.primary_source:
                source_code = bundle.primary_source
                has_source = True
                if bundle.proxy and bundle.implementation:
                    log.info(
                        "pipeline.proxy_resolved",
                        proxy=address,
                        implementation=bundle.implementation,
                        impl_source_len=len(source_code),
                    )
            else:
                log.info("pipeline.no_source_enrichment_only", network=self.network)

        # Track source size for truncation warnings.
        if source_code:
            original_source_len = len(source_code)
            if original_source_len > 48_000:
                source_truncated = True
                log.warning(
                    "pipeline.source_truncated",
                    original_len=original_source_len,
                    truncated_to=48_000,
                    chars_invisible=original_source_len - 48_000,
                )

        # Stage 2 — Static analysis (parallel)
        yield PipelineEvent(stage="static", progress=15, message="Running static analyzers")
        if has_source:
            static_findings = await StaticAnalyzerRegistry.run_all(
                source=source_code, network=self.network
            )
            self.findings.extend(static_findings)
            # Track which engines actually produced results.
            engines_ran = list({f.source_engine for f in static_findings})
            log.info("pipeline.static.done", count=len(static_findings), engines=engines_ran)

            # Cross-engine deduplication: merge findings from different engines
            # that describe the same vulnerability at the same location.
            from audit_engine.dedup import deduplicate_findings
            pre_dedup_count = len(self.findings)
            self.findings = deduplicate_findings(self.findings)
            if pre_dedup_count != len(self.findings):
                log.info(
                    "pipeline.dedup",
                    before=pre_dedup_count,
                    after=len(self.findings),
                    merged=pre_dedup_count - len(self.findings),
                )

            # Network-aware confidence adjustment
            from audit_engine.analyzers.network_context import (
                adjust_confidence_for_network,
                generate_l2_warnings,
            )

            self.findings = adjust_confidence_for_network(self.findings, self.network)
            l2_warnings = generate_l2_warnings(self.network)
            if l2_warnings:
                self.findings.extend(l2_warnings)
                log.info(
                    "pipeline.l2_warnings_added",
                    count=len(l2_warnings),
                    network=self.network,
                )
        else:
            log.info("pipeline.static.skipped_no_source")

        # Stage 3 — LLM triage (multi-agent, single-call for cost)
        yield PipelineEvent(stage="triage", progress=40, message="LLM triage filtering FP")
        llm_available = True
        if not has_source:
            log.info("pipeline.triage.skipped_no_source")
        elif self._triage is not None and self.findings:
            try:
                self.findings = await self._triage.run(self.findings, source=source_code)
                log.info(
                    "pipeline.triage.done",
                    count=len(self.findings),
                    dismissed=sum(1 for f in self.findings if f.dismissed),
                )
            except AllProvidersExhaustedError:
                llm_available = False
                log.warning("pipeline.triage.skipped_no_llm")
                yield PipelineEvent(
                    stage="triage", progress=42,
                    message="LLM unavailable — triage skipped, raw findings preserved",
                )

        # Stage 4 — Foundry PoC generation for HIGH/CRITICAL findings.
        yield PipelineEvent(stage="poc", progress=60, message="Generating PoCs for high-severity")
        if not has_source:
            log.info("pipeline.poc.skipped_no_source")
        elif self._poc is not None and llm_available:
            try:
                targets = [
                    f for f in self.findings
                    if self._poc.should_attempt(f)
                    and not f.source_engine.startswith("llm-")
                    and f.line is not None
                ]
                log.info("pipeline.poc.targets", count=len(targets))
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
                    yield PipelineEvent(
                        stage="poc",
                        progress=60 + int(20 * (idx + 1) / max(len(targets), 1)),
                        message=f"PoC {idx + 1}/{len(targets)}: {finding.title[:60]}",
                    )
                self.findings = list(findings_by_id.values())
            except AllProvidersExhaustedError:
                llm_available = False
                log.warning("pipeline.poc.skipped_no_llm")
                yield PipelineEvent(
                    stage="poc", progress=78,
                    message="LLM unavailable — PoC generation skipped",
                )
        elif self._poc is not None and not llm_available:
            yield PipelineEvent(
                stage="poc", progress=78,
                message="LLM unavailable — PoC generation skipped",
            )

        # Stage 5 — AI-fuzzing with LLM-generated invariants.
        yield PipelineEvent(stage="fuzzing", progress=80, message="AI-fuzzing invariants")
        if not has_source:
            log.info("pipeline.fuzzing.skipped_no_source")
        elif self._fuzzing is not None and llm_available:
            try:
                outcome = await self._fuzzing.run(
                    scan_id=self.scan_id or "ad-hoc",
                    source=source_code,
                    existing_findings=self.findings,
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
            except AllProvidersExhaustedError:
                log.warning("pipeline.fuzzing.skipped_no_llm")
                yield PipelineEvent(
                    stage="fuzzing", progress=88,
                    message="LLM unavailable — fuzzing skipped",
                )
        elif self._fuzzing is not None and not llm_available:
            yield PipelineEvent(
                stage="fuzzing", progress=88,
                message="LLM unavailable — fuzzing skipped",
            )

        # Stage 6 — Formal verification — premium only, skip in MVP

        # Stage 7 — Scoring
        yield PipelineEvent(stage="scoring", progress=95, message="Computing score")
        self._report = compute_score(
            address=address,
            network=self.network,
            findings=self.findings,
        )

        # Coverage metadata: tell the user which engines actually ran and
        # whether source was truncated. This prevents false confidence when
        # only baseline regex ran (because Slither/Aderyn/Wake aren't installed).
        all_expected_engines = (
            ["baseline", "aderyn", "wake", "slither"]
            if self.network != "solana"
            else ["solana-sealevel"]
        )
        coverage_info = {
            "engines_ran": engines_ran,
            "engines_expected": all_expected_engines,
            "engines_missing": [e for e in all_expected_engines if e not in engines_ran],
            "source_chars": original_source_len,
            "source_truncated": source_truncated,
            "llm_triage": llm_available and self.triage_enabled,
            "poc_enabled": self.poc_enabled,
            "fuzzing_enabled": self.fuzzing_enabled,
            "proxy_resolved": bundle.proxy if bundle else False,
            "implementation_address": bundle.implementation if bundle and bundle.proxy else None,
            "findings_before_dedup": pre_dedup_count if has_source else 0,
            "findings_after_dedup": len(self.findings) if has_source else 0,
            "network_aware": self.network != "solana",  # Solana has its own analyzer
        }
        self._report.chain_metadata = {
            **(self._report.chain_metadata or {}),
            "coverage": coverage_info,
        }

        # Warn in metadata if coverage is degraded.
        warnings: list[str] = []
        if coverage_info["engines_missing"]:
            missing = ", ".join(coverage_info["engines_missing"])
            warnings.append(
                f"Static analyzers not available: {missing}. "
                "Install them for deeper analysis."
            )
        if source_truncated:
            warnings.append(
                f"Source code ({original_source_len:,} chars) was truncated to 48,000 chars "
                f"for LLM analysis. {original_source_len - 48_000:,} chars were not reviewed "
                "by AI triage."
            )
        if not llm_available:
            warnings.append(
                "LLM provider unavailable — triage, PoC generation, and fuzzing were skipped. "
                "Raw static-analysis findings only."
            )
        if warnings:
            self._report.chain_metadata["audit_warnings"] = warnings
            log.warning("pipeline.coverage_warnings", warnings=warnings)

        # Chain-metadata enrichment. For Solana programs we pull
        # executable / upgrade-authority / last-upgrade-slot via public RPC
        # — works even when source code was pasted by the user, because
        # this reads on-chain state, not source. Failure is logged but
        # never blocks the report.
        if self.network == "solana":
            try:
                import asyncio

                from audit_engine.enrichment.dexscreener import (
                    compute_liquidity_score as compute_dex_liquidity_score,
                )
                from audit_engine.enrichment.dexscreener import (
                    fetch_liquidity_signals,
                )
                from audit_engine.enrichment.holder_concentration import (
                    compute_concentration_score,
                    fetch_holder_signals,
                )
                from audit_engine.ingestion.solana_metadata import SolanaMetadataFetcher
                from audit_engine.scoring import AXIS_WEIGHTS_TARGET
                from audit_engine.types import ScoreAxis

                meta_result, dex_signals, holder_signals = await asyncio.gather(
                    SolanaMetadataFetcher().fetch(address),
                    fetch_liquidity_signals(address=address, network=self.network),
                    fetch_holder_signals(address=address, network=self.network),
                    return_exceptions=True,
                )

                if isinstance(meta_result, BaseException):
                    log.warning("pipeline.solana_metadata_failed", error=str(meta_result))
                    meta_result = None
                if isinstance(dex_signals, BaseException):
                    log.warning("pipeline.dexscreener_failed", error=str(dex_signals))
                    dex_signals = None
                if isinstance(holder_signals, BaseException):
                    log.warning("pipeline.holder_concentration_failed", error=str(holder_signals))
                    holder_signals = None

                if meta_result is not None:
                    self._report.chain_metadata = meta_result.to_dict()

                chain_meta_updates: dict = {}
                if dex_signals is not None:
                    chain_meta_updates["dex_liquidity"] = dex_signals
                if holder_signals is not None:
                    chain_meta_updates["holder_concentration"] = holder_signals
                if chain_meta_updates:
                    self._report.chain_metadata = {
                        **(self._report.chain_metadata or {}),
                        **chain_meta_updates,
                    }

                dex_liq = await compute_dex_liquidity_score(dex_signals) if dex_signals else None
                holder_sc = compute_concentration_score(holder_signals) if holder_signals else None

                def _activate_sol(axis: ScoreAxis, result: tuple[float, str] | None) -> ScoreAxis:
                    if result is None:
                        return axis
                    score, rationale = result
                    return ScoreAxis(
                        name=axis.name,
                        weight=AXIS_WEIGHTS_TARGET[axis.name],
                        score=score,
                        rationale=rationale,
                    )

                new_axes: list[ScoreAxis] = []
                for axis in self._report.axes:
                    if axis.name == "Liquidity Risk":
                        new_axes.append(_activate_sol(axis, dex_liq))
                    elif axis.name == "Tokenomics / Centralization":
                        new_axes.append(_activate_sol(axis, holder_sc))
                    else:
                        new_axes.append(axis)
                self._report.axes = new_axes

                if any((dex_liq, holder_sc)):
                    self._report = _recompute_weighted_score(self._report)
            except Exception as e:
                log.warning("pipeline.solana_enrichment_failed", error=str(e))
        else:
            # EVM Tokenomics axis: enrich via GoPlus Security. Free public
            # API, no key required at our request volume. The scoring
            # module then promotes the axis from weight=0 to its target
            # weight ON THIS SCAN only — other axes stay pending until
            # they get their own real signal source.
            # Run GoPlus (Tokenomics + Liquidity) and Etherscan
            # creation (On-chain Behavior) in parallel — they're
            # independent network calls.
            import asyncio

            from audit_engine.enrichment.defillama import (
                compute_tvl_score,
                fetch_tvl_signals,
            )
            from audit_engine.enrichment.dexscreener import (
                compute_liquidity_score as compute_dex_liquidity_score,
            )
            from audit_engine.enrichment.dexscreener import (
                fetch_liquidity_signals,
            )
            from audit_engine.enrichment.etherscan_meta import (
                compute_onchain_behavior_score,
                fetch_contract_creation,
            )
            from audit_engine.enrichment.goplus import (
                compute_liquidity_score as compute_goplus_liquidity_score,
            )
            from audit_engine.enrichment.goplus import (
                compute_tokenomics_score,
                fetch_token_security,
            )
            from audit_engine.enrichment.holder_concentration import (
                compute_concentration_score,
                fetch_holder_signals,
            )
            from audit_engine.enrichment.team_kyc import (
                compute_team_kyc_score,
                fetch_team_kyc_signals,
            )
            from audit_engine.scoring import AXIS_WEIGHTS_TARGET
            from audit_engine.types import ScoreAxis

            try:
                # All enrichers are independent network calls — run in parallel.
                # 6 fetchers fire concurrently: GoPlus, Etherscan creation,
                # Team KYC, DeFiLlama TVL, DexScreener liquidity, holder
                # concentration.
                (
                    ts,
                    creation,
                    team_signals,
                    tvl_signals,
                    dex_signals,
                    holder_signals,
                ) = await asyncio.gather(
                    fetch_token_security(address=address, network=self.network),
                    fetch_contract_creation(address=address, network=self.network),
                    fetch_team_kyc_signals(
                        address=address,
                        network=self.network,
                        deployer=None,
                        source_verified=bundle is not None,
                    ),
                    fetch_tvl_signals(address=address, network=self.network),
                    fetch_liquidity_signals(address=address, network=self.network),
                    fetch_holder_signals(address=address, network=self.network),
                    return_exceptions=True,
                )
                if isinstance(ts, BaseException):
                    log.warning("pipeline.goplus_failed", error=str(ts))
                    ts = None
                if isinstance(creation, BaseException):
                    log.warning("pipeline.etherscan_meta_failed", error=str(creation))
                    creation = None
                if isinstance(team_signals, BaseException):
                    log.warning("pipeline.team_kyc_failed", error=str(team_signals))
                    team_signals = None
                if isinstance(tvl_signals, BaseException):
                    log.warning("pipeline.defillama_failed", error=str(tvl_signals))
                    tvl_signals = None
                if isinstance(dex_signals, BaseException):
                    log.warning("pipeline.dexscreener_failed", error=str(dex_signals))
                    dex_signals = None
                if isinstance(holder_signals, BaseException):
                    log.warning("pipeline.holder_concentration_failed", error=str(holder_signals))
                    holder_signals = None

                # If we got the deployer from etherscan_meta, re-run team_kyc
                # and holder_concentration with deployer info (the parallel
                # call above couldn't know it).
                if creation is not None and creation.creator:
                    try:
                        team_signals = await fetch_team_kyc_signals(
                            address=address,
                            network=self.network,
                            deployer=creation.creator,
                            source_verified=bundle is not None,
                        )
                    except Exception as e:
                        log.warning("pipeline.team_kyc_retry_failed", error=str(e))
                    try:
                        holder_signals = await fetch_holder_signals(
                            address=address,
                            network=self.network,
                            deployer_address=creation.creator,
                        )
                    except Exception as e:
                        log.warning("pipeline.holder_retry_failed", error=str(e))

                # --- store raw signals in chain_metadata -----------------
                chain_meta_updates: dict = {}
                if ts is not None:
                    chain_meta_updates["token_security"] = ts.to_dict()
                if creation is not None:
                    chain_meta_updates["contract_creation"] = creation.to_dict()
                if team_signals is not None:
                    chain_meta_updates["team_kyc"] = team_signals.to_dict()
                if tvl_signals is not None:
                    chain_meta_updates["tvl"] = tvl_signals
                if dex_signals is not None:
                    chain_meta_updates["dex_liquidity"] = dex_signals
                if holder_signals is not None:
                    chain_meta_updates["holder_concentration"] = holder_signals
                if chain_meta_updates:
                    self._report.chain_metadata = {
                        **(self._report.chain_metadata or {}),
                        **chain_meta_updates,
                    }

                # --- compute axis scores ---------------------------------
                tk = compute_tokenomics_score(ts) if ts else None

                # Liquidity axis: composite of GoPlus + DexScreener + TVL.
                # Average available sub-scores for a richer signal.
                goplus_liq = compute_goplus_liquidity_score(ts) if ts else None
                dex_liq = await compute_dex_liquidity_score(dex_signals) if dex_signals else None
                tvl_sc = compute_tvl_score(tvl_signals) if tvl_signals else None
                liq = _composite_liquidity(goplus_liq, dex_liq, tvl_sc)

                # Tokenomics axis: composite GoPlus + holder concentration.
                holder_sc = compute_concentration_score(holder_signals) if holder_signals else None
                if tk is not None and holder_sc is not None:
                    # Weighted blend: GoPlus 60%, holder conc 40%.
                    tk_score = tk[0] * 0.6 + holder_sc[0] * 0.4
                    tk = (round(tk_score, 1), f"{tk[1]}; Holders: {holder_sc[1]}")
                elif holder_sc is not None:
                    tk = holder_sc

                onchain = (
                    compute_onchain_behavior_score(creation) if creation else None
                )
                team = (
                    compute_team_kyc_score(team_signals) if team_signals else None
                )

                def _activate(axis: ScoreAxis, result: tuple[float, str] | None) -> ScoreAxis:
                    if result is None:
                        return axis
                    score, rationale = result
                    return ScoreAxis(
                        name=axis.name,
                        weight=AXIS_WEIGHTS_TARGET[axis.name],
                        score=score,
                        rationale=rationale,
                    )

                new_axes: list[ScoreAxis] = []
                for axis in self._report.axes:
                    if axis.name == "Tokenomics / Centralization":
                        new_axes.append(_activate(axis, tk))
                    elif axis.name == "Liquidity Risk":
                        new_axes.append(_activate(axis, liq))
                    elif axis.name == "On-chain Behavior":
                        new_axes.append(_activate(axis, onchain))
                    elif axis.name == "Team / KYC":
                        new_axes.append(_activate(axis, team))
                    else:
                        new_axes.append(axis)
                self._report.axes = new_axes

                if any((tk, liq, onchain, team)):
                    self._report = _recompute_weighted_score(self._report)
            except Exception as e:
                log.warning("pipeline.enrichment_failed", error=str(e))

        yield PipelineEvent(
            stage="done",
            progress=100,
            data={"score": self._report.score, "tier": self._report.tier},
        )

    def result(self) -> dict[str, Any]:
        if self._report is None:
            return {"status": "incomplete"}
        return self._report.model_dump(mode="json")


def _composite_liquidity(
    goplus: tuple[float, str] | None,
    dex: tuple[float, str] | None,
    tvl: tuple[float, str] | None,
) -> tuple[float, str] | None:
    """Merge up to 3 liquidity sub-scores into one axis score.

    Each enricher returns (score, rationale).  We average the available
    scores and concatenate rationales so the user sees the full picture.
    """
    parts: list[tuple[float, str]] = []
    if goplus is not None:
        parts.append(goplus)
    if dex is not None:
        parts.append(dex)
    if tvl is not None:
        parts.append(tvl)
    if not parts:
        return None
    avg = round(sum(p[0] for p in parts) / len(parts), 1)
    rationale = "; ".join(p[1] for p in parts)
    return (avg, rationale)


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
