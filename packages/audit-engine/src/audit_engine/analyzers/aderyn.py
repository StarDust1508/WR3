from __future__ import annotations

import json
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


_ADERYN_SEVERITY_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "info": Severity.INFO,
    "informational": Severity.INFO,
    "critical": Severity.CRITICAL,
}


class AderynAnalyzer(StaticAnalyzer):
    """Aderyn (Cyfrin) — GPL-3, Rust, ~100+ detectors.

    Repo: https://github.com/Cyfrin/aderyn
    Install: cargo install aderyn (or download from releases).
    Invoked as subprocess; JSON output parsed into Findings.
    """

    name = "aderyn"
    cli = "aderyn"

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "Contract.sol").write_text(source, encoding="utf-8")
            (workspace / "foundry.toml").write_text(
                'src = "src"\nout = "out"\nlibs = ["lib"]\n',
                encoding="utf-8",
            )

            report_path = workspace / "report.json"

            code, stdout, stderr = await self._run_cli(
                args=["--output", str(report_path), "--no-snippets"],
                cwd=workspace,
                timeout=180.0,
            )
            if code != 0 and not report_path.exists():
                logger.warning("aderyn.failed", code=code, stderr=stderr[:500])
                return []

            try:
                raw = json.loads(report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.warning("aderyn.parse_failed", error=str(e))
                return []

            return list(self._parse(raw))

    def _parse(self, raw: dict) -> list[Finding]:
        findings: list[Finding] = []
        issues = raw.get("issues", {})
        if isinstance(issues, dict):
            for severity_key, items in issues.items():
                sev = _ADERYN_SEVERITY_MAP.get(severity_key.lower(), Severity.INFO)
                for it in items if isinstance(items, list) else []:
                    findings.append(
                        Finding(
                            id=f"aderyn:{it.get('detector', 'unknown')}:{len(findings)}",
                            title=it.get("title", it.get("detector", "Aderyn finding")),
                            description=it.get("description", ""),
                            severity=sev,
                            source_engine=self.name,
                            file=(it.get("instances", [{}])[0] or {}).get("contract_path"),
                            line=(it.get("instances", [{}])[0] or {}).get("line_no"),
                            confidence=0.75,
                        )
                    )
        return findings
