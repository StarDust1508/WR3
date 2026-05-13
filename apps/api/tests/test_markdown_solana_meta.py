"""Markdown rendering — Solana on-chain metadata section.

Built as a follow-up to W11 stub-fix #6: Solana scans get enriched with
upgrade-authority / executable / last-upgrade-slot via JSON-RPC. The
markdown export now surfaces that block right under the header so the
reader sees the centralisation context before scrolling through findings.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from wr3_api.models import Scan
from wr3_api.services.report_markdown import render_scan_markdown


def _scan_with_meta(meta: dict | None) -> Scan:
    s = Scan()
    s.id = uuid.uuid4()
    s.address = "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"
    s.network = "solana"
    s.stage = "done"
    s.progress = 100
    s.score = 60.0
    s.tier = "yellow"
    s.report = {
        "axes": [],
        "chain_metadata": meta,
    } if meta is not None else None
    s.duration_seconds = 10.0
    s.created_at = datetime(2026, 5, 12, tzinfo=UTC)
    s.completed_at = datetime(2026, 5, 12, tzinfo=UTC)
    return s


def test_markdown_renders_upgradeable_metadata() -> None:
    meta = {
        "address": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
        "executable": True,
        "loader": "BPFLoaderUpgradeab1e11111111111111111111111",
        "upgradeable": True,
        "upgrade_authority": "CvQZZ23qYDWF2RUpxYJ8y9K4skmuvYEEjH7fK58jtipQ",
        "last_upgrade_slot": 418976287,
    }
    md = render_scan_markdown(_scan_with_meta(meta), [])
    assert "## On-chain metadata" in md
    assert "Executable:** yes" in md
    assert "Upgradeable:** yes" in md
    assert "centralisation risk" in md
    assert "CvQZZ23qYDWF2RUpxYJ8y9K4skmuvYEEjH7fK58jtipQ" in md
    assert "418,976,287" in md


def test_markdown_renders_frozen_program() -> None:
    meta = {
        "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "executable": True,
        "loader": "BPFLoader2111111111111111111111111111111111",
        "upgradeable": False,
        "upgrade_authority": None,
        "last_upgrade_slot": None,
    }
    md = render_scan_markdown(_scan_with_meta(meta), [])
    assert "frozen" in md
    assert "Upgradeable:** no" in md
    assert "centralisation" not in md  # we don't warn on frozen programs


def test_markdown_no_metadata_section_when_absent() -> None:
    """EVM scans (no chain_metadata) must not get an empty section."""
    md = render_scan_markdown(_scan_with_meta(None), [])
    assert "On-chain metadata" not in md
