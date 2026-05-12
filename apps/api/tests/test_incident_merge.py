"""Unit tests for _merge_into_canonical — pure in-memory logic.

The actual end-to-end dedup (embedding → similarity → merge) requires the
DB and api.navy network call; it's covered by the live-data sanity check
documented in the W11 commit message. Here we lock in the in-memory merge
semantics so they can't drift.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from wr3_api.models import Incident
from wr3_api.scrapers.shared import ScrapedIncident
from wr3_api.services.incident_repository import _merge_into_canonical


def _canonical(**overrides):
    base = Incident()
    base.title = "Kelp"
    base.summary = "Loss: $293,000,000. Technique: Compromised private key."
    base.url = "https://defillama.com/hack/Kelp"
    base.source = "defillama"
    base.extra_urls = []
    base.extra_sources = []
    base.published_at = datetime(2026, 4, 18, tzinfo=UTC)
    base.loss_usd = 293_000_000
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _scraped(**overrides):
    defaults = {
        "title": "Kelp Protocol REKT - $293M",
        "summary": "Kelp restaking exploit",
        "url": "https://rekt.news/kelp",
        "source": "rekt",
        "published_at": datetime(2026, 4, 19, tzinfo=UTC),
        "loss_usd": None,
        "raw": {},
    }
    defaults.update(overrides)
    return ScrapedIncident(**defaults)


def test_merge_appends_cross_source_url_and_source() -> None:
    c = _canonical()
    _merge_into_canonical(c, _scraped())
    assert c.extra_urls == ["https://rekt.news/kelp"]
    assert c.extra_sources == ["rekt"]


def test_merge_keeps_earliest_published_at() -> None:
    c = _canonical(published_at=datetime(2026, 4, 18, tzinfo=UTC))
    _merge_into_canonical(c, _scraped(published_at=datetime(2026, 4, 19, tzinfo=UTC)))
    # canonical was earlier → unchanged
    assert c.published_at == datetime(2026, 4, 18, tzinfo=UTC)


def test_merge_replaces_published_at_when_scraped_is_earlier() -> None:
    c = _canonical(published_at=datetime(2026, 4, 20, tzinfo=UTC))
    _merge_into_canonical(c, _scraped(published_at=datetime(2026, 4, 18, tzinfo=UTC)))
    assert c.published_at == datetime(2026, 4, 18, tzinfo=UTC)


def test_merge_prefers_defillama_loss_when_available() -> None:
    """A later DefiLlama observation must overwrite a Rekt regex guess."""
    c = _canonical(loss_usd=290_000_000, source="rekt")  # rekt guess
    _merge_into_canonical(c, _scraped(source="defillama", loss_usd=293_000_000))
    assert c.loss_usd == 293_000_000


def test_merge_backfills_missing_loss() -> None:
    c = _canonical(loss_usd=None)
    _merge_into_canonical(c, _scraped(loss_usd=5_000_000))
    assert c.loss_usd == 5_000_000


def test_merge_does_not_duplicate_same_source() -> None:
    """If we already merged Rekt once, re-merging same Rekt URL is a no-op."""
    c = _canonical()
    c.extra_urls = ["https://rekt.news/kelp"]
    c.extra_sources = ["rekt"]
    _merge_into_canonical(c, _scraped())
    assert c.extra_urls == ["https://rekt.news/kelp"]
    assert c.extra_sources == ["rekt"]


def test_merge_does_not_add_canonical_url_to_extras() -> None:
    """Scraped URL == canonical URL must not be re-added."""
    c = _canonical()
    _merge_into_canonical(c, _scraped(url=c.url, source="rekt"))
    assert c.extra_urls == []
    # Source is still added (different rail observed the same canonical URL)
    assert c.extra_sources == ["rekt"]


def test_merge_ignores_old_published_at_within_a_minute() -> None:
    """We use strict < to avoid jitter from RSS times near each other."""
    base = datetime(2026, 4, 18, tzinfo=UTC)
    c = _canonical(published_at=base)
    _merge_into_canonical(c, _scraped(published_at=base + timedelta(seconds=30)))
    assert c.published_at == base
