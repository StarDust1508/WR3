"""Foundry subprocess wrapper.

Sets up a minimal forge project on disk:

    workspace/
        foundry.toml
        src/Contract.sol      <- target contract
        test/PoC.t.sol        <- LLM-generated exploit test

then runs `forge test --json -vv` and parses the JSON envelope into a
`ForgeTestResult`. Compile-fail and per-test revert reasons are surfaced
distinctly so the generator can decide what to feed back to the LLM.

If `forge` is not on PATH we return a "not_installed" result rather than
raising — the pipeline skips PoC for that finding.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger()


_FOUNDRY_TOML = """[profile.default]
src = "src"
out = "out"
libs = ["lib"]
test = "test"
solc_version = "0.8.24"
optimizer = true
optimizer_runs = 200
verbosity = 2
"""


@dataclass
class ForgeTestResult:
    """Outcome of one `forge test` invocation."""

    installed: bool
    compiled: bool
    passed: bool
    raw_stdout: str
    raw_stderr: str
    # When parsed JSON envelope is available:
    test_failures: list[str]  # human-readable failure messages
    revert_reason: str | None
    return_code: int

    @classmethod
    def not_installed(cls) -> ForgeTestResult:
        return cls(
            installed=False,
            compiled=False,
            passed=False,
            raw_stdout="",
            raw_stderr="forge not installed",
            test_failures=[],
            revert_reason=None,
            return_code=-127,
        )

    @property
    def short_diagnostic(self) -> str:
        """One-paragraph diagnostic suitable for feeding back to an LLM."""
        if not self.installed:
            return "forge binary not available on this host"
        if not self.compiled:
            # Compile error — surface stderr/stdout tail.
            tail = (self.raw_stderr or self.raw_stdout)[-1500:]
            return f"COMPILE ERROR (forge):\n{tail}"
        if self.passed:
            return "Test passed; exploit succeeded."
        joined = "\n".join(self.test_failures[:5])
        return f"TEST FAILED:\n{joined or self.raw_stdout[-1500:]}"


class FoundryRunner:
    """Subprocess wrapper around `forge`. Holds no state per call."""

    def __init__(self, *, timeout: float = 180.0, forge_bin: str = "forge") -> None:
        self.timeout = timeout
        self.forge_bin = forge_bin

    async def run(
        self,
        *,
        workspace: Path,
        target_source: str,
        test_source: str,
        target_filename: str = "Contract.sol",
        test_filename: str = "PoC.t.sol",
    ) -> ForgeTestResult:
        self._prepare_workspace(
            workspace=workspace,
            target_source=target_source,
            test_source=test_source,
            target_filename=target_filename,
            test_filename=test_filename,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                self.forge_bin,
                "test",
                "--json",
                "-vv",
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.info("foundry.not_installed", bin=self.forge_bin)
            return ForgeTestResult.not_installed()

        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return ForgeTestResult(
                installed=True,
                compiled=False,
                passed=False,
                raw_stdout="",
                raw_stderr="forge test timeout",
                test_failures=["timeout"],
                revert_reason=None,
                return_code=-1,
            )

        stdout = stdout_b.decode(errors="replace")
        stderr = stderr_b.decode(errors="replace")
        return self._parse(stdout=stdout, stderr=stderr, return_code=proc.returncode or 0)

    def _prepare_workspace(
        self,
        *,
        workspace: Path,
        target_source: str,
        test_source: str,
        target_filename: str,
        test_filename: str,
    ) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "foundry.toml").write_text(_FOUNDRY_TOML, encoding="utf-8")
        src = workspace / "src"
        src.mkdir(exist_ok=True)
        (src / target_filename).write_text(target_source, encoding="utf-8")
        test_dir = workspace / "test"
        test_dir.mkdir(exist_ok=True)
        (test_dir / test_filename).write_text(test_source, encoding="utf-8")

    @staticmethod
    def _parse(*, stdout: str, stderr: str, return_code: int) -> ForgeTestResult:
        # forge --json prints a single JSON object on stdout; compile errors
        # break that contract and surface as plain text on stderr.
        compiled = "Compiler run successful" in stdout or "Compiler run successful" in stderr
        passed_overall = True
        failures: list[str] = []
        revert: str | None = None

        try:
            payload = json.loads(stdout) if stdout.strip().startswith("{") else None
        except json.JSONDecodeError:
            payload = None

        if payload is None:
            # No JSON => either compile failed, or stdout had pre-amble.
            # Try to slice last JSON object.
            try:
                lb = stdout.rfind("{")
                rb = stdout.rfind("}")
                if 0 <= lb < rb:
                    payload = json.loads(stdout[lb : rb + 1])
            except (json.JSONDecodeError, ValueError):
                payload = None

        if payload is None:
            # No JSON => treat as not-compiled if return_code != 0.
            return ForgeTestResult(
                installed=True,
                compiled=compiled,
                passed=False,
                raw_stdout=stdout,
                raw_stderr=stderr,
                test_failures=[stderr.strip()[-500:]] if stderr.strip() else [],
                revert_reason=None,
                return_code=return_code,
            )

        compiled = True
        for _contract_path, suite in payload.items():
            test_results = suite.get("test_results") if isinstance(suite, dict) else None
            if not isinstance(test_results, dict):
                continue
            for test_name, result in test_results.items():
                status = result.get("status") if isinstance(result, dict) else None
                if status != "Success":
                    passed_overall = False
                    reason = (
                        result.get("reason")
                        or result.get("decoded_logs", [""])[-1]
                        or "no reason"
                    )
                    failures.append(f"{test_name}: {reason}")
                    if revert is None and isinstance(reason, str):
                        revert = reason

        return ForgeTestResult(
            installed=True,
            compiled=compiled,
            passed=passed_overall and bool(payload),
            raw_stdout=stdout,
            raw_stderr=stderr,
            test_failures=failures,
            revert_reason=revert,
            return_code=return_code,
        )
