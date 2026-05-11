"""LLM router: chooses provider by sensitivity and routes to OpenAI-compatible APIs.

Sensitivity model:
    LOW    — UI text, coding glue. NavyAI is fine.
    MEDIUM — public-ish reasoning, RAG context. OpenRouter without ZDR.
    HIGH   — security findings, PoC exploit code. OpenRouter with zdr:true.
    SECRET — raw 0-days, client-specific data. Local Qwen only, no network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


class Sensitivity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    SECRET = "secret"


@dataclass
class LLMRequest:
    messages: list[dict[str, Any]]
    sensitivity: Sensitivity = Sensitivity.MEDIUM
    model_hint: str | None = None  # provider-relative ID, e.g. "anthropic/claude-sonnet-4.6"
    temperature: float = 0.2
    max_tokens: int = 4096


class LLMRouter:
    """Routes LLM calls to provider chosen by sensitivity."""

    def __init__(
        self,
        *,
        openrouter_key: str | None = None,
        navyai_key: str | None = None,
        local_url: str = "http://localhost:8000/v1",
        local_model: str = "Qwen/Qwen3-Coder-30B-A3B-Instruct",
    ) -> None:
        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY", "")
        self.navyai_key = navyai_key or os.getenv("NAVYAI_API_KEY", "")
        self.local_url = local_url.rstrip("/")
        self.local_model = local_model

    async def complete(self, req: LLMRequest) -> str:
        provider, model, base_url, key, extra = self._select(req)
        logger.info("llm.dispatch", provider=provider, model=model, sensitivity=req.sensitivity)

        return await self._call_openai_compatible(
            base_url=base_url,
            key=key,
            model=model,
            messages=req.messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            extra=extra,
        )

    def _select(
        self, req: LLMRequest
    ) -> tuple[str, str, str, str | None, dict[str, Any]]:
        if req.sensitivity == Sensitivity.SECRET:
            return ("local", self.local_model, self.local_url, None, {})

        if req.sensitivity == Sensitivity.HIGH:
            return (
                "openrouter-zdr",
                req.model_hint or "anthropic/claude-sonnet-4.6",
                "https://openrouter.ai/api/v1",
                self.openrouter_key,
                {"transforms": [], "route": "fallback", "zdr": True},
            )

        if req.sensitivity == Sensitivity.MEDIUM:
            return (
                "openrouter",
                req.model_hint or "anthropic/claude-sonnet-4.6",
                "https://openrouter.ai/api/v1",
                self.openrouter_key,
                {},
            )

        return (
            "navyai",
            req.model_hint or "claude-sonnet-4.6",
            "https://api.navy/v1",
            self.navyai_key,
            {},
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _call_openai_compatible(
        self,
        *,
        base_url: str,
        key: str | None,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any],
    ) -> str:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **extra,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
