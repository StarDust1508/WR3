"""LLM router: dispatches calls to a provider chosen by sensitivity.

Sensitivity policy (honest, not aspirational):
    LOW     — UI text, coding-glue prompts. api.navy is fine.
    MEDIUM  — public-ish reasoning, dedup, code-explainer.
              api.navy. Retention NOT confirmed zero, but no client
              secrets pass through.
    HIGH    — security analysis of public on-chain contracts.
              Default: api.navy with metadata.zdr=False. NavyAI is a
              reseller proxy and we do not assert ZDR. If
              OPENROUTER_API_KEY is configured we route through
              OpenRouter `data_collection: 'deny'` instead, which is
              their documented zero-retention switch.
    SECRET  — raw 0-day exploits / private client repos. NEVER hit
              api.navy/OpenRouter. Local Qwen3-Coder via vLLM at
              LOCAL_LLM_URL is the only acceptable destination. If
              local LLM is not configured we raise rather than
              degrade silently.

The completion result is opaque text; the policy metadata (which provider
was used, whether ZDR was claimed) is exposed via `last_provider` for the
caller to thread into Finding.metadata.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
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
    model_hint: str | None = None
    temperature: float = 0.2
    max_tokens: int = 4096


@dataclass
class ProviderDecision:
    """Which provider/model the router picked and what guarantees apply.

    Threaded into Finding.metadata via `LLMRouter.last_provider`.
    """

    name: str  # "navyai" | "openrouter" | "local-vllm"
    model: str
    base_url: str
    zdr_claimed: bool
    extra: dict[str, Any] = field(default_factory=dict)


class LocalLLMUnavailableError(RuntimeError):
    """Raised when Sensitivity.SECRET is requested but no local LLM is configured."""


class LLMRouter:
    """Provider-routing LLM client. No silent ZDR claims."""

    def __init__(
        self,
        *,
        navyai_key: str | None = None,
        navyai_base_url: str | None = None,
        navyai_default_model: str | None = None,
        navyai_cheap_model: str | None = None,
        openrouter_key: str | None = None,
        openrouter_base_url: str | None = None,
        local_url: str | None = None,
        local_model: str | None = None,
    ) -> None:
        self.navyai_key = navyai_key or os.getenv("NAVYAI_API_KEY", "")
        self.navyai_base_url = navyai_base_url or os.getenv(
            "NAVYAI_BASE_URL", "https://api.navy/v1"
        )
        self.navyai_default_model = navyai_default_model or os.getenv(
            "NAVYAI_DEFAULT_MODEL", "gpt-5.3-codex"
        )
        self.navyai_cheap_model = navyai_cheap_model or os.getenv(
            "NAVYAI_CHEAP_MODEL", "gpt-4o-mini"
        )

        self.openrouter_key = openrouter_key or os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_base_url = openrouter_base_url or os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )

        self.local_url = (local_url or os.getenv("LOCAL_LLM_URL", "")).rstrip("/")
        self.local_model = local_model or os.getenv(
            "LOCAL_LLM_MODEL", "Qwen/Qwen3-Coder-30B-A3B-Instruct"
        )

        self.last_provider: ProviderDecision | None = None

    async def complete(self, req: LLMRequest) -> str:
        decision = self._select(req)
        self.last_provider = decision

        logger.info(
            "llm.dispatch",
            provider=decision.name,
            model=decision.model,
            sensitivity=req.sensitivity.value,
            zdr=decision.zdr_claimed,
        )

        return await self._call_openai_compatible(
            base_url=decision.base_url,
            key=self._key_for(decision),
            model=decision.model,
            messages=req.messages,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            extra=decision.extra,
        )

    # --- selection ----------------------------------------------------------

    def _select(self, req: LLMRequest) -> ProviderDecision:
        if req.sensitivity == Sensitivity.SECRET:
            if not self.local_url:
                raise LocalLLMUnavailableError(
                    "Sensitivity.SECRET requires LOCAL_LLM_URL. Refusing to "
                    "route private client data through a third-party proxy."
                )
            return ProviderDecision(
                name="local-vllm",
                model=req.model_hint or self.local_model,
                base_url=self.local_url,
                zdr_claimed=True,
            )

        if req.sensitivity == Sensitivity.HIGH and self.openrouter_key:
            # OpenRouter documents a `data_collection: "deny"` provider preference
            # for zero retention. See https://openrouter.ai/docs/features/privacy
            return ProviderDecision(
                name="openrouter",
                model=req.model_hint or "anthropic/claude-sonnet-4.6",
                base_url=self.openrouter_base_url,
                zdr_claimed=True,
                extra={"provider": {"data_collection": "deny"}},
            )

        if req.sensitivity in (Sensitivity.HIGH, Sensitivity.MEDIUM):
            return ProviderDecision(
                name="navyai",
                model=req.model_hint or self.navyai_default_model,
                base_url=self.navyai_base_url,
                # NavyAI does NOT confirm zero-retention. We do not claim it.
                zdr_claimed=False,
            )

        # LOW
        return ProviderDecision(
            name="navyai",
            model=req.model_hint or self.navyai_cheap_model,
            base_url=self.navyai_base_url,
            zdr_claimed=False,
        )

    def _key_for(self, decision: ProviderDecision) -> str | None:
        if decision.name == "navyai":
            return self.navyai_key
        if decision.name == "openrouter":
            return self.openrouter_key
        return None  # local vLLM is keyless

    # --- HTTP ---------------------------------------------------------------

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

        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]

    # --- embeddings ---------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def embed(
        self,
        text: str,
        *,
        model: str = "text-embedding-3-small",
    ) -> list[float]:
        """Embed a single string via api.navy (OpenAI-compatible /embeddings).

        Always goes through api.navy regardless of sensitivity — embeddings
        are non-reversible and we only ever embed public incident text here.
        If you need to embed sensitive data, add a SECRET-routed variant.
        """
        results = await self.embed_batch([text], model=model)
        return results[0]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    )
    async def embed_batch(
        self,
        texts: list[str],
        *,
        model: str = "text-embedding-3-small",
    ) -> list[list[float]]:
        """Embed many strings in one API call.

        OpenAI's /embeddings endpoint accepts `input` as either a string or
        a list of strings — api.navy mirrors this. One round-trip is dramatically
        cheaper than N when called from a scan worker that has many findings
        to enrich. Results are returned in the SAME ORDER as `texts`.
        """
        if not self.navyai_key:
            raise RuntimeError("embed_batch() requires NAVYAI_API_KEY to be configured")
        if not texts:
            return []
        headers = {
            "Authorization": f"Bearer {self.navyai_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "input": texts}
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                f"{self.navyai_base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
        # The response `data` array is ordered by `index`; sort defensively
        # in case the provider ever returns out-of-order.
        rows = sorted(data["data"], key=lambda d: d["index"])
        return [list(row["embedding"]) for row in rows]
