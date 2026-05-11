"""Async SQLAlchemy session factory.

NullPool is intentional: scan workers run on threads that own their own event
loops (Celery eager mode + the thread-fallback in scan_worker._run_async),
and asyncpg pools are loop-bound. Reusing the engine across loops corrupts
the pool. NullPool sidesteps that by opening a fresh connection per checkout.
Postgres connection latency is sub-ms locally — fine for MVP throughput.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from wr3_api.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=_settings.is_local,
    poolclass=NullPool,
)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session
