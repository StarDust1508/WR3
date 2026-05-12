"""Telegram initData HMAC validator."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from wr3_api.telegram.initdata import (
    InitDataError,
    parse_and_verify_initdata,
)

BOT_TOKEN = "1234567:TEST_TOKEN_FOR_HMAC"


def _sign(fields: dict[str, str], *, token: str = BOT_TOKEN) -> str:
    """Replicate Telegram's HMAC scheme to produce a valid initData payload."""
    data_check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields.keys()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    sig = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": sig})


def test_valid_initdata_returns_user() -> None:
    raw = _sign(
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps(
                {"id": 42, "first_name": "Ada", "last_name": "Lovelace", "username": "ada"}
            ),
            "query_id": "abc",
        }
    )
    user = parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)
    assert user.id == 42
    assert user.username == "ada"
    assert user.display_name == "Ada Lovelace"


def test_signature_mismatch_rejected() -> None:
    raw = _sign(
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"id": 1}),
        },
        token="wrong-token",
    )
    with pytest.raises(InitDataError, match="signature mismatch"):
        parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)


def test_missing_hash_rejected() -> None:
    raw = urlencode(
        {"auth_date": "0", "user": json.dumps({"id": 1})}
    )
    with pytest.raises(InitDataError, match="missing hash"):
        parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)


def test_stale_auth_date_rejected() -> None:
    raw = _sign(
        {
            "auth_date": "1",  # very old
            "user": json.dumps({"id": 1}),
        }
    )
    with pytest.raises(InitDataError, match="too old"):
        parse_and_verify_initdata(raw, bot_token=BOT_TOKEN, max_age_seconds=60)


def test_malformed_user_blob_rejected() -> None:
    raw = _sign(
        {
            "auth_date": str(int(time.time())),
            "user": "not a json",
        }
    )
    with pytest.raises(InitDataError, match="malformed user"):
        parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)


def test_user_without_id_rejected() -> None:
    raw = _sign(
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"username": "no-id"}),
        }
    )
    with pytest.raises(InitDataError, match=r"user\.id missing"):
        parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)


def test_empty_input_rejected() -> None:
    with pytest.raises(InitDataError, match="empty"):
        parse_and_verify_initdata("", bot_token=BOT_TOKEN)


def test_unconfigured_bot_token_rejected() -> None:
    with pytest.raises(InitDataError, match="not configured"):
        parse_and_verify_initdata("anything", bot_token="")


def test_username_only_fallback() -> None:
    raw = _sign(
        {
            "auth_date": str(int(time.time())),
            "user": json.dumps({"id": 7, "username": "anonymous"}),
        }
    )
    user = parse_and_verify_initdata(raw, bot_token=BOT_TOKEN)
    assert user.display_name == "anonymous"
