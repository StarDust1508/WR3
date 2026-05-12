"""Subscription — one row per paid period for a user.

We do NOT mutate this row to extend a plan; we insert a new one and let the
"active subscription" be defined as MAX(period_end) WHERE period_end > now().
This gives us an immutable payment history without a separate ledger.

Telegram Stars is the only provider for now (free, no card needed, native to
the bot/Mini App audience). TON Connect / Stripe slot in by adding new
`provider` values; the rest of the API is provider-agnostic.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from wr3_api.models.base import Base, TimestampMixin


# Plan → tier mapping. Keep aligned with apps/web/app/pricing/page.tsx.
PLAN_TO_TIER: dict[str, str] = {
    "hobby": "hobby",
    "team": "team",
    "pro": "pro",
    # Enterprise is sold per-engagement; never bought via Stars.
}

# Plan price in Telegram Stars (XTR).
# Stars-to-USD ≈ $0.013 each (Telegram's posted developer rate as of 2026-05).
# We round to a tidy XTR figure that's also defensible at our marketing prices.
#   hobby  $29  ≈ 2200 ⭐  (we use 2200)
#   team   $99  ≈ 7500 ⭐  (we use 7500)
#   pro    $499 ≈ 38000 ⭐ (we use 38000)
STARS_PRICE: dict[str, int] = {
    "hobby": 2200,
    "team": 7500,
    "pro": 38000,
}


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # "telegram_stars", "ton", "stripe"
    # Provider's own payment id. For Stars this is `telegram_payment_charge_id`,
    # which we need if we ever want to refund via `refundStarPayment`.
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # smallest unit (XTR / cents / lamports)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)  # "XTR", "USD", "TON"

    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Raw provider event for audit / debugging. Never read by business logic.
    raw: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        # Idempotency: the same provider payment can't be recorded twice
        # (webhooks retry on 5xx). Composite with provider so two different
        # rails can't collide on a shared id space.
        Index(
            "ux_subs_provider_payment",
            "provider",
            "provider_payment_id",
            unique=True,
        ),
        # Fast lookup of "active subscription for user" without a full scan.
        Index("ix_subs_user_period_end", "user_id", "period_end"),
    )
