"""LLM router — multi-provider with ZDR enforcement for security work.

Per TZ.md §5.5:
    - OpenRouter (zdr:true) for security PoC / raw findings
    - api.navy (NavyAI) for UI / coding-glue (retention not critical)
    - Local Qwen3-Coder 30B-A3B via vLLM for most sensitive (no network)
    - Gemini embeddings for RAG
"""

from audit_engine.llm.router import (
    AllProvidersExhaustedError,
    LLMRequest,
    LLMRouter,
    Sensitivity,
)

__all__ = ["AllProvidersExhaustedError", "LLMRequest", "LLMRouter", "Sensitivity"]
