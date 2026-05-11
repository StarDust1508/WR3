from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class FuzzInvariant:
    """One generated invariant — name, body, and the rationale used in prompts."""

    name: str  # e.g. "invariant_totalSupplyMatchesSumBalances"
    body: str  # Solidity body inside the function
    rationale: str
    severity_if_broken: Literal["info", "low", "medium", "high", "critical"] = "high"


@dataclass
class Counterexample:
    """One broken invariant captured by the fuzzer."""

    invariant_name: str
    call_trace: str  # multi-line text dump as the fuzzer printed it
    reason: str | None = None
    shrunk_calls: list[str] = field(default_factory=list)


@dataclass
class FuzzResult:
    """Outcome of one fuzz run against a set of invariants."""

    installed: bool
    engine: str  # "medusa" | "forge-invariant" | "skipped"
    runs: int
    duration_seconds: float
    counterexamples: list[Counterexample] = field(default_factory=list)
    raw_stdout: str = ""
    raw_stderr: str = ""

    @classmethod
    def not_installed(cls, engine: str = "skipped") -> FuzzResult:
        return cls(
            installed=False,
            engine=engine,
            runs=0,
            duration_seconds=0.0,
            counterexamples=[],
            raw_stdout="",
            raw_stderr="no fuzz engine on PATH",
        )
