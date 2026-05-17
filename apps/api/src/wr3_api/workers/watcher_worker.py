"""Periodic monitoring of watched contracts.

What this task does each tick (default cadence: every 6 hours):
  1. Picks up to N watched rows whose `last_checked_at` is stale.
  2. Pre-filters: drops rows belonging to a user who currently has
     `preferences.continuous_monitoring=False`. The pref is the on/off
     switch; the rows are kept around so flipping it back resumes
     monitoring without losing history.
  3. For each remaining row, fetches the verified source from Etherscan V2
     via the audit-engine's existing client (reuses retry/back-off logic).
  4. Hashes SourceCode; compares to last_source_hash.
  5. On change: DMs the user via @KitronBot with a "source code changed"
     alert. On first-poll-after-insert (last_source_hash IS NULL) we set
     the baseline silently — no alert, otherwise every newly-watched
     contract would alert once on its very first check.
  6. Records the check (updates last_checked_at + error counters).

No LLM tokens. No paid services. Etherscan free tier: 5 req/sec,
100k req/day — plenty of headroom for the realistic scale.
"""

from __future__ import annotations

import asyncio

import structlog
from audit_engine.ingestion.fetcher import SourceFetcher

from wr3_api.config import get_settings
from wr3_api.models import User, WatchedContract
from wr3_api.services import watch_repository as watch_repo
from wr3_api.services.watch_repository import compute_source_hash
from wr3_api.telegram.bot import BotAction, execute_actions
from wr3_api.workers.celery_app import celery_app

logger = structlog.get_logger()


# Polite spacing between Etherscan calls inside a single tick so we never
# burst past their 5 req/sec rate limit even on a big batch.
_ETHERSCAN_INTER_CALL_DELAY = 0.25


def _is_watching_active(user: User) -> bool:
    prefs = user.preferences or {}
    return bool(prefs.get("continuous_monitoring", False))


async def _process_row(row: WatchedContract, user: User, fetcher: SourceFetcher) -> str:
    """Returns one of: 'skip', 'baseline', 'unchanged', 'changed', 'error'."""
    if not _is_watching_active(user):
        # User flipped the toggle off — leave the row, just skip work.
        return "skip"

    try:
        bundle = await fetcher.fetch(address=row.address, network=row.network)
    except Exception as e:
        logger.warning(
            "watch.fetch_error",
            address=row.address,
            network=row.network,
            error=str(e),
        )
        await watch_repo.record_check(
            row_id=row.id, new_source_hash=None, changed=False, error=True
        )
        return "error"

    if bundle is None:
        # Unverified / unsupported / Etherscan returned nothing useful.
        # Treat as a soft-error so we back off — but we don't alert: the
        # user knows their contract isn't verified, that's not news.
        await watch_repo.record_check(
            row_id=row.id, new_source_hash=None, changed=False, error=True
        )
        return "error"

    # primary_source flattens single-file or joins multi-file output —
    # the same string the analyzers see during a real scan. Hashing that
    # means proxy upgrades that change `files` get caught even when
    # `flattened_source` stays empty.
    new_hash = compute_source_hash(bundle.primary_source)

    if row.last_source_hash is None:
        # First poll establishes the baseline silently.
        await watch_repo.record_check(
            row_id=row.id, new_source_hash=new_hash, changed=False
        )
        return "baseline"

    if new_hash == row.last_source_hash:
        await watch_repo.record_check(
            row_id=row.id, new_source_hash=new_hash, changed=False
        )
        return "unchanged"

    # Real change — record + notify.
    await watch_repo.record_check(
        row_id=row.id, new_source_hash=new_hash, changed=True
    )
    await _notify_user(row=row, user=user)
    return "changed"


async def _notify_user(*, row: WatchedContract, user: User) -> None:
    """Send a DM via @KitronBot. Silent failure on missing token / chat id."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning("watch.notify_no_bot_token")
        return
    if user.telegram_user_id is None:
        logger.info("watch.notify_no_tg_id", user_id=str(user.id))
        return

    text = (
        f"⚠️ *Контракт изменился*\n\n"
        f"`{row.address}` в сети *{row.network}* — verified source "
        f"обновился на Etherscan.\n\n"
        f"Это может быть proxy-upgrade, новая верификация или вообще "
        f"перевыпуск. Запусти новый аудит:\n"
        f"`/scan {row.address} {row.network}`"
    )
    action = BotAction(
        method="sendMessage",
        payload={
            "chat_id": int(user.telegram_user_id),
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        },
    )
    await execute_actions([action], bot_token=settings.telegram_bot_token)


async def _run_tick(
    *,
    interval_hours: int = 6,
    batch_limit: int = 500,
) -> dict[str, int]:
    """One sweep of the watch queue. Returns per-outcome counters."""
    pairs = await watch_repo.due_for_check(
        interval_hours=interval_hours, limit=batch_limit
    )
    if not pairs:
        return {"due": 0}

    fetcher = SourceFetcher()
    stats = {
        "due": len(pairs),
        "skip": 0,
        "baseline": 0,
        "unchanged": 0,
        "changed": 0,
        "error": 0,
    }
    for row, user in pairs:
        outcome = await _process_row(row, user, fetcher)
        stats[outcome] = stats.get(outcome, 0) + 1
        # Respect Etherscan's 5 req/sec ceiling. The skip case didn't call
        # Etherscan, so we don't need to wait after it.
        if outcome != "skip":
            await asyncio.sleep(_ETHERSCAN_INTER_CALL_DELAY)

    logger.info("watch.tick_done", **stats)
    return stats


@celery_app.task(
    bind=True,
    name="wr3_api.workers.watcher_worker.refresh_watched_contracts",
    max_retries=1,
)
def refresh_watched_contracts(self) -> dict[str, int]:
    return asyncio.run(_run_tick())
