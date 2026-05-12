"""JWT roundtrip + decode edge cases."""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

from jose import jwt

from wr3_api.auth import _ALGORITHM, decode_jwt, issue_jwt
from wr3_api.config import get_settings


def test_jwt_roundtrip() -> None:
    uid = uuid.uuid4()
    token = issue_jwt(uid)
    assert decode_jwt(token) == uid


def test_jwt_with_invalid_signature() -> None:
    uid = uuid.uuid4()
    token = jwt.encode({"sub": str(uid), "exp": int(time.time()) + 60}, "wrong", algorithm=_ALGORITHM)
    assert decode_jwt(token) is None


def test_jwt_expired() -> None:
    uid = uuid.uuid4()
    token = issue_jwt(uid, ttl=timedelta(seconds=-10))
    assert decode_jwt(token) is None


def test_jwt_no_sub() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"exp": int(time.time()) + 60}, settings.nextauth_secret, algorithm=_ALGORITHM
    )
    assert decode_jwt(token) is None


def test_jwt_garbage() -> None:
    assert decode_jwt("not-a-jwt") is None


def test_jwt_non_uuid_sub() -> None:
    settings = get_settings()
    token = jwt.encode(
        {"sub": "not-a-uuid", "exp": int(time.time()) + 60},
        settings.nextauth_secret,
        algorithm=_ALGORITHM,
    )
    assert decode_jwt(token) is None
