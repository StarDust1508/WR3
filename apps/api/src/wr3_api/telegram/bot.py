"""Telegram bot — command parsing + reply assembly.

Pure logic: takes a parsed Update dict, decides what to do, calls into the
same `enqueue_scan` path the web API uses, and returns a list of outbound
calls the caller must execute (sending messages).

This separation lets the webhook route test the logic without mocking
httpx — return values are plain dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from wr3_api.models.subscription import STARS_PRICE
from wr3_api.services import subscription_repository as sub_repo
from wr3_api.services import user_repository as user_repo
from wr3_api.workers.scan_worker import enqueue_scan

logger = structlog.get_logger()


_NETWORK_ALIASES = {
    "eth": "ethereum",
    "ethereum": "ethereum",
    "base": "base",
    "arb": "arbitrum",
    "arbitrum": "arbitrum",
    "bsc": "bsc",
    "bnb": "bsc",
    "sol": "solana",
    "solana": "solana",
}
_DEFAULT_NETWORK = "base"
_ADDRESS_EVM = re.compile(r"^0x[a-fA-F0-9]{40}$")
_ADDRESS_SOLANA = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")


@dataclass
class BotAction:
    """One outbound action the webhook handler must execute."""

    method: str  # "sendMessage", "answerCallbackQuery", etc.
    payload: dict[str, Any]


@dataclass
class BotReply:
    actions: list[BotAction] = field(default_factory=list)


def _send_message(chat_id: int, text: str, *, reply_to: int | None = None, parse_mode: str = "Markdown") -> BotAction:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_to is not None:
        payload["reply_to_message_id"] = reply_to
    return BotAction(method="sendMessage", payload=payload)


def _send_stars_invoice(*, chat_id: int, plan: str, stars: int) -> BotAction:
    """Build a `sendInvoice` call for Telegram Stars (currency XTR).

    Stars invoices are special: provider_token must be EMPTY, currency must
    be "XTR", and prices must be a single-item list. The `payload` field is
    echoed back in pre_checkout_query + successful_payment — we encode the
    plan there so the handler knows what was bought.
    """
    title, _ = _PLAN_BLURBS.get(plan, ("Подписка", ""))
    description = {
        "hobby": "10 аудитов в месяц · multi-agent триаж · Foundry PoC retry-loop",
        "team":  "Безлимит аудитов · AI-fuzzing · мониторинг 24/7",
        "pro":   "Всё из Team + Certora formal verification",
    }.get(plan, "wr3 подписка")
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "title": title,
        "description": description,
        # Bot API echoes this on pre_checkout + successful_payment. Prefix
        # with "wr3:" so future payload formats (e.g. "wr3-credits:") don't
        # clash with this subscription flow.
        "payload": f"wr3:sub:{plan}",
        "provider_token": "",  # MUST be empty for Stars
        "currency": "XTR",
        "prices": [{"label": title, "amount": stars}],
    }
    return BotAction(method="sendInvoice", payload=payload)


def _answer_pre_checkout(query_id: str, *, ok: bool, error: str | None = None) -> BotAction:
    payload: dict[str, Any] = {"pre_checkout_query_id": query_id, "ok": ok}
    if not ok and error:
        payload["error_message"] = error
    return BotAction(method="answerPreCheckoutQuery", payload=payload)


def _refund_stars(*, tg_user_id: int, charge_id: str) -> BotAction:
    """Bot API: refundStarPayment. Returns Stars to user instantly when
    within Telegram's refund window (typically 21 days from purchase).
    """
    return BotAction(
        method="refundStarPayment",
        payload={
            "user_id": tg_user_id,
            "telegram_payment_charge_id": charge_id,
        },
    )


def parse_command(text: str) -> tuple[str, list[str]]:
    """Strip optional `/cmd@botname` form; return (command_lower, args)."""
    if not text:
        return "", []
    head, _, tail = text.strip().partition(" ")
    head = head.split("@", 1)[0].lower()  # /scan@wr3_audit_bot -> /scan
    args = [a for a in tail.strip().split() if a]
    return head, args


def detect_network_and_address(args: list[str]) -> tuple[str | None, str | None]:
    """Accept "/scan 0x123 base" OR "/scan base 0x123" OR just "/scan 0x123".

    Returns (address, network) or (None, None) if no recognizable address.
    """
    address: str | None = None
    network: str | None = None
    for a in args:
        low = a.lower()
        if low in _NETWORK_ALIASES:
            network = _NETWORK_ALIASES[low]
            continue
        if _ADDRESS_EVM.match(a):
            address = a
            continue
        if _ADDRESS_SOLANA.match(a):
            address = a
            network = network or "solana"
            continue
    return address, network


async def handle_update(update: dict[str, Any], *, web_base_url: str) -> BotReply:
    """Process one Telegram Update; return outbound actions."""
    # Stars payment flow: pre_checkout_query MUST be answered within 10s, or
    # Telegram cancels the payment. We always accept here — validation
    # happens earlier (when we send the invoice) and at successful_payment
    # (idempotent recording).
    pre_checkout = update.get("pre_checkout_query")
    if pre_checkout:
        query_id = pre_checkout.get("id")
        payload = pre_checkout.get("invoice_payload") or ""
        if not query_id:
            return BotReply()
        # Defensive: reject anything we don't recognise.
        if not payload.startswith("wr3:sub:"):
            return BotReply(actions=[
                _answer_pre_checkout(query_id, ok=False, error="неизвестный invoice")
            ])
        plan = payload.split(":", 2)[2]
        if plan not in STARS_PRICE:
            return BotReply(actions=[
                _answer_pre_checkout(query_id, ok=False, error="неизвестный тариф")
            ])
        return BotReply(actions=[_answer_pre_checkout(query_id, ok=True)])

    message = update.get("message") or update.get("edited_message")
    if not message:
        return BotReply()

    # successful_payment arrives as a field on the message, not a separate
    # top-level update. Handle it before the command parser sees the text.
    if message.get("successful_payment"):
        return await _handle_successful_payment(message=message)

    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is None:
        return BotReply()

    from_user = message.get("from") or {}
    tg_user_id = from_user.get("id")
    if tg_user_id is None:
        return BotReply()

    await user_repo.upsert_telegram_user(
        telegram_user_id=int(tg_user_id),
        telegram_username=from_user.get("username"),
        display_name=_full_name(from_user),
    )

    text = (message.get("text") or "").strip()
    command, args = parse_command(text)

    if command == "/start":
        # /start may carry a deep-link payload set by /pricing CTAs:
        #   "/start upgrade_hobby" -> we route to a subscription explainer
        # (Telegram passes it as the first arg.)
        if args and args[0].startswith("upgrade_"):
            return _handle_upgrade(chat_id=chat_id, plan=args[0][len("upgrade_"):])
        return _greet(chat_id=chat_id, web_base_url=web_base_url)

    if command == "/help":
        return _greet(chat_id=chat_id, web_base_url=web_base_url)

    if command == "/scan":
        return await _handle_scan(
            chat_id=chat_id,
            tg_user_id=int(tg_user_id),
            args=args,
            web_base_url=web_base_url,
        )

    if command == "/refund":
        return await _handle_refund(chat_id=chat_id, tg_user_id=int(tg_user_id))

    # Unknown / plain text: assume an address paste.
    address, network = detect_network_and_address([text, *args])
    if address:
        return await _handle_scan(
            chat_id=chat_id,
            tg_user_id=int(tg_user_id),
            args=[address, *( [network] if network else [] )],
            web_base_url=web_base_url,
        )

    return BotReply(actions=[
        _send_message(
            chat_id,
            "Отправь `/scan 0x... base` или вставь адрес контракта. `/help` — подробности.",
        )
    ])


def _greet(*, chat_id: int, web_base_url: str) -> BotReply:
    text = (
        "*wr3* — AI-аудит смарт-контрактов\n\n"
        "Команды:\n"
        "  `/scan 0x... base` — быстрый аудит (Ethereum, Base, Arbitrum, BSC, Solana)\n"
        "  `/refund` — вернуть Stars за активную подписку\n"
        "  Открой Mini App для полного отчёта:\n"
        f"  {web_base_url}/tg"
    )
    return BotReply(actions=[_send_message(chat_id, text)])


# Планы показываются на /pricing. Deep-link оттуда приходит сюда.
_PLAN_BLURBS: dict[str, tuple[str, str]] = {
    "free": (
        "Бесплатный тариф",
        "вы уже на нём — просто нажмите кнопку wr3 audit внизу чата",
    ),
    "hobby": (
        "Hobby — $29/мес",
        "10 контрактов в месяц, multi-agent триаж, Foundry PoC retry-loop",
    ),
    "team": (
        "Team — $99/мес",
        "безлимит контрактов, AI-fuzzing, мониторинг 24/7",
    ),
    "pro": (
        "Pro — $499/мес",
        "всё из Team + Certora formal verification",
    ),
    "enterprise": (
        "Enterprise / кастом",
        "per-engagement аудит, white-label, объёмные скидки",
    ),
}


def _handle_upgrade(*, chat_id: int, plan: str) -> BotReply:
    """Reply to `/start upgrade_<plan>` deep-link from /pricing.

    Sends a real Telegram Stars invoice for plans we sell that way.
    Enterprise falls through to a contact message — it's per-engagement.
    """
    title, body = _PLAN_BLURBS.get(plan, ("Апгрейд", "неизвестный тариф"))
    stars = STARS_PRICE.get(plan)

    if stars is None:
        # free / enterprise / unknown — explain, don't pretend.
        if plan == "enterprise":
            text = (
                f"*{title}*\n{body}\n\n"
                "Enterprise — per-engagement, не через Stars. "
                "Напиши в этот чат, обсудим объём и цену."
            )
        elif plan == "free":
            text = f"*{title}*\n{body}"
        else:
            text = f"*{title}*\n{body}\n\nЭтот тариф пока не продаётся через бота."
        return BotReply(actions=[_send_message(chat_id, text)])

    intro = (
        f"*{title}*\n{body}\n\n"
        f"Оплата — *{stars}* ⭐ Telegram Stars, период 30 дней.\n"
        "Подтверди в окне оплаты ниже ↓"
    )
    return BotReply(actions=[
        _send_message(chat_id, intro),
        _send_stars_invoice(chat_id=chat_id, plan=plan, stars=stars),
    ])


async def _handle_refund(*, chat_id: int, tg_user_id: int) -> BotReply:
    """Refund the user's most recent active Stars subscription.

    Flow:
      1. Look up the user; find their active Subscription.
      2. Issue refundStarPayment to Telegram (Bot API does the actual
         money movement — Stars return to user's balance instantly).
      3. Mark the subscription refunded in our DB (period_end=now,
         tier→free).
    If there's no active subscription we just tell them.
    """
    user = await user_repo.upsert_telegram_user(telegram_user_id=tg_user_id)
    active = await sub_repo.get_active_for_user(user.id)

    if active is None:
        return BotReply(actions=[
            _send_message(
                chat_id,
                "У тебя нет активной подписки для возврата. Текущий тариф: *free*.",
            )
        ])

    if active.provider != "telegram_stars":
        return BotReply(actions=[
            _send_message(
                chat_id,
                f"Активная подписка оплачена через `{active.provider}`, не через Stars. "
                "Возврат через Telegram-бота возможен только для Stars-платежей. "
                "Напиши в этот чат — разберём вручную.",
            )
        ])

    actions: list[BotAction] = [
        _refund_stars(
            tg_user_id=tg_user_id,
            charge_id=active.provider_payment_id,
        ),
    ]

    # Update our DB now — if Telegram rejects the refund (e.g. past 21-day
    # window) the user can still see this in execution logs; the active
    # subscription rollback is cheap to reverse manually if needed. Doing
    # it post-API would risk the user getting refunded Stars but keeping
    # the paid tier in our system on transient errors.
    refunded = await sub_repo.refund_active_subscription(user.id)
    if refunded is not None:
        actions.append(
            _send_message(
                chat_id,
                (
                    f"✓ Запрос на возврат отправлен в Telegram.\n\n"
                    f"*{active.amount} ⭐* вернутся на твой Stars-баланс. "
                    f"Тариф откатан к *free*.\n\n"
                    "Если Stars не пришли через минуту — возможно, прошёл "
                    "21-дневный лимит Telegram. Напиши в чат, разберёмся."
                ),
            )
        )

    return BotReply(actions=actions)


async def _handle_successful_payment(*, message: dict[str, Any]) -> BotReply:
    """Record a Stars payment and ack the user.

    Idempotent: replays of the same `telegram_payment_charge_id` are no-ops.
    """
    chat_id = (message.get("chat") or {}).get("id")
    from_user = message.get("from") or {}
    tg_user_id = from_user.get("id")
    sp = message.get("successful_payment") or {}

    if chat_id is None or tg_user_id is None:
        return BotReply()

    payload = sp.get("invoice_payload") or ""
    if not payload.startswith("wr3:sub:"):
        logger.warning("bot.payment.unknown_payload", payload=payload)
        return BotReply(actions=[
            _send_message(chat_id, "Платёж получен, но invoice не распознан. Напиши в этот чат — разберёмся.")
        ])

    plan = payload.split(":", 2)[2]
    amount = int(sp.get("total_amount") or 0)
    currency = str(sp.get("currency") or "XTR")
    charge_id = str(sp.get("telegram_payment_charge_id") or "")
    if not charge_id:
        logger.warning("bot.payment.no_charge_id", sp=sp)
        return BotReply(actions=[
            _send_message(chat_id, "Платёж без charge_id — не могу записать. Свяжись с поддержкой.")
        ])

    user = await user_repo.upsert_telegram_user(telegram_user_id=int(tg_user_id))
    sub = await sub_repo.activate_from_payment(
        user_id=user.id,
        plan=plan,
        provider="telegram_stars",
        provider_payment_id=charge_id,
        amount=amount,
        currency=currency,
        raw=sp,
    )

    if sub is None:
        # Duplicate webhook — we already credited this charge. Don't double-notify.
        logger.info("bot.payment.duplicate", charge_id=charge_id)
        return BotReply()

    text = (
        f"✓ Подписка *{plan}* активна до "
        f"`{sub.period_end.strftime('%Y-%m-%d')}` UTC.\n\n"
        f"Спасибо! Открой Mini App — увидишь новый тариф в шапке."
    )
    return BotReply(actions=[_send_message(chat_id, text)])


async def _handle_scan(
    *,
    chat_id: int,
    tg_user_id: int,
    args: list[str],
    web_base_url: str,
) -> BotReply:
    address, network = detect_network_and_address(args)
    if not address:
        return BotReply(actions=[
            _send_message(chat_id, "Использование: `/scan 0x...адрес [сеть]`")
        ])

    network = network or _DEFAULT_NETWORK

    user = await user_repo.upsert_telegram_user(telegram_user_id=tg_user_id)
    import uuid

    job_id = str(uuid.uuid4())
    scan_id = await enqueue_scan(
        job_id=job_id, address=address, network=network, source=None, user_id=user.id
    )
    logger.info("bot.scan_enqueued", scan_id=scan_id, tg=tg_user_id)

    text = (
        f"Сканирую `{address}` в сети {network}.\n"
        f"Открой Mini App — live-прогресс и полный отчёт:\n"
        f"{web_base_url}/tg/scan/{scan_id}"
    )
    return BotReply(actions=[_send_message(chat_id, text)])


def _full_name(from_user: dict[str, Any]) -> str | None:
    parts = [from_user.get("first_name"), from_user.get("last_name")]
    full = " ".join(p for p in parts if p)
    return full or from_user.get("username")


# --- HTTP delivery ----------------------------------------------------------


async def execute_actions(
    actions: list[BotAction], *, bot_token: str, timeout: float = 10.0
) -> None:
    """Fire-and-log every action against Telegram's Bot API."""
    if not actions:
        return
    base = f"https://api.telegram.org/bot{bot_token}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        for action in actions:
            try:
                r = await client.post(f"{base}/{action.method}", json=action.payload)
                if r.status_code >= 400:
                    logger.warning(
                        "bot.send_failed",
                        method=action.method,
                        status=r.status_code,
                        body=r.text[:200],
                    )
            except httpx.HTTPError as e:
                logger.warning("bot.send_error", method=action.method, error=str(e))
