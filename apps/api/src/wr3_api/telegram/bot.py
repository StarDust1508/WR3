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
    message = update.get("message") or update.get("edited_message")
    if not message:
        return BotReply()

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

    if command in ("/start", "/help"):
        return _greet(chat_id=chat_id, web_base_url=web_base_url)

    if command == "/scan":
        return await _handle_scan(
            chat_id=chat_id,
            tg_user_id=int(tg_user_id),
            args=args,
            web_base_url=web_base_url,
        )

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
            "Send `/scan 0x... base` or paste a contract address. `/help` for more.",
        )
    ])


def _greet(*, chat_id: int, web_base_url: str) -> BotReply:
    text = (
        "*wr3* — AI smart-contract audit\n\n"
        "Commands:\n"
        "  `/scan 0x... base` — quick audit (Ethereum, Base, Arbitrum, BSC, Solana)\n"
        "  Open the Mini App for the full report:\n"
        f"  {web_base_url}/tg"
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
            _send_message(chat_id, "Usage: `/scan 0x...address [network]`")
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
        f"Scanning `{address}` on {network}.\n"
        f"Open Mini App for live status & full report:\n"
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
