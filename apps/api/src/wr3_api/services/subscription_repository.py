"""Subscription persistence + tier resolution.

Invariants enforced here:
  - A subscription row is immutable once written. Extending a plan inserts a
    new row; refunds insert a row with period_end <= now() (cancelling).
  - `user.tier` is derived: it's set to the plan of the most-recent active row
    on activation, and reset to "free" by the periodic sweeper when nothing is
    active. We never write tier outside this file.
  - Idempotent: re-processing the same provider_payment_id is a no-op. Webhooks
    retry on 5xx, so this is load-bearing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import desc, select, update
from sqlalchemy.exc import IntegrityError

from wr3_api.db import SessionFactory
from wr3_api.models import Subscription, User
from wr3_api.models.subscription import PLAN_TO_TIER

logger = structlog.get_logger()

# 30 days per paid period. Calendar-month accounting (28/29/30/31) is not
# worth the complexity for an MVP with $29/$99/$499 tiers.
PERIOD_DAYS = 30


async def activate_from_payment(
    *,
    user_id: uuid.UUID,
    plan: str,
    provider: str,
    provider_payment_id: str,
    amount: int,
    currency: str,
    raw: dict[str, Any] | None = None,
) -> Subscription | None:
    """Record a successful payment and bump the user's tier.

    Returns the freshly-inserted Subscription, or None if this payment was
    already recorded (duplicate webhook). Callers should treat None as
    "already handled — succeed".
    """
    if plan not in PLAN_TO_TIER:
        logger.warning("sub.unknown_plan", plan=plan)
        return None

    now = datetime.now(UTC)
    async with SessionFactory() as session:
        # Period stacks on top of any existing active subscription so that a
        # renewal mid-period adds 30 days instead of resetting. If no active
        # row, start now.
        active_q = (
            select(Subscription.period_end)
            .where(Subscription.user_id == user_id)
            .where(Subscription.period_end > now)
            .order_by(desc(Subscription.period_end))
            .limit(1)
        )
        active_end = (await session.execute(active_q)).scalar_one_or_none()
        period_start = active_end or now
        period_end = period_start + timedelta(days=PERIOD_DAYS)

        sub = Subscription(
            user_id=user_id,
            plan=plan,
            provider=provider,
            provider_payment_id=provider_payment_id,
            amount=amount,
            currency=currency,
            period_start=period_start,
            period_end=period_end,
            raw=raw or {},
        )
        session.add(sub)
        try:
            await session.flush()
        except IntegrityError:
            # ux_subs_provider_payment kicked in — Telegram retried the webhook.
            await session.rollback()
            logger.info(
                "sub.duplicate_payment",
                provider=provider,
                provider_payment_id=provider_payment_id,
            )
            return None

        # Bump tier. The new plan wins even if a "higher" plan was active —
        # the user paid for `plan`, that's what they get going forward. We
        # don't try to be clever about merging $29 hobby into an active $99
        # team (Telegram won't sell you the same Stars invoice twice anyway
        # for the same intent).
        await session.execute(
            update(User).where(User.id == user_id).values(tier=PLAN_TO_TIER[plan])
        )
        await session.commit()
        await session.refresh(sub)
        logger.info(
            "sub.activated",
            user_id=str(user_id),
            plan=plan,
            provider=provider,
            period_end=period_end.isoformat(),
        )
        return sub


async def get_active_for_user(user_id: uuid.UUID) -> Subscription | None:
    """Most-recent subscription whose period hasn't ended yet."""
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        q = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.period_end > now)
            .order_by(desc(Subscription.period_end))
            .limit(1)
        )
        return (await session.execute(q)).scalar_one_or_none()


async def refund_active_subscription(user_id: uuid.UUID) -> Subscription | None:
    """Mark the current active subscription as refunded.

    Side effects:
      - Sets period_end to now() so `get_active_for_user` returns None.
      - Resets user.tier to "free".
    Returns the refunded Subscription (with new period_end) or None if the
    user has no active subscription.

    The actual Telegram-side refund (`refundStarPayment` API call) must be
    issued by the caller — typically the bot handler — BEFORE invoking
    this function. We split the concerns so this module stays purely DB.
    """
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        active = (
            await session.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .where(Subscription.period_end > now)
                .order_by(desc(Subscription.period_end))
                .limit(1)
            )
        ).scalar_one_or_none()
        if active is None:
            return None
        active.period_end = now
        await session.execute(
            update(User).where(User.id == user_id).values(tier="free")
        )
        await session.commit()
        await session.refresh(active)
        logger.info("sub.refunded", user_id=str(user_id), plan=active.plan)
        return active


def subscription_to_dict(sub: Subscription | None) -> dict[str, Any]:
    """Public-safe serialization. `raw` is owner-only and stripped here."""
    if sub is None:
        return {"active": False, "plan": "free", "period_end": None}
    return {
        "active": True,
        "plan": sub.plan,
        "provider": sub.provider,
        "period_start": sub.period_start.isoformat(),
        "period_end": sub.period_end.isoformat(),
        "amount": sub.amount,
        "currency": sub.currency,
    }


async def sweep_expired_subscriptions() -> dict[str, int]:
    """Downgrade users whose last paid subscription has expired.

    Run periodically (every hour via Celery beat) to keep `user.tier` in
    sync with reality. Without this, a user who paid for hobby 30 days
    ago still has `user.tier="hobby"` in the DB even though the period
    ended — they'd keep hitting the 10/month hobby quota despite their
    subscription being over.

    Logic:
        For each user whose tier != "free":
          - Find their MAX(period_end) across all subscriptions.
          - If max_end < now → downgrade to free.
          - If max_end >= now → keep current tier (subscription extended
            via renewal purchase before expiry).

    Returns counters dict for telemetry / beat-log inspection.

    Idempotent — safe to run on a schedule; users already at "free" or
    with active periods are not touched.
    """
    from sqlalchemy import func, select, update

    from wr3_api.models import User

    now = datetime.now(UTC)
    stats = {"checked": 0, "downgraded": 0, "still_active": 0, "no_subs": 0}

    async with SessionFactory() as session:
        # Find every paid user. "free" users have nothing to sweep, and
        # there's typically <1% of users in that bucket, so this is a
        # cheap selective scan.
        paid_users = (
            await session.execute(select(User).where(User.tier != "free"))
        ).scalars().all()

        stats["checked"] = len(paid_users)

        for user in paid_users:
            # MAX(period_end) for this user across all their subscriptions.
            # Could be None if they never had any (shouldn't happen — paid
            # tier without subs means data drift — but defensive).
            row = (
                await session.execute(
                    select(func.max(Subscription.period_end)).where(
                        Subscription.user_id == user.id
                    )
                )
            ).first()
            max_end: datetime | None = row[0] if row else None

            if max_end is None:
                # Paid tier but no subscription rows — likely manual data
                # entry or a bug. Downgrade so it self-corrects.
                stats["no_subs"] += 1
                user.tier = "free"
                logger.warning(
                    "sub.sweep.no_subs_paid_tier_drift", user_id=str(user.id)
                )
                continue

            if max_end < now:
                stats["downgraded"] += 1
                logger.info(
                    "sub.sweep.expired",
                    user_id=str(user.id),
                    prev_tier=user.tier,
                    period_end=max_end.isoformat(),
                )
                user.tier = "free"
            else:
                stats["still_active"] += 1

        if stats["downgraded"] or stats["no_subs"]:
            await session.commit()

    logger.info("sub.sweep.done", **stats)
    return stats
