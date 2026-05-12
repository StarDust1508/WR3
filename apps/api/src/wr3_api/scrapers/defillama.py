"""DefiLlama Hacks API scraper — https://api.llama.fi/hacks

DefiLlama publishes a curated, machine-readable list of every DeFi hack
since 2020, with structured fields (date, name, technique, amount, chain).
This is the highest-signal source we have: no HTML scraping, no narrative
guessing — the loss_usd and chain are first-class.

We cap how far back we look (default 90 days) to keep the dataset focused
on what's relevant for current scans. Historical hacks can be a separate
W12 ingest into a vector store for similarity search.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog

from wr3_api.scrapers.shared import ScrapedIncident

logger = structlog.get_logger()

DEFILLAMA_HACKS_URL = "https://api.llama.fi/hacks"


def _format_summary(record: dict[str, Any]) -> str:
    """Compose a human-readable summary from DefiLlama's structured fields."""
    parts: list[str] = []
    if amount := record.get("amount"):
        try:
            usd = int(amount)
            parts.append(f"Loss: ${usd:,}")
        except (TypeError, ValueError):
            pass
    if tech := record.get("technique"):
        parts.append(f"Technique: {tech}")
    if classification := record.get("classification"):
        parts.append(f"Classification: {classification}")
    if chains := record.get("chain"):
        if isinstance(chains, list) and chains:
            parts.append(f"Chain: {', '.join(chains)}")
    if target := record.get("targetType"):
        parts.append(f"Target: {target}")
    return ". ".join(parts)


async def scrape_defillama_hacks(
    *,
    timeout: float = 30.0,
    since_days: int = 90,
) -> list[ScrapedIncident]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(DEFILLAMA_HACKS_URL)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        logger.warning("scraper.defillama.fetch_failed", error=str(e))
        return []

    if not isinstance(data, list):
        logger.warning("scraper.defillama.bad_shape", got=type(data).__name__)
        return []

    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    out: list[ScrapedIncident] = []

    for r in data:
        if not isinstance(r, dict):
            continue
        name = r.get("name")
        date_ts = r.get("date")
        if not name or not isinstance(date_ts, int):
            continue
        published_at = datetime.fromtimestamp(date_ts, tz=UTC)
        if published_at < cutoff:
            continue

        # DefiLlama records may have an empty `source` URL; in that case we
        # fall back to a deterministic canonical link to their own page.
        url = r.get("source") or f"https://defillama.com/hack/{name}"

        amount = r.get("amount")
        loss_usd: int | None
        try:
            loss_usd = int(amount) if amount is not None else None
        except (TypeError, ValueError):
            loss_usd = None

        out.append(
            ScrapedIncident(
                title=str(name),
                summary=_format_summary(r),
                url=url,
                source="defillama",
                published_at=published_at,
                loss_usd=loss_usd,
                raw=r,
            )
        )

    out.sort(key=lambda x: x.published_at, reverse=True)
    logger.info("scraper.defillama.parsed", count=len(out), since_days=since_days)
    return out
