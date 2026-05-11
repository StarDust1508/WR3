"""AI-driven invariant fuzzing — stage 5 of the audit pipeline.

Pipeline within the stage:
    1. InvariantGenerator: LLM proposes N invariant_*() functions for the target.
    2. FuzzRunner: runs the invariants with the best available engine
       (Medusa primary; forge invariant fallback). Graceful skip if no binary
       is on PATH.
    3. CounterexampleAnalyzer: for each broken invariant, LLM decides whether
       the counterexample exposes a real bug or is an artifact of a poorly
       specified invariant.
    4. FuzzingOrchestrator: glues it all and emits new Finding objects with
       source_engine="llm-fuzz-invariant".

Reference: TZ.md section 4.1 stage 5; tooling choices in section 5.7.
"""

from audit_engine.fuzzing.analyzer import AnalysisVerdict, CounterexampleAnalyzer
from audit_engine.fuzzing.invariant_gen import InvariantGenerator
from audit_engine.fuzzing.orchestrator import FuzzingOrchestrator
from audit_engine.fuzzing.runner import FuzzEngine, FuzzRunner
from audit_engine.fuzzing.types import Counterexample, FuzzInvariant, FuzzResult

__all__ = [
    "AnalysisVerdict",
    "Counterexample",
    "CounterexampleAnalyzer",
    "FuzzEngine",
    "FuzzInvariant",
    "FuzzResult",
    "FuzzRunner",
    "FuzzingOrchestrator",
    "InvariantGenerator",
]
