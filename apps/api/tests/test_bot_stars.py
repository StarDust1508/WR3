"""Telegram Stars payment flow — pure-unit tests.

DB calls (upsert_telegram_user, activate_from_payment) are monkeypatched so
these tests run without a Postgres connection, matching the rest of the
test suite. The point is to lock in protocol-level invariants:

  - pre_checkout_query is answered, with ok=true only for valid payloads
  - successful_payment with a known payload activates a subscription
  - duplicate payments (same charge_id) don't double-notify
  - unknown payloads / missing charge_id fail gracefully
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from wr3_api.models import User
from wr3_api.models.subscription import STARS_PRICE, Subscription
from wr3_api.telegram import bot


def _make_user() -> User:
    """Build an unsaved User instance for repo stubs to return."""
    u = User()
    u.id = uuid.uuid4()
    u.telegram_user_id = 12345
    u.tier = "free"
    u.preferences = {}
    return u


def _make_sub(plan: str = "hobby") -> Subscription:
    s = Subscription()
    s.id = uuid.uuid4()
    s.user_id = uuid.uuid4()
    s.plan = plan
    s.provider = "telegram_stars"
    s.provider_payment_id = "charge_abc"
    s.amount = STARS_PRICE[plan]
    s.currency = "XTR"
    now = datetime.now(UTC)
    s.period_start = now
    s.period_end = now + timedelta(days=30)
    s.raw = {}
    return s



async def test_pre_checkout_accepts_known_plan() -> None:
    update = {
        "pre_checkout_query": {
            "id": "q1",
            "invoice_payload": "wr3:sub:hobby",
            "from": {"id": 1},
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert len(reply.actions) == 1
    action = reply.actions[0]
    assert action.method == "answerPreCheckoutQuery"
    assert action.payload == {"pre_checkout_query_id": "q1", "ok": True}



async def test_pre_checkout_rejects_unknown_plan() -> None:
    update = {
        "pre_checkout_query": {
            "id": "q2",
            "invoice_payload": "wr3:sub:godmode",
            "from": {"id": 1},
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert reply.actions[0].payload["ok"] is False
    assert "тариф" in reply.actions[0].payload["error_message"]



async def test_pre_checkout_rejects_foreign_payload() -> None:
    """Payload that isn't ours (didn't originate from this bot's sendInvoice)."""
    update = {
        "pre_checkout_query": {
            "id": "q3",
            "invoice_payload": "some-other-app:sub:hobby",
            "from": {"id": 1},
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert reply.actions[0].payload["ok"] is False



async def test_successful_payment_activates_subscription(monkeypatch) -> None:
    user = _make_user()
    sub = _make_sub("hobby")
    captured: dict = {}

    async def fake_upsert(*, telegram_user_id: int, **_: object) -> User:
        return user

    async def fake_activate(**kwargs) -> Subscription:
        captured.update(kwargs)
        return sub

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)
    monkeypatch.setattr(bot.sub_repo, "activate_from_payment", fake_activate)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "successful_payment": {
                "currency": "XTR",
                "total_amount": 2200,
                "invoice_payload": "wr3:sub:hobby",
                "telegram_payment_charge_id": "charge_abc",
                "provider_payment_charge_id": "",
            },
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")

    # The user got a confirmation message.
    assert len(reply.actions) == 1
    assert reply.actions[0].method == "sendMessage"
    assert "Подписка" in reply.actions[0].payload["text"]
    assert "hobby" in reply.actions[0].payload["text"]

    # And we recorded the right payment.
    assert captured["plan"] == "hobby"
    assert captured["provider"] == "telegram_stars"
    assert captured["provider_payment_id"] == "charge_abc"
    assert captured["amount"] == 2200
    assert captured["currency"] == "XTR"



async def test_duplicate_payment_is_silent(monkeypatch) -> None:
    """Telegram retries webhooks. Re-running same charge must not notify twice."""
    user = _make_user()

    async def fake_upsert(*, telegram_user_id: int, **_: object) -> User:
        return user

    async def fake_activate(**_) -> None:
        return None  # repo signals "already recorded" with None

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)
    monkeypatch.setattr(bot.sub_repo, "activate_from_payment", fake_activate)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "successful_payment": {
                "currency": "XTR",
                "total_amount": 2200,
                "invoice_payload": "wr3:sub:hobby",
                "telegram_payment_charge_id": "charge_abc",
            },
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert reply.actions == []



async def test_successful_payment_without_charge_id_warns(monkeypatch) -> None:
    user = _make_user()

    async def fake_upsert(*, telegram_user_id: int, **_: object) -> User:
        return user

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "successful_payment": {
                "currency": "XTR",
                "total_amount": 2200,
                "invoice_payload": "wr3:sub:hobby",
                # no telegram_payment_charge_id
            },
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    assert len(reply.actions) == 1
    assert "charge_id" in reply.actions[0].payload["text"]



async def test_upgrade_deep_link_sends_invoice(monkeypatch) -> None:
    """/start upgrade_hobby must reply with an intro + a real sendInvoice."""
    user = _make_user()

    async def fake_upsert(*, telegram_user_id: int, **_: object) -> User:
        return user

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "text": "/start upgrade_hobby",
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    methods = [a.method for a in reply.actions]
    assert "sendInvoice" in methods

    invoice = next(a for a in reply.actions if a.method == "sendInvoice")
    assert invoice.payload["currency"] == "XTR"
    assert invoice.payload["provider_token"] == ""  # MUST be empty for Stars
    assert invoice.payload["payload"] == "wr3:sub:hobby"
    assert invoice.payload["prices"] == [
        {"label": "Hobby — $29/мес", "amount": STARS_PRICE["hobby"]}
    ]



async def test_upgrade_enterprise_does_not_send_invoice(monkeypatch) -> None:
    """Enterprise is per-engagement, must not produce a Stars invoice."""
    user = _make_user()

    async def fake_upsert(*, telegram_user_id: int, **_: object) -> User:
        return user

    monkeypatch.setattr(bot.user_repo, "upsert_telegram_user", fake_upsert)

    update = {
        "message": {
            "chat": {"id": 999},
            "from": {"id": 12345},
            "text": "/start upgrade_enterprise",
        }
    }
    reply = await bot.handle_update(update, web_base_url="https://example")
    methods = [a.method for a in reply.actions]
    assert "sendInvoice" not in methods
    assert "sendMessage" in methods
