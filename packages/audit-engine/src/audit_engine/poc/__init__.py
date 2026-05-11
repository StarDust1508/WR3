"""Foundry PoC generation: stage 4 of the audit pipeline.

For each HIGH/CRITICAL finding, an LLM writes a Foundry test that attempts to
trigger the vulnerability. The runner compiles + executes via `forge test`, and
on revert/compile-error feeds the trace back to the LLM for up to
N retries. A successful test marks the finding as poc_validated=true and saves
the test source as an artifact.

License isolation: forge is MIT/Apache-2 dual-licensed; we invoke it as a
subprocess (no library linkage).
"""

from audit_engine.poc.artifacts import PoCArtifactStore
from audit_engine.poc.foundry_runner import ForgeTestResult, FoundryRunner
from audit_engine.poc.generator import PoCGenerator, PoCOutcome

__all__ = [
    "ForgeTestResult",
    "FoundryRunner",
    "PoCArtifactStore",
    "PoCGenerator",
    "PoCOutcome",
]
