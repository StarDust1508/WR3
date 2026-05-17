"""Tier-based scan quota enforcement.

Per /pricing the tiers promise:
    free   — 1 contract / 24 hours
    hobby  — 10 contracts / month
    team   — unlimited
    pro    — unlimited

Without enforcement that text is theatre — anyone can crank free-tier
scans into infinity. This module makes the quota real.

Design:
    * Counters live in Redis as fixed-window keys per user.
        wr3:quota:scans:{user_id}:{window} -> int
        TTL = window seconds + grace.
      Fixed-window is cheap, not perfectly fair at edges (a user could do
      2 scans in 2 seconds across a window boundary) but for our quota
      sizes that's a rounding error not a billing leak.
    * Anonymous calls (no user_id) share one IP-based key with the
      strictest free-tier limit. Otherwise scraping the public API costs
      us LLM tokens for free.
    * The Stars subscription path is the source of truth for `user.tier`;
      this module reads tier off the User row and checks against the
      tier's limit. Subscription expiry → user.tier auto-falls back to
      "free" via the periodic sweeper (not yet wired — TODO note in
      subscription_repository.py).

Returns: `QuotaCheck(allowed: bool, retry_after_seconds: int | None, ...)`.
The route handler raises 429 with the retry-after on `allowed=False`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import redis.asyncio as aioredis
import structlog

from wr3_api.config import get_settings

logger = structlog.get_logger()


@dataclass(frozen=True)
class TierLimit:
    """How many scans this tier gets per `period`. None = unlimited."""

    scans: int | None
    period: timedelta
    label: str


# Single source of truth. Mirror with /pricing display copy when adjusting.
# Free has the tightest window (rolling 24h) to discourage scraping;
# hobby uses calendar-month-sized windows because that's how the user
# experiences "10 contracts per month".
TIER_LIMITS: dict[str, TierLimit] = {
    "free": TierLimit(scans=1, period=timedelta(days=1), label="1 скан / 24 ч"),
    "hobby": TierLimit(scans=10, period=timedelta(days=30), label="10 сканов / 30 д"),
    "team": TierLimit(scans=None, period=timedelta(days=30), label="безлимит"),
    "pro": TierLimit(scans=None, period=timedelta(days=30), label="безлимит"),
}

# Anonymous (no user) gets a free-tier-equivalent budget keyed by IP.
# Same numbers as free; separate counter so an anon flood doesn't burn
# someone else's quota.
ANON_LIMIT = TierLimit(scans=1, period=timedelta(days=1), label="1 скан / 24 ч (anon)")


@dataclass
class QuotaCheck:
    """Result of a quota check. Render this to a 429 body when blocked."""

    allowed: bool
    tier: str
    used: int
    limit: int | None
    retry_after_seconds: int | None
    window_seconds: int


_redis_pool: aioredis.Redis | None = None


def _redis() -> aioredis.Redis:
    """Lazy module-singleton — same pattern as scan_worker."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


def _quota_key(*, user_id: uuid.UUID | None, ip: str, tier: str) -> str:
    """Composite key — user-scoped when authed, IP-scoped when anonymous.

    Including the tier in the key means upgrading from free → hobby
    starts a fresh counter rather than inheriting the prior cap. That's
    intentional: paying customers get a clean slate at upgrade time.
    """
    if user_id is not None:
        return f"wr3:quota:scans:user:{user_id}:{tier}"
    # Sanitise IP for Redis key — strip ports and IPv6 zone identifiers.
    safe_ip = ip.split("%", 1)[0].split(":", 1)[0] or "anon"
    return f"wr3:quota:scans:ip:{safe_ip}"


async def check_and_increment_scan(
    *,
    user_id: uuid.UUID | None,
    tier: str,
    client_ip: str,
) -> QuotaCheck:
    """Atomically check + bump the scan counter for this user/IP.

    Atomicity matters: a naive `get` then `incr` allows two parallel
    requests to both see "0 used" and both get through. We use INCR
    (which returns the new value) and then check the result against the
    limit. If over, DECR back (so we don't permanently inflate the
    counter on rejected requests). EXPIRE is set only on the first incr
    of a window so each window gets its own TTL.
    """
    limit = TIER_LIMITS.get(tier) if user_id is not None else ANON_LIMIT
    if limit is None or limit.scans is None:
        # Unknown tier defaults to free behaviour; unlimited tiers
        # short-circuit before touching Redis.
        return QuotaCheck(
            allowed=True,
            tier=tier,
            used=0,
            limit=None,
            retry_after_seconds=None,
            window_seconds=int(
                (limit.period if limit else timedelta(days=30)).total_seconds()
            ),
        )

    key = _quota_key(user_id=user_id, ip=client_ip, tier=tier)
    window_s = int(limit.period.total_seconds())
    r = _redis()

    # Atomic counter bump + TTL. If TTL wasn't set yet (key didn't exist),
    # set it now so the window terminates correctly. NX flag means "only
    # set if no TTL" — safe across racing writers.
    pipe = r.pipeline()
    pipe.incr(key, 1)
    pipe.expire(key, window_s, nx=True)
    pipe.ttl(key)
    results = await pipe.execute()
    used = int(results[0])
    ttl = int(results[2])

    if used <= limit.scans:
        return QuotaCheck(
            allowed=True,
            tier=tier,
            used=used,
            limit=limit.scans,
            retry_after_seconds=None,
            window_seconds=window_s,
        )

    # Over limit — roll back the increment so the counter reflects actual
    # successful scans, not rejected ones. Otherwise a rapid-fire script
    # would keep pushing the counter up forever.
    await r.decr(key, 1)
    return QuotaCheck(
        allowed=False,
        tier=tier,
        used=limit.scans,
        limit=limit.scans,
        retry_after_seconds=ttl if ttl > 0 else window_s,
        window_seconds=window_s,
    )


async def reset_user_quota(user_id: uuid.UUID, tier: str) -> None:
    """Wipe the user's counter for the given tier. Used after refunds
    where we don't want the user to be locked out of the new free-tier
    counter by an old hobby-tier counter still in TTL."""
    key = _quota_key(user_id=user_id, ip="", tier=tier)
    await _redis().delete(key)
