"""Shared types + helpers for incident scrapers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScrapedIncident:
    """A scraped incident BEFORE dedup + embedding.

    `source` is a short stable key ("rekt" / "slowmist" / "defillama"),
    not a human label. UI strings come from a separate mapping.
    """

    title: str
    summary: str
    url: str
    source: str
    published_at: datetime
    loss_usd: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# Strip HTML quickly. We do NOT parse HTML — incident summaries are short
# and we just want a plain-text snippet for the embedding + UI. The regex
# approach is intentional: pulling beautifulsoup in for 5 lines of cleanup
# would bloat the API image for no win.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None, *, max_len: int = 800) -> str:
    if not text:
        return ""
    s = _TAG_RE.sub(" ", text)
    s = _WS_RE.sub(" ", s).strip()
    return s[:max_len]
