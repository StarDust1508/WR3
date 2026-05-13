from __future__ import annotations

import asyncio
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory

import structlog

from audit_engine.types import Finding

logger = structlog.get_logger()


# Solidity pragma → preferred solc version to use for crytic-compile-based
# tools (Slither, Wake). Mapping is intentionally conservative — we pin to
# the highest patch within the source's major-minor band that we know
# solc-select has installed locally / on the deploy box.
#
# When extending solc-select install list, add the version here too.
_PRAGMA_RE = re.compile(r"pragma\s+solidity\s+[\^>=<]*\s*(\d+\.\d+(?:\.\d+)?)", re.IGNORECASE)
_AVAILABLE_SOLC = ["0.4.25", "0.5.16", "0.8.20"]


def detect_solc_version(source: str) -> str | None:
    """Best-effort pick of an installed solc version that satisfies the
    contract's pragma. Returns None when no pragma is found — callers
    should let the tool's default resolution handle it.
    """
    match = _PRAGMA_RE.search(source)
    if not match:
        return None
    declared = match.group(1)
    parts = declared.split(".")
    major_minor = ".".join(parts[:2])
    for candidate in _AVAILABLE_SOLC:
        if candidate.startswith(major_minor + "."):
            return candidate
    return None


class StaticAnalyzer(ABC):
    """Base class for subprocess-based static analyzers.

    Each analyzer:
        - Has a unique `name` (used in Finding.source_engine)
        - Implements `analyze(source)` returning a list of Findings
        - Is responsible for parsing its CLI output and normalizing into Finding

    Subprocess isolation lets us include AGPL/GPL tools (Slither, Medusa, Halmos)
    without infecting our proprietary core.
    """

    name: str
    cli: str  # absolute path or PATH-resolvable command

    @abstractmethod
    async def analyze(self, *, source: str) -> list[Finding]:
        ...

    async def _run_cli(
        self,
        args: list[str],
        cwd: Path,
        timeout: float = 120.0,
        env: dict[str, str] | None = None,
    ) -> tuple[int, str, str]:
        """Run the subprocess and capture output.

        When `env` is given, those keys merge into the inherited environment
        — so callers can set SOLC_VERSION for crytic-compile-based tools
        without losing PATH and other ambient settings.
        """
        # We need to:
        #   - merge caller-provided env vars (e.g. SOLC_VERSION) into the
        #     inherited environment, so PATH and HOME still propagate.
        #   - REMOVE `VIRTUAL_ENV` when SOLC_VERSION is set: solc-select
        #     1.2.x looks for installed solc versions in
        #     `$VIRTUAL_ENV/.solc-select/` instead of `$HOME/.solc-select/`
        #     when VIRTUAL_ENV exists (constants.py line 6). Running under
        #     uv/poetry/venv sets VIRTUAL_ENV → solc-select can't find any
        #     installed versions → all crytic-compile-based tools fail.
        #     Stripping VIRTUAL_ENV makes solc-select fall back to HOME.
        process_env = None
        if env:
            base_env = dict(os.environ)
            if "SOLC_VERSION" in env and "VIRTUAL_ENV" in base_env:
                del base_env["VIRTUAL_ENV"]
            process_env = {**base_env, **env}
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli,
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
            )
        except FileNotFoundError:
            logger.info("analyzer.skipped.not_installed", engine=self.name, cli=self.cli)
            return -127, "", "not installed"

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            logger.warning("analyzer.timeout", engine=self.name, timeout=timeout)
            return -1, "", "timeout"

        return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")

    def _temp_dir(self) -> TemporaryDirectory:
        return TemporaryDirectory(prefix=f"wr3-{self.name}-")
