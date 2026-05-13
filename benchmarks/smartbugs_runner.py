"""SmartBugs Curated benchmark runner — RECALL measurement for wr3 analyzers.

What this benchmarks (and what it doesn't):
    SmartBugs Curated is 143 labeled vulnerable Solidity contracts grouped
    by vuln-class folder (reentrancy / access_control / arithmetic / ...).
    For each contract we know one expected vulnerability class. We DO NOT
    have "ground truth" line numbers, so this can't measure false-positive
    rate precisely — it only measures whether wr3 surfaces a finding of
    the expected class somewhere.

    Recall here = "for a labeled-vulnerable contract, did at least one
    analyzer produce a HIGH or MEDIUM finding matching the expected class?"

    A real F1 score requires the DefiHackLabs-style "incident → vuln class
    → exact line" labels; that's a follow-up.

Usage:
    uv run --project packages/audit-engine python benchmarks/smartbugs_runner.py \\
        --dataset /tmp/smartbugs-curated/dataset \\
        --categories reentrancy access_control unchecked_low_level_calls \\
        --per-category 5

Outputs a markdown table + JSON dump to benchmarks/results/.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Make the audit-engine importable without installing.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "audit-engine" / "src"))

from audit_engine.analyzers import StaticAnalyzerRegistry  # noqa: E402
from audit_engine.types import Finding, Severity  # noqa: E402


# Mapping: SmartBugs category -> regex over Finding.title|description that
# indicates "this finding matches the expected class".
#
# We match generously here: as long as ONE engine produces a finding
# describing the right class, recall counts as 1. Multiple engines flagging
# the same class don't double-count.
#
# Patterns are case-insensitive. Tested against real Aderyn/Slither/Wake
# detector names and titles (see fixtures in tests/fixtures/*_report.json).
CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "reentrancy": re.compile(r"reentran", re.IGNORECASE),
    "access_control": re.compile(
        r"tx\.origin|tx-origin|access[\s-]control|owner|unprotected|"
        r"missing[\s-]*(auth|access|role)|public\s+function|arbitrary[\s-]*send|"
        # incorrect-constructor-name is a pre-0.5 access-control class:
        # a function named like the contract but spelled wrong is callable
        # by anyone and acts like the constructor.
        r"constructor[\s-]*(name|naming)|incorrect[\s-]*constructor|"
        # Slither's `arbitrary-send-eth` is also commonly classified as
        # access-control (already covered by `arbitrary-send` above) and
        # `suicidal` (callable selfdestruct) is the canonical example.
        r"suicidal|selfdestruct",
        re.IGNORECASE,
    ),
    "unchecked_low_level_calls": re.compile(
        r"unchecked|low[\s-]*level|return[\s-]*value",
        re.IGNORECASE,
    ),
    "arithmetic": re.compile(
        r"overflow|underflow|divide[\s-]*before[\s-]*multiply|"
        r"arithmetic|safemath",
        re.IGNORECASE,
    ),
    "bad_randomness": re.compile(
        r"random|prng|block[\s-]*(timestamp|number|hash)|weak[\s-]*entropy",
        re.IGNORECASE,
    ),
    "denial_of_service": re.compile(
        r"denial[\s-]*of[\s-]*service|dos|out[\s-]*of[\s-]*gas|"
        r"failed[\s-]*call",
        re.IGNORECASE,
    ),
    "time_manipulation": re.compile(
        r"block\.timestamp|time[\s-]*manipulation|now\b",
        re.IGNORECASE,
    ),
}

# A finding only "counts" if it's at this severity or higher. INFO is too
# noisy to claim as a real detection.
_DETECT_SEVERITIES = {Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW}


@dataclass
class ContractResult:
    category: str
    contract_path: str
    total_findings: int
    findings_by_engine: dict[str, int] = field(default_factory=dict)
    detected: bool = False
    matching_findings: list[dict] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str | None = None


def matches_category(finding: Finding, category: str) -> bool:
    if finding.severity not in _DETECT_SEVERITIES:
        return False
    pattern = CATEGORY_PATTERNS.get(category)
    if pattern is None:
        return False
    haystack = f"{finding.title} {finding.description}"
    return bool(pattern.search(haystack))


async def run_one(contract_path: Path, category: str) -> ContractResult:
    source = contract_path.read_text(encoding="utf-8", errors="replace")
    started = time.monotonic()
    try:
        findings = await StaticAnalyzerRegistry.run_all(
            source=source, network="ethereum"
        )
    except Exception as e:
        return ContractResult(
            category=category,
            contract_path=str(contract_path),
            total_findings=0,
            duration_seconds=time.monotonic() - started,
            error=f"{type(e).__name__}: {e}",
        )

    by_engine: Counter[str] = Counter(f.source_engine for f in findings)
    matches = [f for f in findings if matches_category(f, category)]
    return ContractResult(
        category=category,
        contract_path=str(contract_path.relative_to(contract_path.parents[2])),
        total_findings=len(findings),
        findings_by_engine=dict(by_engine),
        detected=bool(matches),
        matching_findings=[
            {
                "engine": f.source_engine,
                "severity": str(f.severity),
                "title": f.title[:80],
                "line": f.line,
            }
            for f in matches[:3]
        ],
        duration_seconds=time.monotonic() - started,
    )


def collect_contracts(
    dataset: Path, categories: list[str], per_category: int
) -> list[tuple[Path, str]]:
    """Pick the first N .sol files per category (deterministic, sorted)."""
    out: list[tuple[Path, str]] = []
    for cat in categories:
        cat_dir = dataset / cat
        if not cat_dir.is_dir():
            print(f"WARN: missing category dir {cat_dir}", file=sys.stderr)
            continue
        files = sorted(cat_dir.glob("*.sol"))[:per_category]
        if not files:
            print(f"WARN: no .sol in {cat_dir}", file=sys.stderr)
        for f in files:
            out.append((f, cat))
    return out


def render_markdown(results: list[ContractResult]) -> str:
    """Per-category recall + a per-contract table."""
    by_cat: dict[str, list[ContractResult]] = {}
    for r in results:
        by_cat.setdefault(r.category, []).append(r)

    lines: list[str] = [
        "# wr3 SmartBugs-Curated benchmark — recall report",
        "",
        f"Total contracts: **{len(results)}**, "
        f"engines: baseline + aderyn + slither + wake",
        "",
        "## Recall by category",
        "",
        "| Category | Contracts | Detected | Recall |",
        "|---|---:|---:|---:|",
    ]
    overall_total = 0
    overall_detected = 0
    for cat, rows in sorted(by_cat.items()):
        n = len(rows)
        det = sum(1 for r in rows if r.detected)
        recall = (det / n * 100.0) if n else 0.0
        overall_total += n
        overall_detected += det
        lines.append(f"| {cat} | {n} | {det} | {recall:.0f}% |")
    overall_recall = (
        (overall_detected / overall_total * 100.0) if overall_total else 0.0
    )
    lines.append(f"| **TOTAL** | **{overall_total}** | **{overall_detected}** | **{overall_recall:.0f}%** |")
    lines.append("")

    lines += [
        "## Per-contract detail",
        "",
        "| Category | Contract | Findings | Engines | Matched | Time |",
        "|---|---|---:|---|:---:|---:|",
    ]
    for r in results:
        engines = ", ".join(f"{k}:{v}" for k, v in sorted(r.findings_by_engine.items()))
        mark = "✓" if r.detected else ("✗" if not r.error else "ERR")
        path = Path(r.contract_path).name
        lines.append(
            f"| {r.category} | `{path}` | {r.total_findings} | "
            f"{engines or '-'} | {mark} | {r.duration_seconds:.1f}s |"
        )

    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "Each contract is run through `StaticAnalyzerRegistry.run_all`, "
        "which executes baseline + aderyn + slither + wake in parallel. "
        "A contract is counted as 'detected' if at least one engine produces "
        "a LOW/MEDIUM/HIGH/CRITICAL finding whose title or description "
        "matches the category regex (see `CATEGORY_PATTERNS` in this script). "
        "INFO findings are excluded — too noisy to claim as detection signal."
    )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--categories", nargs="+", required=True)
    parser.add_argument("--per-category", type=int, default=3)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).parent / "results"
    )
    args = parser.parse_args()

    pairs = collect_contracts(args.dataset, args.categories, args.per_category)
    if not pairs:
        print("No contracts to benchmark.", file=sys.stderr)
        sys.exit(1)

    print(f"Running {len(pairs)} contracts...", file=sys.stderr)
    results: list[ContractResult] = []
    for i, (path, cat) in enumerate(pairs, 1):
        print(f"  [{i}/{len(pairs)}] {cat}/{path.name}", file=sys.stderr)
        r = await run_one(path, cat)
        results.append(r)
        if r.error:
            print(f"    ERR: {r.error[:100]}", file=sys.stderr)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    md_path = args.output_dir / f"smartbugs-{timestamp}.md"
    json_path = args.output_dir / f"smartbugs-{timestamp}.json"

    md_path.write_text(render_markdown(results), encoding="utf-8")
    json_path.write_text(
        json.dumps([r.__dict__ for r in results], indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nWrote {md_path}", file=sys.stderr)
    print(f"Wrote {json_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
