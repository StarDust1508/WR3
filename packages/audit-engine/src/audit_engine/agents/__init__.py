"""Multi-agent triage layer — Trident Arena pattern.

Four parallel agents over the same set of raw findings:
    - SeverityClassifier  — assigns severity ranks
    - FalsePositiveFilter — reads context, dismisses pattern-only matches
    - BusinessLogicReasoner — looks for logical bugs not patterns
    - CrossContractAnalyzer — checks inter-contract interactions

Consensus layer reduces FP rate. Reference: Trident Arena (Ackee) achieved
70% recall on 30 known Solana CVEs with FP rate 26% (vs 86% on plain AI).
"""

from audit_engine.agents.triage import TriageOrchestrator

__all__ = ["TriageOrchestrator"]
