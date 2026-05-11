from __future__ import annotations

import json
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()

_WAKE_SEVERITY_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "warning": Severity.LOW,
    "info": Severity.INFO,
}


class WakeAnalyzer(StaticAnalyzer):
    """Wake (Ackee Blockchain) — ISC permissive, Python + LSP + fuzzing.

    Repo: https://github.com/Ackee-Blockchain/wake
    Install: uvx wake or pip install eth-wake.
    Invoked as subprocess via `wake detect all --json`.
    """

    name = "wake"
    cli = "wake"

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            (workspace / "contracts").mkdir(parents=True, exist_ok=True)
            (workspace / "contracts" / "Contract.sol").write_text(source, encoding="utf-8")

            code, stdout, stderr = await self._run_cli(
                args=["detect", "all", "--json"],
                cwd=workspace,
                timeout=180.0,
            )
            if code != 0:
                logger.warning("wake.failed", code=code, stderr=stderr[:500])
                return []

            try:
                detections = json.loads(stdout)
            except json.JSONDecodeError as e:
                logger.warning("wake.parse_failed", error=str(e))
                return []

            return list(self._parse(detections))

    def _parse(self, raw: dict) -> list[Finding]:
        findings: list[Finding] = []
        for det_name, det_items in (raw.get("detections") or {}).items():
            for it in det_items if isinstance(det_items, list) else []:
                sev_key = (it.get("impact") or it.get("severity") or "info").lower()
                sev = _WAKE_SEVERITY_MAP.get(sev_key, Severity.INFO)
                findings.append(
                    Finding(
                        id=f"wake:{det_name}:{len(findings)}",
                        title=it.get("message", det_name),
                        description=it.get("description", ""),
                        severity=sev,
                        source_engine=self.name,
                        file=it.get("file"),
                        line=it.get("start_line"),
                        confidence=0.8,
                    )
                )
        return findings
