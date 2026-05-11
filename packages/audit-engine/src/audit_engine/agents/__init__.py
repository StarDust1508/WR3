"""Multi-agent triage layer.

Two flavors:
    - TriageOrchestrator (triage.py): single LLM call, cheaper, simpler.
    - MultiAgentTriage (multi_agent.py): 4 parallel agents + consensus,
      matches Trident Arena pattern. Default for production.
"""

from audit_engine.agents.multi_agent import MultiAgentTriage
from audit_engine.agents.triage import TriageOrchestrator

__all__ = ["MultiAgentTriage", "TriageOrchestrator"]
