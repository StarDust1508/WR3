"""Auth helpers: JWT issue + FastAPI dependencies.

JWT carries the wr3 user_id only; everything else is reloaded from DB on each
request. Tokens have a 30-day expiry by default — Mini Apps cache them in
sessionStorage and can refresh by re-running initData login.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from wr3_api.config import get_settings
from wr3_api.models import User
from wr3_api.services import user_repository as user_repo

_ALGORITHM = "HS256"
_DEFAULT_TTL = timedelta(days=30)

_bearer = HTTPBearer(auto_error=False)


def issue_jwt(user_id: uuid.UUID, *, ttl: timedelta = _DEFAULT_TTL) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "iss": "wr3",
    }
    return jwt.encode(payload, settings.nextauth_secret, algorithm=_ALGORITHM)


def decode_jwt(token: str) -> uuid.UUID | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.nextauth_secret, algorithms=[_ALGORITHM])
    except JWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except (ValueError, TypeError):
        return None


async def current_user_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    """Returns the User or None — used for endpoints that allow anonymous calls."""
    if creds is None:
        return None
    user_id = decode_jwt(creds.credentials)
    if user_id is None:
        return None
    return await user_repo.get_user(user_id)


async def current_user_required(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Returns the User or raises 401."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_jwt(creds.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await user_repo.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user
