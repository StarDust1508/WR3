"""WatchedContract persistence + the monitoring loop's data access."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from wr3_api.db import SessionFactory
from wr3_api.models import User, WatchedContract

logger = structlog.get_logger()


def compute_source_hash(source: str | None) -> str:
    """Stable 64-char sha256 hex of the verified-source string.

    NULL/empty source produces a sentinel hash ("e3b0..." = sha256("")). We
    treat empty-vs-empty as no-change, but empty→non-empty (or vice versa)
    will fire an alert because the hash flips.
    """
    return hashlib.sha256((source or "").encode("utf-8")).hexdigest()


async def ensure_watched(
    *,
    user_id: uuid.UUID,
    address: str,
    network: str,
) -> WatchedContract:
    """Idempotent insert/reset. Called from scan_worker after each successful
    scan when continuous_monitoring=True.

    Critical invariant: on conflict we MUST reset `error_count` to 0.
    `due_for_check` excludes rows with error_count >= 5 (back-off after a
    sustained Etherscan failure streak). If the user re-runs a scan
    successfully, the contract is once again worth polling — without this
    reset the watcher would never resume after a transient outage burned
    through 5 retries.
    """
    address_lower = address.lower() if address.startswith("0x") else address
    async with SessionFactory() as session:
        stmt = (
            pg_insert(WatchedContract)
            .values(
                user_id=user_id,
                address=address_lower,
                network=network,
            )
            # ON CONFLICT DO UPDATE so the error_count reset actually runs.
            # Touching `updated_at` keeps the row's timestamp honest and
            # gives us a "user-re-ran-scan" signal in the audit log.
            .on_conflict_do_update(
                index_elements=["user_id", "address", "network"],
                set_={"error_count": 0, "updated_at": text("now()")},
            )
            .returning(WatchedContract.id)
        )
        await session.execute(stmt)
        await session.commit()
        # Reload — RETURNING gives id but we want the full row for callers.
        row = (
            await session.execute(
                select(WatchedContract).where(
                    WatchedContract.user_id == user_id,
                    WatchedContract.address == address_lower,
                    WatchedContract.network == network,
                )
            )
        ).scalar_one()
        return row


async def stop_watching(
    *,
    user_id: uuid.UUID,
    address: str,
    network: str,
) -> bool:
    """Remove a single watch. Returns True if a row was deleted."""
    from sqlalchemy import delete

    address_lower = address.lower() if address.startswith("0x") else address
    async with SessionFactory() as session:
        result = await session.execute(
            delete(WatchedContract).where(
                WatchedContract.user_id == user_id,
                WatchedContract.address == address_lower,
                WatchedContract.network == network,
            )
        )
        await session.commit()
        return (result.rowcount or 0) > 0


async def list_for_user(user_id: uuid.UUID) -> list[WatchedContract]:
    async with SessionFactory() as session:
        q = (
            select(WatchedContract)
            .where(WatchedContract.user_id == user_id)
            .order_by(WatchedContract.created_at.desc())
        )
        return list((await session.execute(q)).scalars().all())


async def due_for_check(*, interval_hours: int = 6, limit: int = 500) -> list[tuple[WatchedContract, User]]:
    """Rows whose last_checked_at is NULL or older than `interval_hours`.

    Joined with User so the caller can pre-filter on
    `preferences.continuous_monitoring` — that's the "watch is on" gate.
    Backed-off rows (error_count > 5) are skipped: we treat 5 consecutive
    Etherscan errors as a sign that the contract is gone or the network
    is broken, and stop spending requests on it until the user manually
    re-runs a scan (which resets error_count via `ensure_watched`).
    """
    cutoff = datetime.now(UTC) - timedelta(hours=interval_hours)
    async with SessionFactory() as session:
        q = (
            select(WatchedContract, User)
            .join(User, User.id == WatchedContract.user_id)
            .where(
                (WatchedContract.last_checked_at.is_(None))
                | (WatchedContract.last_checked_at < cutoff)
            )
            .where(WatchedContract.error_count < 5)
            .order_by(
                WatchedContract.last_checked_at.asc().nulls_first(),
            )
            .limit(limit)
        )
        return [(w, u) for w, u in (await session.execute(q)).all()]


async def record_check(
    *,
    row_id: uuid.UUID,
    new_source_hash: str | None,
    changed: bool,
    error: bool = False,
) -> None:
    """Update bookkeeping after a poll. Three terminal states:
      - success, hash unchanged: bump last_checked_at, reset error_count
      - success, hash changed:    also bump last_changed_at + last_source_hash
      - error:                    bump error_count + last_checked_at (so we
                                  spread retries instead of hammering)
    """
    now = datetime.now(UTC)
    async with SessionFactory() as session:
        values: dict = {"last_checked_at": now}
        if error:
            values["error_count"] = WatchedContract.error_count + 1
        else:
            values["error_count"] = 0
            if new_source_hash is not None:
                values["last_source_hash"] = new_source_hash
            if changed:
                values["last_changed_at"] = now
        await session.execute(
            update(WatchedContract).where(WatchedContract.id == row_id).values(**values)
        )
        await session.commit()
