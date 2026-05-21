"""Static analyzers — multi-engine consensus.

Per TZ.md §5.6:
    - Aderyn (Cyfrin, GPL-3) — primary, via CLI subprocess
    - Wake (Ackee, ISC) — secondary, can link as library
    - Slither (ToB, AGPL-3) — fallback for legacy <=0.5

License isolation: all GPL/AGPL tools are invoked via subprocess with clean JSON I/O,
NOT linked as libraries into wr3's proprietary core.
"""

from __future__ import annotations

from collections import defaultdict

import anyio
import structlog

from audit_engine.analyzers.aderyn import AderynAnalyzer
from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.analyzers.baseline import BaselineAnalyzer
from audit_engine.analyzers.slither import SlitherAnalyzer
from audit_engine.analyzers.solana import SolanaSealevelAnalyzer
from audit_engine.analyzers.wake import WakeAnalyzer
from audit_engine.types import Finding, Network

logger = structlog.get_logger()


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Deduplicate findings produced by multiple engines.

    Two-pass dedup:

    1. **Exact dedup** — group by ``(title.lower().strip(), line)``.  When
       duplicates exist, keep the finding with the highest ``confidence``,
       and merge ``source_engine`` values into ``metadata["engines"]``.

    2. **Title-level rollup** — group surviving findings by
       ``title.lower().strip()``.  If the same pattern appears at multiple
       lines, collapse them into a single representative finding and store
       all affected lines in ``metadata["locations"]``.
    """

    if not findings:
        return []

    # --- Pass 1: exact dedup by (normalised title, line) -------------------
    exact_groups: dict[tuple[str, int | None], list[Finding]] = defaultdict(list)
    for f in findings:
        key = (f.title.lower().strip(), f.line)
        exact_groups[key].append(f)

    deduped: list[Finding] = []
    for group in exact_groups.values():
        # Pick the finding with the highest confidence as the representative.
        group.sort(key=lambda f: f.confidence, reverse=True)
        best = group[0].model_copy(deep=True)

        # Collect all unique engine names that reported this finding.
        engines = list(dict.fromkeys(f.source_engine for f in group))
        best.metadata["engines"] = engines
        deduped.append(best)

    # --- Pass 2: title-level rollup across different lines -----------------
    title_groups: dict[str, list[Finding]] = defaultdict(list)
    for f in deduped:
        title_groups[f.title.lower().strip()].append(f)

    result: list[Finding] = []
    for group in title_groups.values():
        # Pick the representative with the highest confidence.
        group.sort(key=lambda f: f.confidence, reverse=True)
        best = group[0].model_copy(deep=True)

        # Collect all unique lines where the issue was detected.
        locations = list(dict.fromkeys(f.line for f in group if f.line is not None))
        if locations:
            best.metadata["locations"] = sorted(locations)

        # Merge engine lists from all rolled-up findings.
        all_engines: list[str] = []
        for f in group:
            all_engines.extend(f.metadata.get("engines", [f.source_engine]))
        best.metadata["engines"] = list(dict.fromkeys(all_engines))

        result.append(best)

    before, after = len(findings), len(result)
    if before != after:
        logger.info("dedup.done", before=before, after=after, removed=before - after)

    return result


class StaticAnalyzerRegistry:
    """Runs all available static analyzers in parallel and merges findings."""

    @staticmethod
    def for_network(network: Network) -> list[StaticAnalyzer]:
        if network == "solana":
            # Solana track: regex-based Sealevel-attacks analyzer is the only
            # in-house engine for now. Trident fuzz (W6 wrapper) handles
            # invariants; symbolic exec / Certora-Solana wiring is W12+.
            return [SolanaSealevelAnalyzer()]
        # Baseline first: in-process, no deps, fast.
        # Aderyn/Wake/Slither will silently skip if their binaries aren't installed.
        return [
            BaselineAnalyzer(),
            AderynAnalyzer(),
            WakeAnalyzer(),
            SlitherAnalyzer(),
        ]

    @staticmethod
    async def run_all(*, source: str, network: Network) -> list[Finding]:
        analyzers = StaticAnalyzerRegistry.for_network(network)
        if not analyzers:
            logger.warning("static.no_analyzers", network=network)
            return []

        results: list[list[Finding]] = []

        async def _run(a: StaticAnalyzer) -> None:
            try:
                findings = await a.analyze(source=source)
                results.append(findings)
                logger.info("static.done", engine=a.name, count=len(findings))
            except Exception as e:
                logger.exception("static.failed", engine=a.name, error=str(e))
                results.append([])

        async with anyio.create_task_group() as tg:
            for a in analyzers:
                tg.start_soon(_run, a)

        flat = [f for batch in results for f in batch]
        return deduplicate_findings(flat)


__all__ = ["StaticAnalyzer", "StaticAnalyzerRegistry", "deduplicate_findings"]
