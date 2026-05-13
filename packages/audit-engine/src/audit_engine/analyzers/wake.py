"""Wake (Ackee Blockchain) analyzer wrapper — ISC permissive, Python.

Repo: https://github.com/Ackee-Blockchain/wake  (v4.22.1 verified live)
Install: `uvx wake` or `pipx install eth-wake`.

CLI surface (4.x): `wake detect --export json all` writes
`<cwd>/.wake/detections.json` as a JSON array. Stdout is the ANSI-rendered
human report — NOT what we parse.

Schema per element (verified live on the Vuln contract):

    {
      "detector_name": "unchecked-return-value",
      "impact": "medium",     // lowercase: high|medium|low|warning|info
      "confidence": "medium",
      "uri": "https://ackee.xyz/wake/docs/...",
      "detection": {
        "message": "Unchecked return value",
        "location": {
          "relative_path": "src/Vuln.sol",
          "start_line": 27,
          "start_col": 9,
          "end_line": 27,
          "end_col": 50,
          "source": "..."          // the code snippet
        }
      },
      "suppressed": false
    }

License note: Wake is ISC permissive — we COULD import it as a library
without infecting our license. Keeping subprocess for now matches the
isolation pattern used for AGPL tools (Slither/Medusa) and avoids pulling
in Wake's heavy compile-time dependencies (eth-account, web3, etc.) into
audit-engine's own dependency tree.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog

from audit_engine.analyzers.base import StaticAnalyzer, detect_solc_version
from audit_engine.types import Finding, Severity

logger = structlog.get_logger()


# Wake emits lowercase impact strings. `warning` is bucketed as LOW so it
# doesn't bloat the LOW band — Wake uses it for ERC-4337 portability hints
# and similar non-critical advisories.
_WAKE_SEVERITY_MAP = {
    "high": Severity.HIGH,
    "medium": Severity.MEDIUM,
    "low": Severity.LOW,
    "warning": Severity.LOW,
    "info": Severity.INFO,
}

# Wake confidence is High/Medium/Low — convert to our 0-1 float scale.
_WAKE_CONFIDENCE_MAP = {
    "high": 0.85,
    "medium": 0.65,
    "low": 0.45,
}


class WakeAnalyzer(StaticAnalyzer):
    """Wake detector pass over a single-file workspace.

    Skips silently when `wake` isn't on PATH (base class catches
    FileNotFoundError). Compile errors inside Wake also produce empty
    output rather than raising — the pipeline survives missing tools.
    """

    name = "wake"
    cli = "wake"

    async def analyze(self, *, source: str) -> list[Finding]:
        with self._temp_dir() as td:
            workspace = Path(td)
            # Wake auto-discovers .sol files anywhere under the cwd; a flat
            # layout works. We put the file under `src/` to mirror the
            # other analyzers' workspaces and so `relative_path` in Wake's
            # output is `src/Contract.sol` (consistent with Aderyn).
            (workspace / "src").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "Contract.sol").write_text(source, encoding="utf-8")

            # `wake detect all --export json` writes to .wake/detections.json.
            # The `--export` flag goes on the PARENT `wake detect` group, then
            # `all` is the subcommand — order matters.
            env: dict[str, str] = {}
            solc_v = detect_solc_version(source)
            if solc_v:
                env["SOLC_VERSION"] = solc_v

            code, _stdout, stderr = await self._run_cli(
                args=["detect", "--export", "json", "all"],
                cwd=workspace,
                timeout=180.0,
                env=env or None,
            )

            report_path = workspace / ".wake" / "detections.json"
            if not report_path.exists():
                if code != -127:
                    logger.warning("wake.no_report", code=code, stderr=stderr[:400])
                return []

            try:
                raw = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("wake.parse_failed", error=str(e))
                return []

            findings = list(self._parse(raw))
            logger.info("wake.parsed", count=len(findings))
            return findings

    def _parse(self, raw: list | dict) -> list[Finding]:
        """Wake 4.x emits a top-level LIST. Legacy 3.x emitted a dict
        keyed by detector_name. We accept both — the dict form goes
        through a generic flattener — so an environment with an old
        Wake doesn't silently return zero findings.
        """
        items: list[dict] = []
        if isinstance(raw, list):
            items = [r for r in raw if isinstance(r, dict)]
        elif isinstance(raw, dict):
            for det_items in (raw.get("detections") or raw).values():
                if isinstance(det_items, list):
                    items.extend(r for r in det_items if isinstance(r, dict))

        findings: list[Finding] = []
        for it in items:
            if it.get("suppressed"):
                continue
            detector = str(it.get("detector_name") or "unknown")
            impact = str(it.get("impact") or "info").lower()
            sev = _WAKE_SEVERITY_MAP.get(impact, Severity.INFO)
            confidence = _WAKE_CONFIDENCE_MAP.get(
                str(it.get("confidence") or "").lower(), 0.6
            )

            detection = it.get("detection") or {}
            location = detection.get("location") or {}
            message = detection.get("message") or detector

            findings.append(
                Finding(
                    id=f"wake:{detector}:{len(findings)}",
                    title=message,
                    description=detection.get("message", "")
                    if not it.get("uri")
                    else f"{detection.get('message', '')}\n\nReference: {it.get('uri')}",
                    severity=sev,
                    source_engine=self.name,
                    file=location.get("relative_path"),
                    line=location.get("start_line"),
                    confidence=confidence,
                    metadata={
                        "detector": detector,
                        "wake_confidence": it.get("confidence"),
                        "wake_uri": it.get("uri"),
                    },
                )
            )
        return findings
