from __future__ import annotations

import json
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()

_SLITHER_IMPACT_MAP = {
    "High": Severity.HIGH,
    "Medium": Severity.MEDIUM,
    "Low": Severity.LOW,
    "Informational": Severity.INFO,
    "Optimization": Severity.INFO,
}


class SlitherAnalyzer(StaticAnalyzer):
    """Slither (Trail of Bits) — AGPL-3, Python.

    Used as fallback for legacy Solidity (<0.5) or when Aderyn fails.
    Invoked as subprocess (AGPL isolation).
    """

    name = "slither"
    cli = "slither"

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            contract_path = workspace / "Contract.sol"
            contract_path.write_text(source, encoding="utf-8")
            report_path = workspace / "slither.json"

            code, stdout, stderr = await self._run_cli(
                args=[
                    str(contract_path),
                    "--json",
                    str(report_path),
                    "--disable-color",
                ],
                cwd=workspace,
                timeout=180.0,
            )

            if not report_path.exists():
                logger.warning("slither.failed", code=code, stderr=stderr[:500])
                return []

            try:
                raw = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("slither.parse_failed", error=str(e))
                return []

            return list(self._parse(raw))

    def _parse(self, raw: dict) -> list[Finding]:
        findings: list[Finding] = []
        results = (raw.get("results") or {}).get("detectors") or []
        for d in results:
            sev = _SLITHER_IMPACT_MAP.get(d.get("impact", ""), Severity.INFO)
            elements = d.get("elements") or [{}]
            first = elements[0] if elements else {}
            src_map = first.get("source_mapping") or {}
            findings.append(
                Finding(
                    id=f"slither:{d.get('check', 'unknown')}:{len(findings)}",
                    title=d.get("check", "Slither finding"),
                    description=d.get("description", ""),
                    severity=sev,
                    source_engine=self.name,
                    file=src_map.get("filename_relative") or src_map.get("filename_absolute"),
                    line=(src_map.get("lines") or [None])[0],
                    confidence=_confidence_from_slither(d.get("confidence")),
                )
            )
        return findings


def _confidence_from_slither(c: str | None) -> float:
    return {"High": 0.85, "Medium": 0.6, "Low": 0.4}.get(c or "", 0.5)
