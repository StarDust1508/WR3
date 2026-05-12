from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wr3_api.models.base import Base, TimestampMixin

# Single source of truth for what a fresh user's preferences look like.
# Keep aligned with apps/api/alembic/versions/0003_user_preferences.py.
DEFAULT_PREFERENCES: dict[str, Any] = {
    "auto_poc": True,
    "auto_fuzzing": True,
    "multi_agent_triage": True,
    "continuous_monitoring": False,
    "anonymous_in_public": False,
}


class User(Base, TimestampMixin):
    """A user identified by ANY of telegram_user_id / wallet_address / email.

    All three are optional and uniqueness is enforced only when set (partial
    indexes). This keeps anonymous scans working — they have user_id=NULL —
    and lets a single human gradually attach more identities later.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    wallet_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free")

    # Owner-controlled feature toggles. Plain dict in Python; JSONB in PG so
    # we can add new toggles without a migration each time. The pipeline
    # reads these to decide which stages to skip.
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: dict(DEFAULT_PREFERENCES),
        server_default=text("'{}'::jsonb"),
    )
