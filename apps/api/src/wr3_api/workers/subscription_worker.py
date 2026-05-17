"""Periodic subscription maintenance.

One task — `sweep_expired_subscriptions` — runs hourly via Celery beat
and downgrades `user.tier` to "free" for any user whose paid period has
elapsed. Without this the tier sticks at "hobby"/"team"/"pro" forever
even though the subscription is over, which means:

  - The user gets free access past their paid period (revenue leak).
  - When they try to renew, our quota counter for their stale tier may
    block them at the wrong limit.
  - Tier-based gating across the platform (e.g. "premium-only PoC
    detail") would falsely allow access.

Cadence is hourly — not 6h — because subscription windows are 30 days
and we want the downgrade to land within an hour of expiry. Hourly is
also cheap: it's one `SELECT WHERE tier != 'free'` (small set) plus one
`UPDATE` per expired user.
"""

from __future__ import annotations

import asyncio

import structlog

from wr3_api.workers.celery_app import celery_app

logger = structlog.get_logger()


async def _run_sweep() -> dict[str, int]:
    from wr3_api.services import subscription_repository as sub_repo

    return await sub_repo.sweep_expired_subscriptions()


@celery_app.task(
    bind=True,
    name="wr3_api.workers.subscription_worker.sweep_expired_subscriptions",
    max_retries=1,
)
def sweep_expired_subscriptions(self) -> dict[str, int]:
    return asyncio.run(_run_sweep())
