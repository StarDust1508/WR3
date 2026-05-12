"""Markdown rendering of scan reports — pure unit tests.

We construct in-memory Scan + Finding instances (no DB) and assert that
the rendered markdown contains the structural elements clients depend
on: severity headers, file/line citations, the score breakdown table,
and the dismissed-findings details section.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from wr3_api.models import Finding, Scan
from wr3_api.services.report_markdown import render_scan_markdown


def _scan(**overrides) -> Scan:
    s = Scan()
    s.id = uuid.uuid4()
    s.address = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    s.network = "ethereum"
    s.stage = "done"
    s.progress = 100
    s.score = 70.2
    s.tier = "green"
    s.report = {
        "axes": [
            {"name": "Code Security", "weight": 0.35, "score": 52.0, "rationale": "6x medium"},
            {"name": "Liquidity Risk", "weight": 0.15, "score": 80.0, "rationale": "Not evaluated"},
        ],
    }
    s.duration_seconds = 48.2
    s.created_at = datetime(2026, 5, 12, 14, 20, tzinfo=UTC)
    s.completed_at = datetime(2026, 5, 12, 14, 21, tzinfo=UTC)
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _finding(**overrides) -> Finding:
    f = Finding()
    f.id = uuid.uuid4()
    f.title = "Address parameter without zero-address check"
    f.description = "Functions accepting address must verify it is non-zero."
    f.severity = "medium"
    f.source_engine = "baseline"
    f.file = None
    f.line = 235
    f.confidence = 0.6
    f.dismissed = False
    f.poc_validated = False
    f.poc_path = None
    for k, v in overrides.items():
        setattr(f, k, v)
    return f


def test_markdown_includes_score_and_tier() -> None:
    md = render_scan_markdown(_scan(), [])
    assert "70.2 / 100" in md
    assert "GREEN" in md
    assert "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" in md


def test_markdown_renders_axes_table() -> None:
    md = render_scan_markdown(_scan(), [])
    assert "| Axis | Weight | Score | Rationale |" in md
    assert "| Code Security | 35% | 52.0 | 6x medium |" in md


def test_markdown_groups_findings_by_severity() -> None:
    fs = [
        _finding(severity="critical", title="Reentrancy", line=10),
        _finding(severity="medium", title="No zero check", line=235),
        _finding(severity="low", title="Bad style", line=500),
    ]
    md = render_scan_markdown(_scan(), fs)
    assert "🔴 CRITICAL" in md
    assert "🟡 MEDIUM" in md
    assert "🔵 LOW" in md
    # CRITICAL must come before MEDIUM in the document
    assert md.find("🔴 CRITICAL") < md.find("🟡 MEDIUM")


def test_markdown_no_active_findings_message() -> None:
    md = render_scan_markdown(_scan(), [])
    assert "No active findings" in md


def test_markdown_dismissed_in_details_section() -> None:
    fs = [
        _finding(severity="medium", title="Active"),
        _finding(severity="low", title="Dismissed by triage", dismissed=True),
    ]
    md = render_scan_markdown(_scan(), fs)
    assert "<details>" in md
    assert "Dismissed by triage (1)" in md


def test_markdown_poc_validated_badge() -> None:
    fs = [_finding(severity="high", title="Real exploit", poc_validated=True)]
    md = render_scan_markdown(_scan(), fs)
    assert "PoC ✓" in md


def test_markdown_escapes_pipes_in_rationale() -> None:
    """SQL injection-style pipes in axis text shouldn't break the table."""
    scan = _scan(report={"axes": [
        {"name": "X | Y", "weight": 0.5, "score": 80.0, "rationale": "a | b"},
    ]})
    md = render_scan_markdown(scan, [])
    # The escaped pipes survive but as `\|`
    assert "X \\| Y" in md
    assert "a \\| b" in md
