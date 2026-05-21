"""Tests for finding deduplication logic."""

from audit_engine.analyzers import deduplicate_findings
from audit_engine.types import Finding, Severity


def _finding(
    title: str = "Reentrancy",
    line: int | None = 42,
    confidence: float = 0.7,
    engine: str = "baseline",
    **kwargs,
) -> Finding:
    return Finding(
        id=f"test-{title}-{line}-{engine}",
        title=title,
        description=f"{title} at line {line}",
        severity=Severity.HIGH,
        source_engine=engine,
        file="Contract.sol",
        line=line,
        confidence=confidence,
        **kwargs,
    )


class TestExactDedup:
    """Pass 1: same title + same line = duplicate."""

    def test_identical_findings_collapsed(self):
        findings = [
            _finding(engine="baseline", confidence=0.6),
            _finding(engine="slither", confidence=0.9),
            _finding(engine="aderyn", confidence=0.8),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].confidence == 0.9
        assert result[0].metadata["engines"] == ["slither", "aderyn", "baseline"]

    def test_case_insensitive_title_match(self):
        findings = [
            _finding(title="Reentrancy", engine="baseline"),
            _finding(title="reentrancy", engine="slither"),
            _finding(title="  REENTRANCY  ", engine="wake"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1

    def test_different_lines_not_exact_dedup(self):
        """Same title at different lines survives pass 1 as separate items."""
        findings = [
            _finding(line=10, engine="baseline"),
            _finding(line=20, engine="baseline"),
        ]
        # After exact dedup they are separate; title rollup collapses them.
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert sorted(result[0].metadata["locations"]) == [10, 20]


class TestTitleRollup:
    """Pass 2: same title across different lines = one finding with locations."""

    def test_locations_collected(self):
        findings = [
            _finding(line=10, engine="baseline", confidence=0.5),
            _finding(line=20, engine="slither", confidence=0.9),
            _finding(line=30, engine="baseline", confidence=0.6),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].metadata["locations"] == [10, 20, 30]
        assert result[0].confidence == 0.9

    def test_engines_merged_across_lines(self):
        findings = [
            _finding(line=10, engine="baseline"),
            _finding(line=20, engine="slither"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        engines = result[0].metadata["engines"]
        assert "baseline" in engines
        assert "slither" in engines

    def test_none_line_excluded_from_locations(self):
        findings = [
            _finding(line=None, engine="baseline"),
            _finding(line=10, engine="slither"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].metadata["locations"] == [10]


class TestEdgeCases:

    def test_empty_input(self):
        assert deduplicate_findings([]) == []

    def test_single_finding_unchanged(self):
        f = _finding()
        result = deduplicate_findings([f])
        assert len(result) == 1
        assert result[0].title == f.title
        assert result[0].metadata["engines"] == [f.source_engine]

    def test_different_titles_not_merged(self):
        findings = [
            _finding(title="Reentrancy"),
            _finding(title="Unchecked return value"),
        ]
        result = deduplicate_findings(findings)
        assert len(result) == 2

    def test_metadata_preserved(self):
        f = _finding(metadata={"custom_key": "value"})
        result = deduplicate_findings([f])
        assert result[0].metadata["custom_key"] == "value"
        assert "engines" in result[0].metadata

    def test_large_duplication_collapsed(self):
        """Simulate the 10x baseline spam scenario from the task description."""
        findings = [
            _finding(
                title="Address parameter without zero-address check",
                line=i * 10,
                engine="baseline",
                confidence=0.5,
            )
            for i in range(10)
        ]
        # Add a slither duplicate for one of them.
        findings.append(
            _finding(
                title="Address parameter without zero-address check",
                line=10,
                engine="slither",
                confidence=0.85,
            )
        )
        result = deduplicate_findings(findings)
        assert len(result) == 1
        assert result[0].confidence == 0.85
        assert len(result[0].metadata["locations"]) == 10
        assert "slither" in result[0].metadata["engines"]
        assert "baseline" in result[0].metadata["engines"]
