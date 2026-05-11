"""Multi-agent triage. STUB — wires real LLM calls in W3-W5 per TZ.md plan."""

from __future__ import annotations

import structlog

from audit_engine.llm import LLMRouter
from audit_engine.types import Finding

logger = structlog.get_logger()


class TriageOrchestrator:
    """Runs 4 parallel agents over raw findings and reaches consensus.

    Stage 3 of the pipeline (TZ.md §4.1).
    """

    def __init__(self, llm: LLMRouter | None = None) -> None:
        self.llm = llm or LLMRouter()

    async def run(self, findings: list[Finding], *, source: str) -> list[Finding]:
        # TODO W5 — implement 4 agents in parallel:
        #   - severity classifier (re-ranks)
        #   - false positive filter (dismisses)
        #   - business logic reasoner (adds new findings AI catches but static missed)
        #   - cross-contract analyzer (proxies, delegatecalls)
        # then consensus pass that emits final ranked list.
        logger.info("triage.stub", count=len(findings))
        return findings
