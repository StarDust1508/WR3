"""External knowledge sources used to inform LLM triage and reasoning.

Per TZ.md section 4.3:
    - Solodit API (Cyfrin, 50K+ findings) — primary RAG source
    - DeFiHackLabs (Foundry PoCs)
    - Sealevel-attacks (Solana golden dataset)
    - SWC Registry (taxonomy)

This subpackage exposes lightweight clients that fetch context on demand.
Heavy ingestion (offline embedding of large corpora) lives in a separate
worker — not in the request path.
"""

from audit_engine.knowledge.solodit import SoloditClient, SoloditEntry

__all__ = ["SoloditClient", "SoloditEntry"]
