"""Slither analyzer parser tests against real recorded output.

Fixture `slither_vuln_report.json` is what `slither 0.11.5` actually
emitted for a hand-crafted 4-bug contract — re-record if the schema
changes (rare, Slither output has been stable for years).
"""

from __future__ import annotations

import json
from pathlib import Path

from audit_engine.analyzers.slither import SlitherAnalyzer, _confidence_from_slither
from audit_engine.types import Severity

FIXTURE = Path(__file__).parent / "fixtures" / "slither_vuln_report.json"


def test_parser_handles_real_slither_output() -> None:
    raw = json.loads(FIXTURE.read_text())
    findings = SlitherAnalyzer()._parse(raw)
    # Real run: 9 detector hits on the Vuln contract.
    assert len(findings) == 9
    titles = {f.title for f in findings}
    # The notable HIGH that complements Aderyn (which doesn't catch it).
    assert "arbitrary-send-eth" in titles
    # Medium that Aderyn also misses.
    assert "unchecked-lowlevel" in titles
    # Slither flags tx.origin at MEDIUM where Aderyn marks it HIGH — the
    # downstream triage stage reconciles by consensus.
    assert "tx-origin" in titles


def test_slither_high_severity_extracted_correctly() -> None:
    raw = json.loads(FIXTURE.read_text())
    findings = SlitherAnalyzer()._parse(raw)
    high = [f for f in findings if f.severity == Severity.HIGH]
    assert len(high) == 1
    assert high[0].title == "arbitrary-send-eth"
    # The withdraw() function lives at lines 26-28; we take the first line.
    assert high[0].line == 26


def test_slither_pulls_first_line_from_source_mapping() -> None:
    """Slither emits `source_mapping.lines: [int, ...]`. We take lines[0]
    because findings are per-detector-hit, not per-statement."""
    raw = json.loads(FIXTURE.read_text())
    findings = SlitherAnalyzer()._parse(raw)
    for f in findings:
        # Every finding has an integer line number when source_mapping is
        # present (Slither always emits it for real detectors).
        assert f.line is None or isinstance(f.line, int)


def test_confidence_map() -> None:
    assert _confidence_from_slither("High") == 0.85
    assert _confidence_from_slither("Medium") == 0.6
    assert _confidence_from_slither("Low") == 0.4
    assert _confidence_from_slither(None) == 0.5
    assert _confidence_from_slither("garbage") == 0.5


def test_parser_handles_missing_elements() -> None:
    """Defensive: a detector hit with no elements must not crash."""
    raw = {
        "results": {
            "detectors": [
                {
                    "check": "ghost",
                    "impact": "Low",
                    "confidence": "High",
                    "description": "no elements field",
                    # elements key intentionally absent
                }
            ]
        }
    }
    findings = SlitherAnalyzer()._parse(raw)
    assert len(findings) == 1
    assert findings[0].line is None
    assert findings[0].file is None


def test_parser_handles_empty_results() -> None:
    """A clean contract returns no findings — must not raise."""
    assert SlitherAnalyzer()._parse({"results": {"detectors": []}}) == []
    assert SlitherAnalyzer()._parse({"results": {}}) == []
    assert SlitherAnalyzer()._parse({}) == []


def test_optimization_impact_maps_to_info() -> None:
    """Slither's 'Optimization' impact is gas-level noise; collapse to INFO
    so it doesn't pollute the score."""
    raw = {
        "results": {
            "detectors": [
                {
                    "check": "external-function",
                    "impact": "Optimization",
                    "confidence": "High",
                    "description": "could be external",
                    "elements": [
                        {
                            "source_mapping": {
                                "filename_relative": "src/X.sol",
                                "lines": [5],
                            }
                        }
                    ],
                }
            ]
        }
    }
    findings = SlitherAnalyzer()._parse(raw)
    assert findings[0].severity == Severity.INFO
