"""Telegram bot + Mini App integration.

Two entry points share one User model:
    1. Telegram bot — receives webhook updates and reacts to /start, /scan etc.
    2. Mini App — runs inside Telegram, ships initData on first call which we
       validate via HMAC against the bot token, returning a JWT.

Both flows route through `services.user_repository.upsert_telegram_user` and
the same `enqueue_scan` path the web API uses. No bot-specific pipeline.
"""

from wr3_api.telegram.initdata import (
    InitDataError,
    InitDataUser,
    parse_and_verify_initdata,
)

__all__ = ["InitDataError", "InitDataUser", "parse_and_verify_initdata"]
