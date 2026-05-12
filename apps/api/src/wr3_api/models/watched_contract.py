"""Watched contract — one row per (user, address, network) being monitored.

Populated automatically by the scan worker when:
  1. A scan completes successfully (stage=done) AND
  2. The owning user has `preferences.continuous_monitoring = True`

A periodic Celery task re-fetches the verified source from Etherscan every
6 hours, sha256-hashes the SourceCode field, and DMs the user via the bot
when the hash changes. No LLM cost — pure Etherscan reads (free tier =
5 req/sec, 100k req/day).

When the user flips `continuous_monitoring` off, we leave the rows in the
table so flipping it back on resumes monitoring without losing history.
The task selects on `last_checked_at` — the prefs gate is enforced at
notify-time, not at iterate-time.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from wr3_api.models.base import Base, TimestampMixin


class WatchedContract(Base, TimestampMixin):
    __tablename__ = "watched_contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(String(128), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)

    # sha256 of Etherscan's SourceCode field on the last successful poll.
    # NULL on first insert — first poll establishes the baseline without
    # alerting (otherwise every newly-watched contract would alert once).
    last_source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Optional, when Etherscan returns an owner — currently we leave NULL,
    # owner detection via RPC slot reads is a follow-up.
    last_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)

    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Count of consecutive Etherscan errors. Used by the task to back off
    # noisy targets without removing them entirely.
    error_count: Mapped[int] = mapped_column(
        nullable=False, server_default=text("0")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "address", "network", name="ux_watch_user_addr_net"),
        Index("ix_watch_user", "user_id"),
        Index("ix_watch_checked", "last_checked_at"),
    )
