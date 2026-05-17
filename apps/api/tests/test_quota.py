"""Quota enforcement — concurrent-safe counter behaviour.

We don't run Redis in the test environment, so this test patches the
`_redis()` factory to a fakeredis-style stub. The interesting properties
to lock in are:

  1. Atomic increment (no race window where two parallel requests both
     pass through under "0 used")
  2. Decrement-on-reject (rejected requests don't permanently inflate
     the counter, so a paused client comes back to the right state)
  3. TTL is set on first increment of a window (so the window actually
     expires)
  4. Unlimited tiers short-circuit before touching Redis at all
  5. Anonymous calls share an IP-keyed counter (one anon can't burn
     another anon's quota)
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from wr3_api.services import quota
from wr3_api.services.quota import (
    ANON_LIMIT,
    TIER_LIMITS,
    QuotaCheck,
    check_and_increment_scan,
)


class _FakePipeline:
    """Minimal Redis pipeline that records commands and replays them."""

    def __init__(self, store: dict[str, int], ttls: dict[str, int]) -> None:
        self.store = store
        self.ttls = ttls
        self._commands: list[tuple[str, tuple]] = []

    def incr(self, key: str, amount: int) -> "_FakePipeline":
        self._commands.append(("incr", (key, amount)))
        return self

    def expire(self, key: str, seconds: int, *, nx: bool = False) -> "_FakePipeline":
        self._commands.append(("expire", (key, seconds, nx)))
        return self

    def ttl(self, key: str) -> "_FakePipeline":
        self._commands.append(("ttl", (key,)))
        return self

    async def execute(self) -> list:
        results = []
        for cmd, args in self._commands:
            if cmd == "incr":
                key, amount = args
                self.store[key] = self.store.get(key, 0) + amount
                results.append(self.store[key])
            elif cmd == "expire":
                key, seconds, nx = args
                if not nx or key not in self.ttls:
                    self.ttls[key] = seconds
                results.append(True)
            elif cmd == "ttl":
                key = args[0]
                results.append(self.ttls.get(key, -1))
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}
        self.ttls: dict[str, int] = {}

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.store, self.ttls)

    async def decr(self, key: str, amount: int = 1) -> int:
        self.store[key] = self.store.get(key, 0) - amount
        return self.store[key]

    async def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if existed else 0


@pytest.fixture(autouse=True)
def _fake_redis(monkeypatch):
    """Patch quota._redis to a fresh in-memory fake for every test."""
    fake = _FakeRedis()
    monkeypatch.setattr(quota, "_redis", lambda: fake)
    return fake


async def test_free_tier_allows_first_scan() -> None:
    result = await check_and_increment_scan(
        user_id=uuid.uuid4(),
        tier="free",
        client_ip="1.2.3.4",
    )
    assert isinstance(result, QuotaCheck)
    assert result.allowed
    assert result.used == 1
    assert result.limit == 1
    assert result.tier == "free"
    assert result.retry_after_seconds is None


async def test_free_tier_blocks_second_scan_in_window() -> None:
    uid = uuid.uuid4()
    first = await check_and_increment_scan(
        user_id=uid, tier="free", client_ip="1.2.3.4"
    )
    assert first.allowed
    second = await check_and_increment_scan(
        user_id=uid, tier="free", client_ip="1.2.3.4"
    )
    assert not second.allowed
    assert second.retry_after_seconds is not None
    assert second.retry_after_seconds > 0
    # The retry-after must roughly match the configured window.
    assert second.retry_after_seconds <= int(
        TIER_LIMITS["free"].period.total_seconds()
    )


async def test_rejected_scan_decrements_counter(_fake_redis: _FakeRedis) -> None:
    """If a scan is rejected for over-quota, the counter must roll back
    so a paused user doesn't keep climbing the count with each 429."""
    uid = uuid.uuid4()
    await check_and_increment_scan(user_id=uid, tier="free", client_ip="1.2.3.4")
    # Counter is now at 1 (the limit).
    key = quota._quota_key(user_id=uid, ip="1.2.3.4", tier="free")
    assert _fake_redis.store[key] == 1

    # Three rapid attempts that all get rejected.
    for _ in range(3):
        result = await check_and_increment_scan(
            user_id=uid, tier="free", client_ip="1.2.3.4"
        )
        assert not result.allowed

    # Counter is STILL at 1 — rejections rolled back.
    assert _fake_redis.store[key] == 1


