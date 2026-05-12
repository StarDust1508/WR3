"""Security incident — one row per real-world exploit report.

Ingested from public sources (Rekt News, SlowMist, DefiLlama Hacks). The
`embedding` column holds a 1536-dim vector from api.navy
text-embedding-3-small over `title + summary`; dedup uses cosine distance.

Two incidents from different sources describing the same hack (e.g. Rekt
post + SlowMist incident report on the Curve/Vyper exploit) collapse to
one canonical row. We keep the EARLIEST `published_at` and append any
additional source URLs into `extra_urls`.

The schema intentionally has no FK to scans — incidents are a separate
domain object. Linking specific findings to historical exploits is a W12
job.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wr3_api.models.base import Base, TimestampMixin

# Must match api.navy text-embedding-3-small output dimension.
# If we switch models (e.g. to -large at 3072), this constant and the
# migration's IVFFlat index need to change in lockstep.
EMBEDDING_DIM = 1536

# Cosine similarity threshold for "same incident", calibrated against real
# text-embedding-3-small output on actual Rekt vs DefiLlama pairs:
#   > 0.80 — same hack, near-identical wording (rare across sources)
#   0.65–0.80 — same hack, different framing (Rekt narrative vs DefiLlama
#                structured) — the actual cross-source dedup case
#   0.45–0.65 — same category, different protocols (false-positive zone)
#   < 0.45 — unrelated
# We chose 0.65 because the observed gap between "same event" (~0.66-0.72)
# and "different event, same category" (~0.47) is wide enough to set the
# bar there without expecting false positives.
DEDUP_COSINE_THRESHOLD = 0.65


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Source URL where this incident was first observed. Additional URLs
    # for the same canonical incident go into extra_urls during dedup.
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)  # "rekt" | "slowmist" | "defillama"

    extra_urls: Mapped[list[str]] = mapped_column(
        ARRAY(String(1024)), nullable=False, server_default=text("'{}'::varchar[]")
    )
    extra_sources: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), nullable=False, server_default=text("'{}'::varchar[]")
    )

    # When the source published the post, not when we scraped it.
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Best-effort loss in USD (DefiLlama provides this; Rekt usually in title).
    loss_usd: Mapped[int | None] = mapped_column(nullable=True)

    # Embedding of (title + summary), used for dedup. NULL until first scrape
    # of an entry that couldn't reach api.navy — we backfill on retry.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )

    # Raw source row (RSS entry / API record) for debugging. Never read by
    # business code.
    raw: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        # We can have multiple records with the same URL during a race
        # between two workers; the repo handles this. But within a single
        # canonical incident, URL is unique-ish. Don't make this UNIQUE —
        # it kills the upsert-by-similarity path.
        Index("ix_incidents_published_at", "published_at"),
        Index("ix_incidents_source", "source"),
        Index("ix_incidents_url", "url"),
    )
