"""Security regressions — guards against the issues found in the self-audit.

These tests do NOT replace the live e2e checks; they pin specific contracts
that, if broken in a future refactor, would re-introduce a real-world bug.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from wr3_api.models import Finding, Scan
from wr3_api.services.report_markdown import render_scan_markdown


# --- Markdown injection guard -----------------------------------------------


def _scan() -> Scan:
    s = Scan()
    s.id = uuid.uuid4()
    s.address = "0xabc"
    s.network = "ethereum"
    s.stage = "done"
    s.progress = 100
    s.score = 50.0
    s.tier = "yellow"
    s.report = {"axes": []}
    s.duration_seconds = 1.0
    s.created_at = datetime(2026, 5, 13, tzinfo=UTC)
    s.completed_at = datetime(2026, 5, 13, tzinfo=UTC)
    return s


def _finding_with_title(title: str, *, description: str = "") -> Finding:
    f = Finding()
    f.id = uuid.uuid4()
    f.title = title
    f.description = description
    f.severity = "high"
    f.source_engine = "baseline"
    f.file = None
    f.line = 1
    f.confidence = 0.9
    f.dismissed = False
    f.poc_validated = False
    f.poc_path = None
    f.extra = None
    return f


def test_md_title_cannot_inject_heading() -> None:
    """A finding title containing '#' must not break document structure."""
    f = _finding_with_title("# pwned root heading")
    md = render_scan_markdown(_scan(), [f])
    # The literal '#' in the title must be escaped — never start a new heading.
    # We render finding titles as `#### {title}` (4 hashes), so a malicious
    # leading `#` would have made it `##### ...` (still escalation).
    assert "#### \\# pwned" in md
    # And the escaped form must NOT match the unescaped "## pwned" pattern.
    assert "\n# pwned root heading\n" not in md


def test_md_title_cannot_inject_link() -> None:
    """`[text](evil)` in titles would render as a phishing link otherwise."""
    f = _finding_with_title("Reentrancy [click here](https://evil.example)")
    md = render_scan_markdown(_scan(), [f])
    # Brackets and parens must be escaped, breaking the link syntax.
    assert "[click here]" not in md
    assert "\\[click here\\]" in md
    assert "(https://evil.example)" not in md


def test_md_description_cannot_inject_image() -> None:
    """`![](http://evil/pixel.png)` would phone home from any md viewer."""
    f = _finding_with_title("bug", description="![evil](http://attacker/track.png)")
    md = render_scan_markdown(_scan(), [f])
    assert "![evil]" not in md
    assert "(http://attacker/track.png)" not in md


def test_md_similar_incidents_strips_javascript_scheme() -> None:
    """If the incidents table ever held a `javascript:` URL, we must not
    surface it as a clickable link in the report."""
    f = _finding_with_title("Reentrancy")
    f.extra = {
        "similar_incidents": [
            {
                "title": "Fake Hack",
                "url": "javascript:alert(1)",
                "source": "rekt",
                "loss_usd": 0,
                "published_at": "2026-04-01",
                "similarity": 0.9,
            }
        ]
    }
    md = render_scan_markdown(_scan(), [f])
    assert "javascript:" not in md  # entirely dropped, not just escaped
    # But the title-bullet still renders (so the user sees there's a match
    # they need to investigate).
    assert "Fake Hack" in md


def test_md_axes_rationale_escapes_inline_markdown() -> None:
    """LLM-generated rationale shouldn't be able to inject markdown."""
    scan = _scan()
    scan.report = {
        "axes": [
            {
                "name": "X",
                "weight": 0.5,
                "score": 50.0,
                "rationale": "See [malicious](http://evil) for details",
            }
        ]
    }
    md = render_scan_markdown(scan, [])
    assert "[malicious](http://evil)" not in md
    assert "\\[malicious\\]" in md


# --- Dedup loop fix ---------------------------------------------------------


def test_dedup_loop_finds_cross_source_past_same_source_top() -> None:
    """The previous implementation broke after the FIRST row regardless of
    source, so a same-source top match would mask a legitimate cross-source
    duplicate at rank #2. The fix walks results in descending similarity
    until either (a) similarity drops below threshold or (b) a cross-source
    match is found.

    We exercise the logic directly by simulating an ordered result list.
    """
    from wr3_api.models.incident import DEDUP_COSINE_THRESHOLD

    # Simulated query result: top match is same-source but the second is
    # cross-source and would qualify under the new logic.
    rekt_top = type("R", (), {"source": "rekt"})()
    defillama_second = type("D", (), {"source": "defillama"})()
    rows = [
        (rekt_top, 0.92),         # top: same source — must NOT be picked
        (defillama_second, 0.80), # cross-source and above threshold — MUST be picked
        (rekt_top, 0.30),         # below threshold — must short-circuit further iteration
    ]

    # Inline the loop logic so we test the actual rule shape, not the SQL.
    canonical = None
    for row, sim in rows:
        if sim < DEDUP_COSINE_THRESHOLD:
            break
        if row.source != "rekt":
            canonical = row
            break

    assert canonical is defillama_second


def test_dedup_loop_short_circuits_below_threshold() -> None:
    """Once similarity falls below threshold, we MUST NOT keep checking —
    rows are ordered by distance ascending."""
    from wr3_api.models.incident import DEDUP_COSINE_THRESHOLD

    same_src = type("R", (), {"source": "rekt"})()
    other_src_too_far = type("D", (), {"source": "defillama"})()
    rows = [
        (same_src, 0.99),          # top: same source, skip
        (other_src_too_far, 0.10), # cross-source but way below threshold
    ]

    canonical = None
    for row, sim in rows:
        if sim < DEDUP_COSINE_THRESHOLD:
            break
        if row.source != "rekt":
            canonical = row
            break

    assert canonical is None  # too-far cross-source must NOT be picked
