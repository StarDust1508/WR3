"""Fuzz runner: medusa primary, forge invariant fallback.

Both wrappers operate on the same minimal workspace layout used by the PoC
stage:
    workspace/
        foundry.toml
        src/Contract.sol      <- target
        test/Invariant.t.sol  <- harness with all invariants

If neither binary is installed we return FuzzResult.not_installed() and the
pipeline skips this stage. We never crash the pipeline on a missing tool.
"""

from __future__ import annotations

import asyncio
import re
import time
from enum import StrEnum
from pathlib import Path

import structlog

from audit_engine.fuzzing.types import Counterexample, FuzzInvariant, FuzzResult

logger = structlog.get_logger()


_FOUNDRY_TOML = """[profile.default]
src = "src"
out = "out"
libs = ["lib"]
test = "test"
solc_version = "0.8.24"
optimizer = true
optimizer_runs = 200

[invariant]
runs = 64
depth = 32
fail_on_revert = false
"""


class FuzzEngine(StrEnum):
    MEDUSA = "medusa"
    FORGE = "forge-invariant"
    AUTO = "auto"


class FuzzRunner:
    """Picks the best installed fuzzer and runs against generated invariants."""

    def __init__(
        self,
        *,
        timeout: float = 240.0,
        engine: FuzzEngine = FuzzEngine.AUTO,
        medusa_bin: str = "medusa",
        forge_bin: str = "forge",
    ) -> None:
        self.timeout = timeout
        self.engine = engine
        self.medusa_bin = medusa_bin
        self.forge_bin = forge_bin

    async def run(
        self,
        *,
        workspace: Path,
        target_source: str,
        invariants: list[FuzzInvariant],
    ) -> FuzzResult:
        if not invariants:
            return FuzzResult.not_installed("no-invariants")

        self._prepare_workspace(
            workspace=workspace,
            target_source=target_source,
            invariants=invariants,
        )

        engines = self._engines_to_try()
        for engine in engines:
            available = await self._is_installed(engine)
            if not available:
                continue
            return await self._run_engine(engine=engine, workspace=workspace)
        return FuzzResult.not_installed()

    # --- engine selection -----------------------------------------------------

    def _engines_to_try(self) -> list[FuzzEngine]:
        if self.engine == FuzzEngine.MEDUSA:
            return [FuzzEngine.MEDUSA]
        if self.engine == FuzzEngine.FORGE:
            return [FuzzEngine.FORGE]
        return [FuzzEngine.MEDUSA, FuzzEngine.FORGE]

    async def _is_installed(self, engine: FuzzEngine) -> bool:
        cmd = self.medusa_bin if engine == FuzzEngine.MEDUSA else self.forge_bin
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd,
                "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return False
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return False
        return proc.returncode == 0

    # --- workspace prep -------------------------------------------------------

    def _prepare_workspace(
        self,
        *,
        workspace: Path,
        target_source: str,
        invariants: list[FuzzInvariant],
    ) -> None:
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "foundry.toml").write_text(_FOUNDRY_TOML, encoding="utf-8")

        src_dir = workspace / "src"
        src_dir.mkdir(exist_ok=True)
        (src_dir / "Contract.sol").write_text(target_source, encoding="utf-8")

        test_dir = workspace / "test"
        test_dir.mkdir(exist_ok=True)
        harness = _build_harness(invariants)
        (test_dir / "Invariant.t.sol").write_text(harness, encoding="utf-8")

    # --- engine runners -------------------------------------------------------

    async def _run_engine(self, *, engine: FuzzEngine, workspace: Path) -> FuzzResult:
        started = time.monotonic()
        if engine == FuzzEngine.MEDUSA:
            stdout, stderr, _rc = await self._run_subprocess(
                [self.medusa_bin, "fuzz", "--no-color"],
                workspace=workspace,
            )
        else:
            stdout, stderr, _rc = await self._run_subprocess(
                [
                    self.forge_bin,
                    "test",
                    "--match-contract",
                    "InvariantHarness",
                    "-vvv",
                ],
                workspace=workspace,
            )
        duration = time.monotonic() - started

        ces = _parse_counterexamples(engine=engine, stdout=stdout, stderr=stderr)
        return FuzzResult(
            installed=True,
            engine=engine.value,
            runs=_extract_runs(stdout),
            duration_seconds=duration,
            counterexamples=ces,
            raw_stdout=stdout,
            raw_stderr=stderr,
        )

    async def _run_subprocess(
        self, argv: list[str], *, workspace: Path
    ) -> tuple[str, str, int]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return "", "binary not found", -127

        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "fuzz timeout", -1
        return out_b.decode(errors="replace"), err_b.decode(errors="replace"), proc.returncode or 0


# --- harness builder ---------------------------------------------------------


_HARNESS_TEMPLATE = """// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/Contract.sol";

/// @title wr3 AI-generated invariant harness
contract InvariantHarness is Test {{
    /// Replace `Contract` with the actual contract name if needed.
    // address target;

    function setUp() public {{
        // Auto-generated: caller may override target deployment as needed.
    }}

{invariants}
}}
"""


def _build_harness(invariants: list[FuzzInvariant]) -> str:
    body_lines: list[str] = []
    for inv in invariants:
        body_lines.append(
            f"    /// {inv.rationale}\n"
            f"    function {inv.name}() public {{\n"
            f"{_indent(inv.body, 8)}\n"
            f"    }}\n"
        )
    return _HARNESS_TEMPLATE.format(invariants="\n".join(body_lines))


def _indent(text: str, n: int) -> str:
    pad = " " * n
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


# --- counterexample parsing --------------------------------------------------


_FORGE_FAIL = re.compile(
    r"\[FAIL[^]]*\]\s+(invariant_\w+)\s*\(\)\s*(?:.*?\n)((?:.*?\n){0,40})",
    re.DOTALL,
)
_MEDUSA_FAIL = re.compile(
    r"invariant\s+\"?(invariant_\w+)\"?\s+(?:failed|broken)[^\n]*\n((?:.*?\n){0,40})",
    re.IGNORECASE | re.DOTALL,
)
_RUNS_LINE = re.compile(r"(?:runs|fuzz_runs)\s*[:=]\s*(\d+)", re.IGNORECASE)


def _parse_counterexamples(*, engine: FuzzEngine, stdout: str, stderr: str) -> list[Counterexample]:
    text = stdout + "\n" + stderr
    pattern = _MEDUSA_FAIL if engine == FuzzEngine.MEDUSA else _FORGE_FAIL

    out: list[Counterexample] = []
    seen: set[str] = set()
    for m in pattern.finditer(text):
        name = m.group(1)
        if name in seen:
            continue
        seen.add(name)
        trace = (m.group(2) or "").strip()
        reason = _first_line(trace) or None
        out.append(
            Counterexample(invariant_name=name, call_trace=trace, reason=reason)
        )
    return out


def _first_line(s: str) -> str:
    for line in s.splitlines():
        if line.strip():
            return line.strip()
    return ""


def _extract_runs(stdout: str) -> int:
    m = _RUNS_LINE.search(stdout)
    if not m:
        return 0
    try:
        return int(m.group(1))
    except ValueError:
        return 0
