"""Scraper unit tests against a recorded Rekt RSS fixture.

We do NOT hit the network in tests — the fixture in tests/fixtures/rekt_feed.xml
is a real snapshot. Re-record it (`curl https://rekt.news/rss/feed.xml`) if
the source structure changes.

DefiLlama is tested separately with a synthesized JSON payload because its
real response is 500KB+ and not worth committing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import respx

from wr3_api.scrapers.defillama import (
    DEFILLAMA_HACKS_URL,
    scrape_defillama_hacks,
)
from wr3_api.scrapers.rekt import REKT_FEED_URL, _parse_loss, scrape_rekt
from wr3_api.scrapers.shared import strip_html

FIXTURE = Path(__file__).parent / "fixtures" / "rekt_feed.xml"


def test_parse_loss_thousands() -> None:
    assert _parse_loss("Foo - $340k") == 340_000


def test_parse_loss_millions_abbr() -> None:
    assert _parse_loss("Curve REKT - $61m") == 61_000_000


def test_parse_loss_billions_word() -> None:
    assert _parse_loss("Hack of $1.2 billion") == 1_200_000_000


def test_parse_loss_comma_thousands() -> None:
    assert _parse_loss("$1,234,567 stolen") == 1_234_567


def test_parse_loss_no_match() -> None:
    assert _parse_loss("no dollars here") is None


def test_strip_html_removes_tags_and_collapses() -> None:
    s = strip_html("<p>hello   <b>world</b></p>  <br>foo")
    assert s == "hello world foo"


def test_strip_html_handles_empty() -> None:
    assert strip_html(None) == ""
    assert strip_html("") == ""


def test_strip_html_truncates() -> None:
    s = strip_html("a" * 1000, max_len=50)
    assert len(s) == 50


async def test_rekt_parses_recorded_feed() -> None:
    """Real Rekt RSS fixture must round-trip to >=1 ScrapedIncident."""
    body = FIXTURE.read_text()
    with respx.mock:
        respx.get(REKT_FEED_URL).mock(
            return_value=httpx.Response(200, text=body, headers={"content-type": "application/rss+xml"})
        )
        incidents = await scrape_rekt()

    assert len(incidents) >= 1
    first = incidents[0]
    assert first.source == "rekt"
    assert first.title
    assert "rekt.news/" in first.url
    assert first.published_at.tzinfo is not None  # must be timezone-aware


async def test_rekt_handles_fetch_error() -> None:
    with respx.mock:
        respx.get(REKT_FEED_URL).mock(
            return_value=httpx.Response(500, text="server error")
        )
        incidents = await scrape_rekt()
    assert incidents == []


async def test_defillama_filters_by_age() -> None:
    """Records older than `since_days` must be dropped."""
    now = datetime.now(UTC)
    fresh_ts = int(now.timestamp())
    old_ts = int((now.timestamp())) - 365 * 86_400  # ~1 year old
    payload = [
        {
            "date": fresh_ts,
            "name": "FreshHack",
            "amount": 1_000_000,
            "technique": "Reentrancy",
            "classification": "Smart Contract",
            "chain": ["Ethereum"],
            "source": "https://example.com/fresh",
        },
        {
            "date": old_ts,
            "name": "AncientHack",
            "amount": 99_000_000,
            "technique": "Bridge exploit",
            "chain": ["Ronin"],
            "source": "https://example.com/old",
        },
    ]
    with respx.mock:
        respx.get(DEFILLAMA_HACKS_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        incidents = await scrape_defillama_hacks(since_days=30)

    assert len(incidents) == 1
    assert incidents[0].title == "FreshHack"
    assert incidents[0].loss_usd == 1_000_000
    assert incidents[0].source == "defillama"
    # Summary uses natural-language prose (technique/classification/chain
    # embedded into sentences for better embedding similarity vs structured
    # "Key: value" listings).
    assert "reentrancy" in incidents[0].summary.lower()
    assert "Ethereum" in incidents[0].summary
    assert "FreshHack" in incidents[0].summary  # protocol name is part of the prose
    assert "$1,000,000" in incidents[0].summary  # loss formatted with commas


async def test_defillama_falls_back_to_canonical_url_when_source_empty() -> None:
    """Some DefiLlama rows have empty `source` — we must NOT drop them."""
    now = datetime.now(UTC)
    payload = [
        {
            "date": int(now.timestamp()),
            "name": "NoSourceHack",
            "amount": 500_000,
            "technique": "Phishing",
            "chain": ["Solana"],
            "source": "",
        },
    ]
    with respx.mock:
        respx.get(DEFILLAMA_HACKS_URL).mock(
            return_value=httpx.Response(200, json=payload)
        )
        incidents = await scrape_defillama_hacks(since_days=30)
    assert len(incidents) == 1
    assert incidents[0].url == "https://defillama.com/hack/NoSourceHack"


async def test_defillama_handles_bad_shape() -> None:
    """If DefiLlama ever returns a dict or non-list, we degrade gracefully."""
    with respx.mock:
        respx.get(DEFILLAMA_HACKS_URL).mock(
            return_value=httpx.Response(200, text=json.dumps({"unexpected": "shape"}))
        )
        incidents = await scrape_defillama_hacks()
    assert incidents == []
