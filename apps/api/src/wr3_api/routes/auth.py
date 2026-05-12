"""Authentication endpoints.

  POST /v1/auth/tg/login    Validate Telegram WebApp initData → JWT
  GET  /v1/auth/me          Return current user (or 401 if no/invalid token)
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wr3_api.auth import current_user_required, issue_jwt
from wr3_api.config import get_settings
from wr3_api.models import User
from wr3_api.services import user_repository as user_repo
from wr3_api.telegram import InitDataError, parse_and_verify_initdata

logger = structlog.get_logger()
router = APIRouter()


class TelegramLoginRequest(BaseModel):
    init_data: str = Field(..., min_length=1, max_length=8192)


class LoginResponse(BaseModel):
    token: str
    user: dict[str, Any]


@router.post("/tg/login", response_model=LoginResponse)
async def telegram_login(req: TelegramLoginRequest) -> LoginResponse:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="telegram login not configured on this deployment",
        )
    try:
        tg_user = parse_and_verify_initdata(
            req.init_data, bot_token=settings.telegram_bot_token
        )
    except InitDataError as e:
        logger.info("auth.tg.invalid_initdata", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e)
        ) from e

    user = await user_repo.upsert_telegram_user(
        telegram_user_id=tg_user.id,
        telegram_username=tg_user.username,
        display_name=tg_user.display_name,
        avatar_url=tg_user.photo_url,
    )
    logger.info("auth.tg.login", user_id=str(user.id), tg_id=tg_user.id)

    token = issue_jwt(user.id)
    return LoginResponse(token=token, user=user_repo.user_to_dict(user))


@router.get("/me")
async def me(user: User = Depends(current_user_required)) -> dict[str, Any]:
    return user_repo.user_to_dict(user)


class PreferencesPatch(BaseModel):
    """Partial update of user feature toggles. Unknown keys are silently
    dropped server-side (no errors, no surprises)."""

    auto_poc: bool | None = None
    auto_fuzzing: bool | None = None
    multi_agent_triage: bool | None = None
    continuous_monitoring: bool | None = None
    anonymous_in_public: bool | None = None


@router.get("/preferences")
async def get_preferences(user: User = Depends(current_user_required)) -> dict[str, Any]:
    return user.preferences or {}


@router.patch("/preferences")
async def patch_preferences(
    patch: PreferencesPatch,
    user: User = Depends(current_user_required),
) -> dict[str, Any]:
    """Merge non-null fields of patch into user.preferences."""
    incoming = {k: v for k, v in patch.model_dump().items() if v is not None}
    if not incoming:
        return user.preferences or {}
    updated = await user_repo.update_preferences(user.id, incoming)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    logger.info("auth.preferences.updated", user_id=str(user.id), patch=incoming)
    return updated.preferences or {}
