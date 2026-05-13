"""Aderyn analyzer wrapper — Cyfrin's GPL-3 Rust static analyzer.

Repo: https://github.com/Cyfrin/aderyn  (v0.1.9 at time of writing)
Install: `cargo install aderyn` OR official install script from repo readme.

We invoke `aderyn <root> -o report.json --skip-update-check --no-snippets`
on a temp Foundry-style workspace seeded with the user's source. Aderyn
needs a project layout to drive its solc compile step — passing a bare
.sol file errors with "Not a directory" (verified live, 0.1.9).

Output schema (verified on Vuln.sol probe — see commit message for the
recorded sample):

    {
      "files_summary": {...},
      "issue_count": {"high": N, "low": M},
      "high_issues": {
        "issues": [
          {
            "title": "Potential use of `tx.origin` for authentication.",
            "description": "...",
            "detector_name": "tx-origin-used-for-auth",
            "instances": [{"contract_path": "src/X.sol", "line_no": 17, ...}]
          },
          ...
        ]
      },
      "low_issues": {"issues": [...]}
    }

Aderyn 0.1.9 emits ONLY `high` and `low` buckets. No critical / medium /
info. If a future version adds buckets we read them generically.

Subprocess isolation keeps the GPL boundary clean — we never link or
import Aderyn code. JSON over a tempfile is the only contract.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


# Aderyn severity bucket name -> our Severity enum. Aderyn's "high" =
# their highest band; we keep it HIGH (not CRITICAL) because CRITICAL is
# reserved for findings the PoC stage actually proved exploitable.
_ADERYN_SEVERITY_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
    "informational": Severity.INFO,
    "critical": Severity.CRITICAL,
}

# Per-detector confidence overrides. Some Aderyn detectors are very
# precise (literal pattern match — `tx.origin` use) while others are
# heuristic (style / gas suggestions). The default 0.75 is fine for
# pattern-based; we down-weight purely-style detectors so the LLM-triage
# stage tends to dismiss them.
_DETECTOR_CONFIDENCE_OVERRIDES = {
    "unspecific-solidity-pragma": 0.40,
    "useless-public-function": 0.50,
    "unused-state-variable": 0.50,
}


def _resolve_aderyn_cli() -> str:
    """Return an absolute path to the aderyn binary if discoverable.

    Looks in $PATH first (production install), then `~/.cargo/bin/aderyn`
    (the canonical dev install via `cargo install`). Falls back to bare
    "aderyn" so the existing FileNotFoundError handling in the base class
    silently skips when nothing is installed.
    """
    from shutil import which

    found = which("aderyn")
    if found:
        return found
    cargo_bin = Path.home() / ".cargo" / "bin" / "aderyn"
    if cargo_bin.is_file() and os.access(cargo_bin, os.X_OK):
        return str(cargo_bin)
    return "aderyn"


class AderynAnalyzer(StaticAnalyzer):
    """Aderyn (Cyfrin) — GPL-3, Rust, ~95+ detectors as of v0.1.9.

    Skips silently when the binary isn't installed (base class handles
    FileNotFoundError). So adding this analyzer to the registry is safe
    even on dev boxes without aderyn — the pipeline just won't get its
    findings.
    """

    name = "aderyn"

    def __init__(self) -> None:
        # Resolve at instance-construction time. Tests can override by
        # setting `analyzer.cli = "/path/to/mock-aderyn"` before .analyze().
        self.cli = _resolve_aderyn_cli()

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "Contract.sol").write_text(source, encoding="utf-8")
            # Minimal Foundry config — drives Aderyn's compile step. `out`
            # is mandatory or solc complains about the build path. `libs`
            # empty array skips library resolution which we don't have.
            (workspace / "foundry.toml").write_text(
                '[profile.default]\nsrc = "src"\nout = "out"\nlibs = []\n',
                encoding="utf-8",
            )

            report_path = workspace / "report.json"
            code, _stdout, stderr = await self._run_cli(
                args=[
                    str(workspace),
                    "-o", str(report_path),
                    "--no-snippets",
                    "--skip-update-check",
                ],
                cwd=workspace,
                timeout=180.0,
            )
            # Aderyn exits 0 on success. Non-zero with a written report
            # can happen when there are findings but no errors — be lenient.
            if not report_path.exists():
                if code != -127:  # -127 = not installed, already logged
                    logger.warning("aderyn.no_report", code=code, stderr=stderr[:500])
                return []

            try:
                raw = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning("aderyn.parse_failed", error=str(e))
                return []

            findings = list(self._parse(raw))
            logger.info("aderyn.parsed", count=len(findings))
            return findings

    def _parse(self, raw: dict) -> list[Finding]:
        """Walk both `high_issues.issues` and `low_issues.issues` (and any
        other `<severity>_issues` bucket a future Aderyn might add).

        Each issue can have multiple `instances`. We emit ONE Finding per
        instance — that's how the downstream pipeline expects findings
        (1 finding = 1 location). Multi-instance issues sharing title and
        detector are deduped on the merge step in the pipeline, not here.
        """
        findings: list[Finding] = []

        # Generic walk: any top-level key matching "<severity>_issues" is
        # a bucket. Future-proof against Aderyn adding "medium_issues" etc.
        for key, value in raw.items():
            if not key.endswith("_issues") or not isinstance(value, dict):
                continue
            severity_name = key[: -len("_issues")]
            sev = _ADERYN_SEVERITY_MAP.get(severity_name.lower(), Severity.INFO)
            items = value.get("issues") or []
            if not isinstance(items, list):
                continue

            for issue in items:
                if not isinstance(issue, dict):
                    continue
                detector = str(issue.get("detector_name") or "unknown")
                title = str(issue.get("title") or detector)
                description = str(issue.get("description") or "")
                confidence = _DETECTOR_CONFIDENCE_OVERRIDES.get(detector, 0.75)

                instances = issue.get("instances") or [{}]
                if not isinstance(instances, list) or not instances:
                    instances = [{}]
                for i, inst in enumerate(instances):
                    if not isinstance(inst, dict):
                        continue
                    findings.append(
                        Finding(
                            id=f"aderyn:{detector}:{len(findings)}",
                            title=title,
                            description=description,
                            severity=sev,
                            source_engine=self.name,
                            file=inst.get("contract_path"),
                            line=inst.get("line_no"),
                            confidence=confidence,
                            metadata={
                                "detector": detector,
                                "instance_index": i,
                                "src_range": inst.get("src"),
                            },
                        )
                    )
        return findings
