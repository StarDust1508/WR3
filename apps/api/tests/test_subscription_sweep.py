"""Tier-expiry sweeper — hourly Celery task that downgrades
`user.tier` back to "free" once their last paid period has ended.

DB-touching: we use the live local Postgres (same as other api tests)
to avoid mocking SQLAlchemy. Each test creates a fresh user + (optional)
subscription rows and cleans up after itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete

from wr3_api.db import SessionFactory
from wr3_api.models import Subscription, User
from wr3_api.services.subscription_repository import sweep_expired_subscriptions


def _stars_charge_id() -> str:
    """provider_payment_id is uniqued on (provider, charge_id) — use a
    fresh UUID per row so concurrent tests don't collide."""
    return f"test_{uuid.uuid4().hex}"


@pytest.fixture
async def _cleanup_users():
    """Track which user_ids the test created and delete them at teardown
    so they don't accumulate in the local DB."""
    created: list[uuid.UUID] = []
    yield created
    if not created:
        return
    async with SessionFactory() as session:
        await session.execute(
            delete(Subscription).where(Subscription.user_id.in_(created))
        )
        await session.execute(delete(User).where(User.id.in_(created)))
        await session.commit()


async def _make_user_with_sub(
    tier: str,
    *,
    sub_end_offset: timedelta | None,
) -> uuid.UUID:
    """Create a User at the given tier, optionally with a subscription
    row whose period_end is now + offset (None = no subscription row)."""
    user = User(tier=tier, telegram_user_id=int(uuid.uuid4().int % 2_000_000_000))
    async with SessionFactory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
        if sub_end_offset is not None:
            now = datetime.now(UTC)
            sub = Subscription(
                user_id=user.id,
                plan=tier,
                provider="telegram_stars",
                provider_payment_id=_stars_charge_id(),
                amount=2200,
                currency="XTR",
                period_start=now - timedelta(days=30),
                period_end=now + sub_end_offset,
                raw={},
            )
            session.add(sub)
            await session.commit()
    return user.id


async def _get_user_tier(user_id: uuid.UUID) -> str:
    async with SessionFactory() as session:
        u = await session.get(User, user_id)
        return u.tier if u else "<deleted>"


async def test_sweep_downgrades_user_with_expired_period(_cleanup_users) -> None:
    """The whole point: hobby subscription ended yesterday → user falls
    back to free at next sweeper tick."""
    uid = await _make_user_with_sub("hobby", sub_end_offset=-timedelta(hours=2))
    _cleanup_users.append(uid)

    stats = await sweep_expired_subscriptions()
    assert stats["downgraded"] >= 1
    assert await _get_user_tier(uid) == "free"


async def test_sweep_keeps_active_subscription_intact(_cleanup_users) -> None:
    """Mid-period hobby user stays on hobby."""
    uid = await _make_user_with_sub("hobby", sub_end_offset=timedelta(days=10))
    _cleanup_users.append(uid)

    stats = await sweep_expired_subscriptions()
    assert stats["still_active"] >= 1
    assert await _get_user_tier(uid) == "hobby"


async def test_sweep_ignores_free_users(_cleanup_users) -> None:
    """Free users aren't loaded by the sweeper at all — that's the
    selective scan optimisation."""
    uid = await _make_user_with_sub("free", sub_end_offset=None)
    _cleanup_users.append(uid)

    stats = await sweep_expired_subscriptions()
    # User isn't included in stats["checked"] because they're free.
    assert await _get_user_tier(uid) == "free"


async def test_sweep_downgrades_paid_tier_drift(_cleanup_users) -> None:
    """A user with tier='hobby' but NO subscription rows is data drift —
    sweeper should fix it by falling back to free."""
    uid = await _make_user_with_sub("hobby", sub_end_offset=None)
    _cleanup_users.append(uid)

    stats = await sweep_expired_subscriptions()
    assert stats["no_subs"] >= 1
    assert await _get_user_tier(uid) == "free"


async def test_sweep_uses_max_period_end(_cleanup_users) -> None:
    """A user with two subscription rows — one expired, one active in the
    future — should NOT be downgraded. The sweeper takes MAX(period_end),
    which is the active one, not the expired one."""
    now = datetime.now(UTC)
    user = User(tier="hobby", telegram_user_id=int(uuid.uuid4().int % 2_000_000_000))
    async with SessionFactory() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Old expired subscription
        session.add(Subscription(
            user_id=user.id,
            plan="hobby",
            provider="telegram_stars",
            provider_payment_id=_stars_charge_id(),
            amount=2200,
            currency="XTR",
            period_start=now - timedelta(days=60),
            period_end=now - timedelta(days=30),
            raw={},
        ))
        # Renewal that's still active
        session.add(Subscription(
            user_id=user.id,
            plan="hobby",
            provider="telegram_stars",
            provider_payment_id=_stars_charge_id(),
            amount=2200,
            currency="XTR",
            period_start=now - timedelta(days=29),
            period_end=now + timedelta(days=1),
            raw={},
        ))
        await session.commit()

    _cleanup_users.append(user.id)

    await sweep_expired_subscriptions()
    # Renewed → must stay hobby
    assert await _get_user_tier(user.id) == "hobby"
