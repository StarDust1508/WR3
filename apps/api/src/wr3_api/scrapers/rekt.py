"""Rekt News RSS scraper — https://rekt.news/rss/feed.xml

Rekt is the canonical narrative source for major DeFi exploits. Their RSS
has full HTML body in `<content:encoded>` plus a clean `<title>` and
`<pubDate>`. We pull just the title + lead paragraph for the embedding,
and store the full body in `raw` for debugging.

Loss extraction: Rekt almost always includes the USD figure in the title
(e.g. "Curve Finance - REKT" -> body, "Cypher Protocol - REKT - $1m"). We
do best-effort regex on the title; missing values are honest NULL, not 0.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from wr3_api.scrapers.shared import ScrapedIncident, strip_html

logger = structlog.get_logger()

REKT_FEED_URL = "https://rekt.news/rss/feed.xml"

# Matches "$1.2m", "$340k", "$61M", "$500,000", "$1.2 billion" etc.
_LOSS_RE = re.compile(
    r"\$([\d,]+(?:\.\d+)?)\s*([kmb]|million|billion|thousand)?",
    re.IGNORECASE,
)


def _parse_loss(text: str) -> int | None:
    """Best-effort extract a USD loss figure as integer dollars.

    Returns None when we can't be confident — better NULL than wrong.
    """
    m = _LOSS_RE.search(text)
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = (m.group(2) or "").lower()
    multiplier = {
        "": 1,
        "k": 1_000, "thousand": 1_000,
        "m": 1_000_000, "million": 1_000_000,
        "b": 1_000_000_000, "billion": 1_000_000_000,
    }.get(unit, 1)
    return int(n * multiplier)


async def _fetch(url: str, *, timeout: float) -> str:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.text


async def scrape_rekt(*, timeout: float = 15.0) -> list[ScrapedIncident]:
    """Fetch + parse Rekt RSS. No side effects."""
    try:
        body = await _fetch(REKT_FEED_URL, timeout=timeout)
    except httpx.HTTPError as e:
        logger.warning("scraper.rekt.fetch_failed", error=str(e))
        return []

    feed = feedparser.parse(body)
    out: list[ScrapedIncident] = []
    for entry in feed.entries:
        title = strip_html(getattr(entry, "title", ""), max_len=256)
        if not title:
            continue
        link = getattr(entry, "link", "")
        if not link:
            continue

        # feedparser fills `published_parsed` as a time.struct_time in UTC
        # when the source provides RFC822 dates (Rekt does).
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

        loss = _parse_loss(title) or _parse_loss(summary[:300])

        out.append(
            ScrapedIncident(
                title=title,
                summary=summary,
                url=link,
                source="rekt",
                published_at=published_at,
                loss_usd=loss,
                raw={"feed_entry": dict(entry)},
            )
        )

    logger.info("scraper.rekt.parsed", count=len(out))
    return out
