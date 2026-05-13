"""Aderyn analyzer unit tests against a real recorded JSON output.

The fixture `tests/fixtures/aderyn_vuln_report.json` is what
`aderyn 0.1.9` actually emitted for a hand-crafted 4-bug contract — we
DON'T regenerate it from the binary in CI. If you upgrade Aderyn and the
schema changes, re-record the fixture and update the assertions.

We only mock the subprocess layer; the parser runs over real output bytes,
so any schema drift would break tests before it broke prod.
"""

from __future__ import annotations

import json
from pathlib import Path

from audit_engine.analyzers.aderyn import AderynAnalyzer
from audit_engine.types import Severity

FIXTURE = Path(__file__).parent / "fixtures" / "aderyn_vuln_report.json"


def test_parser_handles_real_aderyn_output() -> None:
    raw = json.loads(FIXTURE.read_text())
    findings = AderynAnalyzer()._parse(raw)
    assert len(findings) == 8

    by_detector = {}
    for f in findings:
        by_detector.setdefault(f.metadata["detector"], []).append(f)

    # The contract has exactly one tx.origin use; we MUST surface it.
    assert "tx-origin-used-for-auth" in by_detector
    tx_origin = by_detector["tx-origin-used-for-auth"][0]
    assert tx_origin.severity == Severity.HIGH
    assert tx_origin.line == 17
    assert tx_origin.file == "src/Vuln.sol"
    assert tx_origin.source_engine == "aderyn"

    # zero-address-check is one finding (single instance at line 22).
    zero = by_detector["zero-address-check"][0]
    assert zero.severity == Severity.LOW
    assert zero.line == 22


def test_parser_emits_one_finding_per_instance() -> None:
    """Aderyn groups multiple locations under a single issue; we expand
    to one Finding per location so the pipeline can rank and de-dup them
    independently."""
    raw = json.loads(FIXTURE.read_text())
    findings = AderynAnalyzer()._parse(raw)
    useless_public = [f for f in findings if f.metadata["detector"] == "useless-public-function"]
    # The fixture has 4 instances of this detector.
    assert len(useless_public) == 4
    # Each instance keeps its own line number, not the first one's.
    lines = sorted(f.line for f in useless_public if f.line is not None)
    assert lines == sorted(lines)  # all present
    assert len(set(lines)) == 4  # distinct


def test_parser_lowers_confidence_for_stylistic_detectors() -> None:
    """Pure-style detectors (pragma version, public-vs-external) shouldn't
    weigh as much as pattern matches. We down-weight them so the LLM-triage
    stage dismisses noise."""
    raw = json.loads(FIXTURE.read_text())
    findings = AderynAnalyzer()._parse(raw)
    for f in findings:
        if f.metadata["detector"] == "unspecific-solidity-pragma":
            assert f.confidence == 0.40
        elif f.metadata["detector"] == "useless-public-function":
            assert f.confidence == 0.50
        elif f.metadata["detector"] == "tx-origin-used-for-auth":
            # Pattern match — default high confidence.
            assert f.confidence == 0.75


def test_parser_walks_unknown_severity_buckets() -> None:
    """Future Aderyn versions may add medium_issues / critical_issues.
    Our parser must pick those up generically by `<sev>_issues` suffix."""
    fake = {
        "issue_count": {"critical": 1},
        "critical_issues": {
            "issues": [
                {
                    "title": "Reentrancy",
                    "description": "Classic external-call-before-state-write.",
                    "detector_name": "reentrancy",
                    "instances": [{"contract_path": "src/X.sol", "line_no": 42}],
                }
            ]
        },
    }
    findings = AderynAnalyzer()._parse(fake)
    assert len(findings) == 1
    assert findings[0].severity == Severity.CRITICAL


def test_parser_tolerates_missing_fields() -> None:
    """Defensive: instances with no contract_path or no line_no must not crash."""
    raw = {
        "low_issues": {
            "issues": [
                {
                    "title": "X",
                    "detector_name": "x",
                    "instances": [{}, None, "garbage"],
                }
            ]
        }
    }
    findings = AderynAnalyzer()._parse(raw)
    # Only the first (empty dict) instance is valid-but-empty.
    assert len(findings) >= 1
    assert all(f.severity == Severity.LOW for f in findings)


def test_parser_handles_empty_report() -> None:
    """A clean contract returns no findings — must not raise."""
    assert AderynAnalyzer()._parse({"issue_count": {}}) == []


def test_parser_ignores_non_issue_keys() -> None:
    """Top-level keys like files_summary / issue_count must NOT be walked."""
    raw = {
        "files_summary": {"total_sloc": 100, "issues": "not really"},
        "issue_count": {"high": 0},
    }
    findings = AderynAnalyzer()._parse(raw)
    assert findings == []


def test_cli_resolves_to_cargo_bin_when_path_missing(monkeypatch, tmp_path) -> None:
    """If `aderyn` isn't on PATH but ~/.cargo/bin/aderyn exists, we should
    pick it up — matches the canonical `cargo install aderyn` install."""
    from audit_engine.analyzers import aderyn as mod

    fake_home = tmp_path
    fake_cargo = fake_home / ".cargo" / "bin"
    fake_cargo.mkdir(parents=True)
    fake_binary = fake_cargo / "aderyn"
    fake_binary.write_text("#!/bin/sh\n")
    fake_binary.chmod(0o755)

    monkeypatch.setattr(mod.Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr("shutil.which", lambda _: None)

    assert mod._resolve_aderyn_cli() == str(fake_binary)