async def test_hobby_tier_allows_ten_then_blocks() -> None:
    uid = uuid.uuid4()
    for i in range(10):
        r = await check_and_increment_scan(
            user_id=uid, tier="hobby", client_ip="1.2.3.4"
        )
        assert r.allowed, f"scan {i + 1} was unexpectedly blocked"
        assert r.used == i + 1
    # 11th must be blocked
    r = await check_and_increment_scan(
        user_id=uid, tier="hobby", client_ip="1.2.3.4"
    )
    assert not r.allowed
    assert r.used == 10


async def test_team_tier_is_unlimited(_fake_redis: _FakeRedis) -> None:
    """Team/Pro have no scans cap. We short-circuit before touching Redis."""
    uid = uuid.uuid4()
    for _ in range(50):
        r = await check_and_increment_scan(
            user_id=uid, tier="team", client_ip="1.2.3.4"
        )
        assert r.allowed
        assert r.limit is None
    # No Redis writes since unlimited
    assert all("team" not in k for k in _fake_redis.store)


async def test_pro_tier_is_unlimited() -> None:
    r = await check_and_increment_scan(
        user_id=uuid.uuid4(), tier="pro", client_ip="1.2.3.4"
    )
    assert r.allowed
    assert r.limit is None


async def test_anonymous_keyed_by_ip() -> None:
    """Different IPs get their own counters."""
    r1 = await check_and_increment_scan(user_id=None, tier="free", client_ip="1.2.3.4")
    r2 = await check_and_increment_scan(user_id=None, tier="free", client_ip="9.9.9.9")
    assert r1.allowed
    assert r2.allowed
    # Same IP — second call from same anon IP IS blocked
    r3 = await check_and_increment_scan(user_id=None, tier="free", client_ip="1.2.3.4")
    assert not r3.allowed


async def test_anonymous_uses_anon_limit_not_user_tier() -> None:
    """When user_id is None we ignore the `tier` arg and apply ANON_LIMIT.
    Otherwise a malicious anon client could declare itself 'pro' to bypass."""
    # ANON_LIMIT.scans == 1 — same as free. Without user_id, claiming 'pro'
    # must still result in a 1-scan window.
    r1 = await check_and_increment_scan(user_id=None, tier="pro", client_ip="1.2.3.4")
    assert r1.allowed
    r2 = await check_and_increment_scan(user_id=None, tier="pro", client_ip="1.2.3.4")
    assert not r2.allowed


async def test_ttl_set_only_on_first_increment(_fake_redis: _FakeRedis) -> None:
    """Window TTL is set on the FIRST scan and should NOT reset on later
    scans within the window — otherwise the window would slide
    indefinitely as the user spaces out their scans."""
    uid = uuid.uuid4()
    await check_and_increment_scan(user_id=uid, tier="hobby", client_ip="1.2.3.4")
    key = quota._quota_key(user_id=uid, ip="1.2.3.4", tier="hobby")
    first_ttl = _fake_redis.ttls[key]
    # Mutate stored ttl to simulate time passing on Redis side.
    _fake_redis.ttls[key] = first_ttl - 100
    # Second scan in same window
    await check_and_increment_scan(user_id=uid, tier="hobby", client_ip="1.2.3.4")
    # TTL must NOT have been reset to the full window again
    assert _fake_redis.ttls[key] == first_ttl - 100


async def test_unknown_tier_falls_back_to_unlimited() -> None:
    """Defensive: a tier string we don't recognise shouldn't lock the user
    out — it returns unlimited, and ops can investigate the data drift."""
    r = await check_and_increment_scan(
        user_id=uuid.uuid4(), tier="enterprise_legacy", client_ip="1.2.3.4"
    )
    assert r.allowed
    assert r.limit is None
