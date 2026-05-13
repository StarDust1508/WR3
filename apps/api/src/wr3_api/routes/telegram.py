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

    web_base_url = str(request.base_url).rstrip("/")
    # Prefer NEXT_PUBLIC_SITE_URL when set — webhook host is the API host,
    # not the web host.
    site = (settings.model_extra or {}).get("next_public_site_url")
    if site:
        web_base_url = str(site).rstrip("/")

    reply = await handle_update(
        update,
        web_base_url=web_base_url,
        bot_token=settings.telegram_bot_token,
    )
    await execute_actions(reply.actions, bot_token=settings.telegram_bot_token)
    return {"ok": True}
