"""User lookup + upsert by identity."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from wr3_api.db import SessionFactory
from wr3_api.models import User


async def upsert_telegram_user(
    *,
    telegram_user_id: int,
    telegram_username: str | None = None,
    display_name: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Find-or-create a User by TG id; update mutable fields on every hit."""
    async with SessionFactory() as session:
        row = (
            await session.execute(
                select(User).where(User.telegram_user_id == telegram_user_id)
            )
        ).scalar_one_or_none()

        if row is None:
            row = User(
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
                display_name=display_name,
                avatar_url=avatar_url,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return row

        changed = False
        if telegram_username and row.telegram_username != telegram_username:
            row.telegram_username = telegram_username
            changed = True
        if display_name and row.display_name != display_name:
            row.display_name = display_name
            changed = True
        if avatar_url and row.avatar_url != avatar_url:
            row.avatar_url = avatar_url
            changed = True

        if changed:
            await session.commit()
            await session.refresh(row)
        return row


async def get_user(user_id: uuid.UUID) -> User | None:
    async with SessionFactory() as session:
        return await session.get(User, user_id)


def user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "telegram_user_id": user.telegram_user_id,
        "telegram_username": user.telegram_username,
        "wallet_address": user.wallet_address,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "tier": user.tier,
        "preferences": user.preferences or {},
    }


async def update_preferences(
    user_id: uuid.UUID,
    patch: dict[str, Any],
) -> User | None:
    """Merge `patch` into user.preferences and persist.

    We never replace the full dict — only update provided keys — so the
    client can PATCH a single toggle without re-sending the rest.
    Returns the updated User, or None if user not found.
    """
    # Only allow known keys to be set; silently drop anything else.
    from wr3_api.models.user import DEFAULT_PREFERENCES

    allowed = {k: bool(v) for k, v in patch.items() if k in DEFAULT_PREFERENCES}

    async with SessionFactory() as session:
        row = await session.get(User, user_id)
        if row is None:
            return None
        merged = {**DEFAULT_PREFERENCES, **(row.preferences or {}), **allowed}
        row.preferences = merged
        # SQLAlchemy needs a hint that JSONB column changed when we
        # mutate-then-assign.
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(row, "preferences")
        await session.commit()
        await session.refresh(row)
        return row
