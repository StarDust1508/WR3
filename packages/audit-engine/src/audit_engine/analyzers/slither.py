from __future__ import annotations

import json
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer, detect_solc_version
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

    Complementary to Aderyn: catches different classes (e.g. arbitrary-send-eth,
    unchecked-lowlevel as MEDIUM, naming-convention/solc-version). Detector
    overlap is intentional — when two engines flag the same line that's a
    consensus signal the multi-agent triage stage uses.

    Prereqs (silently skipped if absent — base class handles
    FileNotFoundError + non-zero exit):
        - `slither` on PATH (`uvx slither-analyzer` or `pipx install
          slither-analyzer`)
        - `solc` on PATH (`brew install solc-select && solc-select install
          0.8.20 && solc-select use 0.8.20`)

    crytic-compile (Slither's build layer) auto-selects matching solc when
    solc-select is installed. We DON'T pin a version here — the contract's
    pragma drives it.

    Subprocess isolation keeps the AGPL boundary clean: we never import
    Slither code into wr3's proprietary core. JSON over a tempfile is the
    only contract.
    """

    name = "slither"
    cli = "slither"

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            contract_path = workspace / "Contract.sol"
            contract_path.write_text(source, encoding="utf-8")
            report_path = workspace / "slither.json"

            # SOLC_VERSION drives crytic-compile's solc-select resolution.
            # Without this, an old (^0.4.19) contract fails to compile under
            # the user's default solc (likely 0.8.x from Homebrew).
            env: dict[str, str] = {}
            solc_v = detect_solc_version(source)
            if solc_v:
                env["SOLC_VERSION"] = solc_v

            code, _stdout, stderr = await self._run_cli(
                args=[
                    str(contract_path),
                    "--json",
                    str(report_path),
                    "--disable-color",
                ],
                cwd=workspace,
                timeout=180.0,
                env=env or None,
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
