from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory

import structlog

from audit_engine.types import Finding

logger = structlog.get_logger()


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

    async def _run_cli(self, args: list[str], cwd: Path, timeout: float = 120.0) -> tuple[int, str, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self.cli,
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
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
