"""Periodic incident-feed refresh worker.

In dev (CELERY_TASK_ALWAYS_EAGER=1) call `refresh_incidents.delay()` from a
script or test to run immediately. In prod, schedule via celery beat — see
NEXT_STEPS in repo root.

This task is deliberately self-contained: it spins up its own LLMRouter and
embedder closure rather than reaching into the audit pipeline's globals. We
want the news scraper to fail independently of audit infrastructure.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

import structlog

from audit_engine.llm.router import LLMRouter
from wr3_api.scrapers import (
    ScrapedIncident,
    scrape_defillama_hacks,
    scrape_rekt,
    scrape_slowmist,
)
from wr3_api.services import incident_repository as inc_repo
from wr3_api.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _run_refresh() -> dict[str, int]:
    """Pull all sources, embed, dedup-insert. Returns per-source counters."""
    router = LLMRouter()  # picks up NAVYAI_* from env

    async def embed(text: str) -> list[float]:
        return await router.embed(text)

    # Run all three scrapers in parallel — they're independent network calls.
    results = await asyncio.gather(
        scrape_rekt(),
        scrape_slowmist(),
        scrape_defillama_hacks(since_days=90),
        return_exceptions=True,
    )

    rekt, slowmist, defillama = (_unwrap(r) for r in results)

    stats = {
        "rekt_scraped": len(rekt),
        "slowmist_scraped": len(slowmist),
        "defillama_scraped": len(defillama),
        "inserted": 0,
        "deduped": 0,
        "embed_failed": 0,
    }

    # Process sources in canonical-priority order. DefiLlama is structured,
    # so we insert it first — Rekt/SlowMist that arrive afterwards will dedup
    # AGAINST DefiLlama and inherit its accurate loss_usd via _merge_into_canonical.
    for scraped in _chain(defillama, rekt, slowmist):
        try:
            _, inserted = await inc_repo.ingest_one(scraped, embed)
            if inserted:
                stats["inserted"] += 1
            else:
                stats["deduped"] += 1
        except Exception as e:
            logger.warning(
                "incident.ingest_failed",
                title=scraped.title[:80],
                source=scraped.source,
                error=str(e),
            )

    logger.info("incident.refresh_done", **stats)
    return stats


def _unwrap(r: list[ScrapedIncident] | BaseException) -> list[ScrapedIncident]:
    if isinstance(r, BaseException):
        logger.warning("scraper.failed", error=str(r))
        return []
    return r


def _chain(*iters: Iterable[ScrapedIncident]) -> Iterable[ScrapedIncident]:
    for it in iters:
        yield from it


@celery_app.task(
    bind=True,
    name="wr3_api.workers.incident_worker.refresh_incidents",
    max_retries=1,
)
def refresh_incidents(self) -> dict[str, int]:  # noqa: ARG001 - bound task
    """Celery entry point. Returns counters dict for the result backend."""
    return asyncio.run(_run_refresh())
