"""Static analyzers — multi-engine consensus.

Per TZ.md §5.6:
    - Aderyn (Cyfrin, GPL-3) — primary, via CLI subprocess
    - Wake (Ackee, ISC) — secondary, can link as library
    - Slither (ToB, AGPL-3) — fallback for legacy <=0.5

License isolation: all GPL/AGPL tools are invoked via subprocess with clean JSON I/O,
NOT linked as libraries into wr3's proprietary core.
"""

from __future__ import annotations

import anyio
import structlog

from audit_engine.analyzers.aderyn import AderynAnalyzer
from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.analyzers.slither import SlitherAnalyzer
from audit_engine.analyzers.wake import WakeAnalyzer
from audit_engine.types import Finding, Network

logger = structlog.get_logger()


class StaticAnalyzerRegistry:
    """Runs all available static analyzers in parallel and merges findings."""

    @staticmethod
    def for_network(network: Network) -> list[StaticAnalyzer]:
        if network == "solana":
            # TODO: SolanaAnalyzer (custom AST on anchor-syn + Sealevel-attacks rules)
            return []
        return [
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

        return [f for batch in results for f in batch]


__all__ = ["StaticAnalyzer", "StaticAnalyzerRegistry"]
