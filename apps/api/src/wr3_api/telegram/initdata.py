"""Telegram WebApp `initData` validator.

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

The Mini App provides a URL-encoded `initData` string. To validate:
  1. Parse keys; reserve the `hash` field separately.
  2. Build a data-check-string: sorted keys, lines "key=value".
  3. secret_key = HMAC_SHA256(bot_token, "WebAppData")
  4. expected = HMAC_SHA256(data_check_string, secret_key) in hex
  5. Compare to `hash` using constant-time equality.

We additionally enforce that `auth_date` is no older than 24 hours by default.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """Raised when initData is malformed, signed by a different bot, or stale."""


@dataclass(frozen=True)
class InitDataUser:
    """Subset of fields we use from initData['user'] JSON blob."""

    id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    photo_url: str | None
    language_code: str | None

    @classmethod
    def from_blob(cls, blob: dict) -> InitDataUser:
        return cls(
            id=int(blob["id"]),
            username=blob.get("username"),
            first_name=blob.get("first_name"),
            last_name=blob.get("last_name"),
            photo_url=blob.get("photo_url"),
            language_code=blob.get("language_code"),
        )

    @property
    def display_name(self) -> str:
        parts = [self.first_name, self.last_name]
        full = " ".join(p for p in parts if p)
        return full or (self.username or f"tg:{self.id}")


def parse_and_verify_initdata(
    raw: str,
    *,
    bot_token: str,
    max_age_seconds: int = 86400,
    now: float | None = None,
) -> InitDataUser:
    """Return the verified telegram user or raise InitDataError."""
    if not raw:
        raise InitDataError("empty initData")
    if not bot_token:
        raise InitDataError("bot token is not configured on the server")

    pairs = dict(parse_qsl(raw, keep_blank_values=True, strict_parsing=False))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash field")

    data_check_string = "\n".join(
        f"{k}={pairs[k]}" for k in sorted(pairs.keys())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        raise InitDataError("signature mismatch — initData was not signed by this bot")

    # auth_date may be missing in some edge cases (older clients) — be permissive.
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError as e:
        raise InitDataError("invalid auth_date") from e

    if auth_date > 0:
        current = now if now is not None else time.time()
        if current - auth_date > max_age_seconds:
            raise InitDataError("initData too old")

    user_json = pairs.get("user")
    if not user_json:
        raise InitDataError("missing user field")
    try:
        user_blob = json.loads(user_json)
    except json.JSONDecodeError as e:
        raise InitDataError("malformed user JSON") from e

    if "id" not in user_blob:
        raise InitDataError("user.id missing")

    return InitDataUser.from_blob(user_blob)
