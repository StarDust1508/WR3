"""Solodit API client.

Solodit (Cyfrin) aggregates audit findings from ToB / OZ / Sherlock / Code4rena
etc. The API surface is intentionally treated as best-effort: we degrade
gracefully if the endpoint is unavailable, returning empty context rather than
failing the audit pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()

_SOLODIT_BASE = "https://solodit.cyfrin.io/api"


@dataclass(frozen=True)
class SoloditEntry:
    """One normalized finding pulled from Solodit."""

    title: str
    severity: str
    body: str
    source_firm: str | None
    project: str | None
    url: str | None


class SoloditClient:
    """Async client. Stateless; safe to construct per-request."""

    def __init__(self, *, api_key: str | None = None, timeout: float = 12.0) -> None:
        self._api_key = api_key or os.getenv("SOLODIT_API_KEY", "")
        self._timeout = timeout

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=False,
    )
    async def search(self, query: str, *, limit: int = 5) -> list[SoloditEntry]:
        """Return up to `limit` relevant entries for the given free-text query."""
        if not query.strip():
            return []

        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        params = {"q": query[:512], "limit": str(limit)}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.get(
                    f"{_SOLODIT_BASE}/findings/search",
                    params=params,
                    headers=headers,
                )
            if r.status_code != 200:
                logger.info(
                    "solodit.non_200",
                    status=r.status_code,
                    body=r.text[:200] if r.text else "",
                )
                return []
            data = r.json()
        except httpx.HTTPError as e:
            logger.info("solodit.http_error", error=str(e))
            return []

        return list(self._parse(data, limit=limit))

    def _parse(self, data: dict | list, *, limit: int) -> list[SoloditEntry]:
        """Tolerant parser — Solodit's API shape may change; we only require
        title + severity + body fields, anything else is best-effort."""
        if isinstance(data, dict):
            items = data.get("results") or data.get("items") or data.get("data") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []

        out: list[SoloditEntry] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            out.append(
                SoloditEntry(
                    title=str(item.get("title") or item.get("name") or "")[:512],
                    severity=str(item.get("severity") or item.get("risk") or "unknown"),
                    body=str(item.get("body") or item.get("description") or "")[:4000],
                    source_firm=item.get("audit_firm") or item.get("firm"),
                    project=item.get("project") or item.get("protocol"),
                    url=item.get("url") or item.get("permalink"),
                )
            )
        return out
