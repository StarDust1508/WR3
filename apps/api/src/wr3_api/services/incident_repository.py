"""Incident persistence with embedding-based dedup.

Public surface:
    ingest_one(scraped, embedder)   — embed + upsert one ScrapedIncident
    list_recent(limit, days)        — public read for the feed widget

Dedup contract:
    Given a scraped incident with embedding `e`, we cosine-similarity-match
    against the most recent N incidents (N=200 — enough to cover any
    duplicate that arrives within ~weeks of the original). If best match's
    similarity >= DEDUP_COSINE_THRESHOLD AND its source != ours, we treat
    this as the same canonical incident and merge:
       - keep the EARLIER published_at (the original)
       - append our URL/source to extra_urls/extra_sources
       - prefer DefiLlama's structured loss_usd over Rekt's regex-guessed one
    Otherwise we insert a new row.

We embed BEFORE dedup, never after — embedding is required for the check.
If embed() fails, we still write the row (with embedding=NULL) so the data
isn't lost; a refresh job can backfill later.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import select, update

from wr3_api.db import SessionFactory
from wr3_api.models import Incident
from wr3_api.models.incident import DEDUP_COSINE_THRESHOLD
from wr3_api.scrapers import ScrapedIncident

logger = structlog.get_logger()

# Embedding function signature so callers can inject a mock in tests.
Embedder = Callable[[str], Awaitable[list[float]]]

# How many recent rows to scan for dedup. Empirically: cross-source
# duplicates for the same hack arrive within ~3 days of each other; 200
# rows = roughly 2 months of feed activity, plenty of headroom.
DEDUP_SCAN_LIMIT = 200


def _embed_text(scraped: ScrapedIncident) -> str:
    """Text we feed to the embedding model.

    Title is high-signal, summary disambiguates. Truncate summary so we
    don't burn tokens on Rekt's marketing footers.
    """
    return f"{scraped.title}\n\n{scraped.summary[:600]}"


async def ingest_one(
    scraped: ScrapedIncident,
    embedder: Embedder | None,
) -> tuple[Incident, bool]:
    """Persist one scraped incident. Returns (row, was_inserted).

    `was_inserted=False` means we merged into an existing canonical
    incident — the returned `row` is the canonical one, mutated to include
    our source.
    """
    # 1) embed (best effort — None is OK, we recover later)
    embedding: list[float] | None = None
    if embedder is not None:
        try:
            embedding = await embedder(_embed_text(scraped))
        except Exception as e:
            logger.warning(
                "incident.embed_failed",
                title=scraped.title[:80],
                error=str(e),
            )

    async with SessionFactory() as session:
        # 2) URL exact-match short-circuit. Cheaper than vector search and
        # catches the most common case: same feed scraped twice.
        existing_by_url = (
            await session.execute(
                select(Incident).where(Incident.url == scraped.url).limit(1)
            )
        ).scalar_one_or_none()
        if existing_by_url is not None:
            # If we now have an embedding but the existing row didn't, backfill it.
            changed = False
            if embedding is not None and existing_by_url.embedding is None:
                existing_by_url.embedding = embedding
                changed = True
            if changed:
                await session.commit()
                await session.refresh(existing_by_url)
            return existing_by_url, False

        # 3) vector similarity search — only if we have an embedding
        canonical: Incident | None = None
        if embedding is not None:
            # `embedding <=> :q` is cosine distance (0 = identical, 2 = opposite).
            # We compute 1 - distance to get similarity.
            q = (
                select(
                    Incident,
                    (1 - Incident.embedding.cosine_distance(embedding)).label("sim"),
                )
                .where(Incident.embedding.isnot(None))
                .order_by(Incident.embedding.cosine_distance(embedding))
                .limit(DEDUP_SCAN_LIMIT)
            )
            rows = (await session.execute(q)).all()
            for row, sim in rows:
                if sim >= DEDUP_COSINE_THRESHOLD and row.source != scraped.source:
                    canonical = row
                    break
                # First miss is enough — results are sorted by distance ascending.
                # Anything past the first row will only be less similar.
                break

        if canonical is not None:
            _merge_into_canonical(canonical, scraped)
            await session.commit()
            await session.refresh(canonical)
            logger.info(
                "incident.deduped",
                canonical_id=str(canonical.id),
                merged_source=scraped.source,
                title=scraped.title[:80],
            )
            return canonical, False

        # 4) brand-new incident
        row = Incident(
            title=scraped.title[:512],
            summary=scraped.summary,
            url=scraped.url,
            source=scraped.source,
            published_at=scraped.published_at,
            loss_usd=scraped.loss_usd,
            embedding=embedding,
            raw=scraped.raw,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        logger.info(
            "incident.inserted",
            id=str(row.id),
            source=scraped.source,
            title=scraped.title[:80],
        )
        return row, True


def _merge_into_canonical(canonical: Incident, scraped: ScrapedIncident) -> None:
    """Mutate `canonical` in place to record a cross-source observation."""
    if scraped.url not in canonical.extra_urls and scraped.url != canonical.url:
        canonical.extra_urls = [*canonical.extra_urls, scraped.url]
    if scraped.source not in canonical.extra_sources and scraped.source != canonical.source:
        canonical.extra_sources = [*canonical.extra_sources, scraped.source]
    # DefiLlama loss is structured; trust it over a Rekt regex guess.
    if scraped.source == "defillama" and scraped.loss_usd is not None:
        canonical.loss_usd = scraped.loss_usd
    elif canonical.loss_usd is None and scraped.loss_usd is not None:
        canonical.loss_usd = scraped.loss_usd
    # Keep the EARLIEST published_at — the "first observed" date.
    if scraped.published_at < canonical.published_at:
        canonical.published_at = scraped.published_at


async def list_recent(
    *,
    limit: int = 20,
    max_age_days: int = 60,
) -> list[Incident]:
    """Most-recent incidents by published_at, capped by age."""
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    async with SessionFactory() as session:
        q = (
            select(Incident)
            .where(Incident.published_at >= cutoff)
            .order_by(Incident.published_at.desc())
            .limit(limit)
        )
        return list((await session.execute(q)).scalars().all())


async def count_total() -> int:
    """Total incident count (for stats widgets)."""
    from sqlalchemy import func

    async with SessionFactory() as session:
        return int(
            (await session.execute(select(func.count(Incident.id)))).scalar_one()
        )


def incident_to_dict(inc: Incident) -> dict[str, Any]:
    return {
        "id": str(inc.id),
        "title": inc.title,
        "summary": inc.summary,
        "url": inc.url,
        "source": inc.source,
        "extra_sources": list(inc.extra_sources or []),
        "extra_urls": list(inc.extra_urls or []),
        "published_at": inc.published_at.isoformat(),
        "loss_usd": inc.loss_usd,
    }
