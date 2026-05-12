"""SlowMist Medium RSS scraper — https://slowmist.medium.com/feed

SlowMist is a security firm; their Medium feed mixes incident write-ups
with general security commentary. We don't try to filter by category here
— the dedup step will silently fold near-duplicates of Rekt posts, and
genuinely off-topic posts (e.g. recruiting) will just appear once and
that's acceptable for an MVP feed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from wr3_api.scrapers.shared import ScrapedIncident, strip_html

logger = structlog.get_logger()

SLOWMIST_FEED_URL = "https://slowmist.medium.com/feed"


async def scrape_slowmist(*, timeout: float = 15.0) -> list[ScrapedIncident]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(SLOWMIST_FEED_URL)
            r.raise_for_status()
            body = r.text
    except httpx.HTTPError as e:
        logger.warning("scraper.slowmist.fetch_failed", error=str(e))
        return []

    feed = feedparser.parse(body)
    out: list[ScrapedIncident] = []
    for entry in feed.entries:
        title = strip_html(getattr(entry, "title", ""), max_len=256)
        link = getattr(entry, "link", "")
        if not title or not link:
            continue

        pub = getattr(entry, "published_parsed", None)
        if pub:
            published_at = datetime(*pub[:6], tzinfo=UTC)
        else:
            published_at = datetime.now(UTC)

        summary_html = (
            getattr(entry, "summary", "")
            or (getattr(entry, "content", [{}])[0].get("value") if hasattr(entry, "content") else "")
        )
        summary = strip_html(summary_html, max_len=800)

        out.append(
            ScrapedIncident(
                title=title,
                summary=summary,
                url=link,
                source="slowmist",
                published_at=published_at,
                loss_usd=None,
                raw={"feed_entry": dict(entry)},
            )
        )

    logger.info("scraper.slowmist.parsed", count=len(out))
    return out
