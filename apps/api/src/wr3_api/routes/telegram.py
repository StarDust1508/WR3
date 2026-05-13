"""Telegram bot webhook.

Configured with a shared secret token; Telegram includes it in the
`X-Telegram-Bot-Api-Secret-Token` header. We compare in constant time.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from wr3_api.config import get_settings
from wr3_api.telegram.bot import execute_actions, handle_update

logger = structlog.get_logger()
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram bot is not configured",
        )

    expected = settings.telegram_webhook_secret
    if expected and x_telegram_bot_api_secret_token != expected:
        logger.warning("tg.webhook.bad_secret")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad secret")

    try:
        update = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"bad json: {e}") from e

    # Use the configured public web URL when set (NEXT_PUBLIC_SITE_URL env
    # → settings.next_public_site_url). The webhook hits the API host
    # (e.g. api.example.com / serveo tunnel), not the Mini App host, so
    # without this override every /tg/* link in bot DMs would 404.
    web_base_url = (
        settings.next_public_site_url.rstrip("/")
        if settings.next_public_site_url
        else str(request.base_url).rstrip("/")
    )

    reply = await handle_update(
        update,
        web_base_url=web_base_url,
        bot_token=settings.telegram_bot_token,
    )
    await execute_actions(reply.actions, bot_token=settings.telegram_bot_token)
    return {"ok": True}
