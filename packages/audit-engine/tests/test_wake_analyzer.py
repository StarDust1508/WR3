"""Wake analyzer parser tests against real recorded output (wake 4.22.1)."""

from __future__ import annotations

import json
from pathlib import Path

from audit_engine.analyzers.wake import WakeAnalyzer
from audit_engine.types import Severity

FIXTURE = Path(__file__).parent / "fixtures" / "wake_vuln_report.json"


def test_parser_handles_real_wake_4x_list_output() -> None:
    raw = json.loads(FIXTURE.read_text())
    assert isinstance(raw, list)  # Wake 4.x emits a top-level list
    findings = WakeAnalyzer()._parse(raw)
    assert len(findings) == 3
    titles = {f.title for f in findings}
    assert "Unsafe usage of tx.origin" in titles
    assert "Unchecked return value" in titles


def test_parser_pulls_correct_line_from_location() -> None:
    raw = json.loads(FIXTURE.read_text())
    findings = WakeAnalyzer()._parse(raw)
    tx_origin = next(f for f in findings if f.metadata["detector"] == "tx-origin")
    # Detector hit was on the require(tx.origin == owner) statement.
    assert tx_origin.line == 17


def test_parser_accepts_legacy_dict_output() -> None:
    """Wake 3.x emitted dict keyed by detector_name. We keep that path
    working so an environment with an old Wake doesn't silently return 0
    findings."""
    legacy = {
        "detections": {
            "tx-origin": [
                {
                    "detector_name": "tx-origin",
                    "impact": "medium",
                    "confidence": "high",
                    "detection": {
                        "message": "tx.origin used",
                        "location": {"relative_path": "src/X.sol", "start_line": 7},
                    },
                }
            ]
        }
    }
    findings = WakeAnalyzer()._parse(legacy)
    assert len(findings) == 1
    assert findings[0].severity == Severity.MEDIUM


def test_parser_skips_suppressed() -> None:
    raw = [
        {
            "detector_name": "x",
            "impact": "high",
            "confidence": "high",
            "detection": {"message": "y", "location": {"start_line": 1}},
            "suppressed": True,
        }
    ]
    assert WakeAnalyzer()._parse(raw) == []


def test_parser_maps_confidence_correctly() -> None:
    """Wake's High/Medium/Low confidence labels are converted to floats
    on the same scale we use for other analyzers."""
    raw = json.loads(FIXTURE.read_text())
    findings = WakeAnalyzer()._parse(raw)
    for f in findings:
        # The fixture has all-medium confidence → 0.65 mapping.
        if f.metadata.get("wake_confidence") == "medium":
            assert f.confidence == 0.65


def test_parser_handles_empty_list() -> None:
    """Clean contract → empty top-level list — must not crash."""
    assert WakeAnalyzer()._parse([]) == []
    assert WakeAnalyzer()._parse({}) == []


def test_parser_includes_uri_in_description() -> None:
    """Wake's `uri` points to docs.ackee.xyz — useful to link in the
    report. We append it to description rather than dropping it."""
    raw = json.loads(FIXTURE.read_text())
    findings = WakeAnalyzer()._parse(raw)
    f = findings[0]
    if f.metadata.get("wake_uri"):
        assert "Reference:" in f.description
        assert f.metadata["wake_uri"] in f.description


def test_warning_impact_buckets_to_low() -> None:
    """`warning` impact is Wake's portability/style band; treat as LOW
    so the score isn't bloated by ERC-4337 portability hints."""
    raw = [
        {
            "detector_name": "warn",
            "impact": "warning",
            "confidence": "low",
            "detection": {"message": "be careful", "location": {"start_line": 1}},
        }
    ]
    findings = WakeAnalyzer()._parse(raw)
    assert findings[0].severity == Severity.LOW
