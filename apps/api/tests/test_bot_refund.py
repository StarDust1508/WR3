"""Telegram /refund command — pure-unit tests with monkeypatched repos.

Lock in the contract with Telegram Bot API:
  - We MUST call refundStarPayment with telegram_payment_charge_id
  - We MUST NOT issue a refund when there's no active subscription
  - Stars-only — refunding a TON/Stripe subscription via this command
    would be misleading
  - The DB rollback (period_end=now, tier=free) must run alongside the
    Telegram API call so the two stay consistent
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from wr3_api.models import Subscription, User
from wr3_api.models.subscription import STARS_PRICE
from wr3_api.telegram import bot


def _user() -> User:
    u = User()
    u.id = uuid.uuid4()
    u.telegram_user_id = 12345
    u.tier = "hobby"
    u.preferences = {}
    return u


def _sub(provider: str = "telegram_stars", charge: str = "charge_xyz") -> Subscription:
    s = Subscription()
    s.id = uuid.uuid4()
    s.user_id = uuid.uuid4()
    s.plan = "hobby"
    s.provider = provider
    s.provider_payment_id = charge
    s.amount = STARS_PRICE["hobby"]
    s.currency = "XTR"
    now = datetime.now(UTC)
    s.period_start = now - timedelta(days=2)
    s.period_end = now + timedelta(days=28)
    s.raw = {}
    return s


async def test_refund_no_subscription_replies_friendly(monkeypatch) -> None:
    async def fake_upsert(*, telegram_user_id: int, **_):
        return _user()
    async def fake_active(*_):
        return None

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)
    monkeypatch.setattr(bot.sub_repo, "get_active_for_user", fake_active)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "text": "/refund",
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert len(reply.actions) == 1
    assert reply.actions[0].method == "sendMessage"
    assert "нет активной подписки" in reply.actions[0].payload["text"]


async def test_refund_stars_calls_telegram_and_db(monkeypatch) -> None:
    user = _user()
    sub = _sub()
    refund_called: dict = {}

    async def fake_upsert(*, telegram_user_id: int, **_):
        return user
    async def fake_active(_):
        return sub
    async def fake_refund(user_id):
        refund_called["user_id"] = user_id
        return sub

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)
    monkeypatch.setattr(bot.sub_repo, "get_active_for_user", fake_active)
    monkeypatch.setattr(bot.sub_repo, "refund_active_subscription", fake_refund)

    update = {
        "message": {"chat": {"id": 999}, "from": {"id": 12345}, "text": "/refund"},
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    methods = [a.method for a in reply.actions]
    assert "refundStarPayment" in methods

    refund_action = next(a for a in reply.actions if a.method == "refundStarPayment")
    assert refund_action.payload == {
        "user_id": 12345,
        "telegram_payment_charge_id": "charge_xyz",
    }
    # DB rollback must have been called
    assert refund_called["user_id"] == user.id


async def test_refund_rejects_non_stars_provider(monkeypatch) -> None:
    """Refunding a TON/Stripe subscription via this command is misleading."""
    user = _user()
    sub = _sub(provider="ton")
    db_called = {"v": False}

    async def fake_upsert(*, telegram_user_id: int, **_):
        return user
    async def fake_active(_):
        return sub
    async def fake_refund(_):
        db_called["v"] = True
        return sub

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)
    monkeypatch.setattr(bot.sub_repo, "get_active_for_user", fake_active)
    monkeypatch.setattr(bot.sub_repo, "refund_active_subscription", fake_refund)

    update = {
        "message": {"chat": {"id": 999}, "from": {"id": 12345}, "text": "/refund"},
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    methods = [a.method for a in reply.actions]
    assert "refundStarPayment" not in methods
    assert any("Stars-платеж" in (a.payload.get("text") or "") for a in reply.actions)
    assert db_called["v"] is False  # DB unchanged
