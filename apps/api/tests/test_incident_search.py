"""Unit tests for the incident-search enrichment.

We mock the DB layer (`find_similar_incidents`) and the embedder so the
test is pure-Python, in line with the rest of the api suite. The live
e2e check is documented in the W12 commit: real USDC scan, `tx.origin`
finding matched a real SlowMist post via api.navy + pgvector.

Coverage:
  - Only HIGH/CRITICAL active findings get enriched (per ENRICHABLE_SEVERITIES)
  - Embed batching is invoked ONCE with the right texts
  - `metadata.similar_incidents` is populated in-place
  - The `metadata={}` empty-dict edge case (previously a bug — falsy
    short-circuit) is regressed
  - Embed failure is non-fatal: stats report it, scan still proceeds
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from wr3_api.models import Incident
from wr3_api.services import incident_search


def _incident(title: str, source: str = "rekt", loss: int | None = None) -> Incident:
    i = Incident()
    i.id = uuid.uuid4()
    i.title = title
    i.summary = ""
    i.url = f"https://example.com/{title.lower().replace(' ', '-')}"
    i.source = source
    i.extra_urls = []
    i.extra_sources = []
    i.published_at = datetime(2026, 4, 1, tzinfo=UTC)
    i.loss_usd = loss
    i.embedding = None  # not used by the mock
    return i


def _finding(severity: str, title: str = "Some bug", **overrides) -> dict:
    base = {
        "id": str(uuid.uuid4()),
        "title": title,
        "description": "Some technical description.",
        "severity": severity,
        "dismissed": False,
        "metadata": {},
    }
    base.update(overrides)
    return base


def _make_embed_batch(call_log: list):
    async def stub(texts: list[str]) -> list[list[float]]:
        call_log.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]
    return stub


@pytest.fixture
def fake_find_similar(monkeypatch):
    """Patch find_similar_incidents to return a single match per call."""
    inc = _incident("Kelp", source="defillama", loss=293_000_000)

    async def stub(embedding, *, threshold=None, limit=None):
        return [(inc, 0.55)]

    monkeypatch.setattr(incident_search, "find_similar_incidents", stub)
    return inc


async def test_enrich_only_high_critical(fake_find_similar) -> None:
    call_log: list[list[str]] = []
    report = {
        "findings": [
            _finding("critical", "Reentrancy"),
            _finding("high", "Oracle manipulation"),
            _finding("medium", "Missing zero check"),  # skipped
            _finding("low", "Floating pragma"),         # skipped
            _finding("info", "Style nit"),              # skipped
        ]
    }
    stats = await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=_make_embed_batch(call_log)
    )
    assert stats["enrichable"] == 2
    assert stats["matched"] == 2
    # Only the 2 high/critical texts went to the embedder
    assert len(call_log) == 1
    assert len(call_log[0]) == 2

    # The high/critical findings got similar_incidents populated
    enriched_titles = [f["title"] for f in report["findings"]
                       if f.get("metadata", {}).get("similar_incidents")]
    assert sorted(enriched_titles) == ["Oracle manipulation", "Reentrancy"]


async def test_enrich_skips_dismissed(fake_find_similar) -> None:
    call_log: list[list[str]] = []
    report = {
        "findings": [
            _finding("critical", "Real bug", dismissed=False),
            _finding("critical", "False positive", dismissed=True),
        ]
    }
    await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=_make_embed_batch(call_log)
    )
    assert len(call_log[0]) == 1  # only the non-dismissed one was embedded


async def test_enrich_handles_empty_metadata_dict_regression(fake_find_similar) -> None:
    """Regression: `metadata.setdefault('metadata', {}) or {}` short-circuited
    when metadata was already `{}` (falsy), causing the mutation to write to
    a throwaway dict and never appear in the report.
    """
    call_log: list[list[str]] = []
    report = {"findings": [_finding("critical", "Bug", metadata={})]}
    await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=_make_embed_batch(call_log)
    )
    sims = report["findings"][0]["metadata"]["similar_incidents"]
    assert len(sims) == 1
    assert sims[0]["title"] == "Kelp"


async def test_enrich_handles_none_metadata(fake_find_similar) -> None:
    """If upstream serialized metadata as None, we must still populate it."""
    call_log: list[list[str]] = []
    report = {"findings": [_finding("critical", "Bug", metadata=None)]}
    await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=_make_embed_batch(call_log)
    )
    sims = report["findings"][0]["metadata"]["similar_incidents"]
    assert len(sims) == 1


async def test_enrich_embed_failure_is_nonfatal(monkeypatch) -> None:
    async def boom(_texts):
        raise RuntimeError("api.navy down")

    inc = _incident("Foo")
    async def find_stub(*_, **__): return [(inc, 0.55)]
    monkeypatch.setattr(incident_search, "find_similar_incidents", find_stub)

    report = {"findings": [_finding("critical", "Bug")]}
    stats = await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=boom
    )
    assert stats["embed_failed"] == 1
    # No matches were written
    assert "similar_incidents" not in (report["findings"][0].get("metadata") or {})


async def test_enrich_no_targets_returns_zero(monkeypatch) -> None:
    """A scan with only LOW/INFO findings should NOT call the embedder."""
    called = {"n": 0}
    async def boom(_texts):
        called["n"] += 1
        return []
    report = {"findings": [_finding("info", "x"), _finding("low", "y")]}
    stats = await incident_search.enrich_report_with_similar_incidents(
        report, embed_batch=boom
    )
    assert stats == {"enrichable": 0, "matched": 0, "embed_failed": 0}
    assert called["n"] == 0


def test_serialize_match_shape() -> None:
    inc = _incident("Curve", source="rekt", loss=61_000_000)
    out = incident_search.serialize_match(inc, 0.6534)
    assert out["incident_id"] == str(inc.id)
    assert out["title"] == "Curve"
    assert out["source"] == "rekt"
    assert out["loss_usd"] == 61_000_000
    assert out["similarity"] == 0.653  # rounded to 3 places
    assert out["url"].startswith("https://example.com/")


def test_build_query_text_truncates_description() -> None:
    long_desc = "x" * 2000
    f = _finding("high", "Title", description=long_desc)
    text = incident_search._build_query_text(f)
    # severity prefix + title + \n\n + first 600 chars of description
    assert text.startswith("high-severity smart contract vulnerability. Title\n\n")
    # Body capped at 600 even when description is huge.
    body_start = text.index("Title\n\n") + len("Title\n\n")
    assert len(text[body_start:]) <= 600


def test_build_query_text_includes_severity_prefix() -> None:
    """Empirically, this prefix lifts recall by a few points. Lock it in."""
    f = _finding("critical", "Reentrancy", description="x")
    text = incident_search._build_query_text(f)
    assert text.startswith("critical-severity smart contract vulnerability.")


def test_build_query_text_no_severity_omits_prefix() -> None:
    """Defensive: a finding without severity (shouldn't happen in practice)
    must not produce a bare 'unknown-severity ...' prefix."""
    f = {"title": "X", "description": "y", "severity": ""}
    text = incident_search._build_query_text(f)
    assert "severity" not in text.lower().split(".")[0]
