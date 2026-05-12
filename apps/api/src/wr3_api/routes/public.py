"""Unauthenticated public endpoints.

  GET /v1/public/scans      Anonymized leaderboard data
  GET /v1/public/stats      Aggregate counters (total scans, avg score)
  GET /v1/public/incidents  Recent real-world exploits (Rekt/SlowMist/DefiLlama)

These respect user preferences: anyone with `anonymous_in_public=True` is
filtered out of leaderboard responses entirely (we don't surface their data
anywhere public).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from wr3_api.db import SessionFactory
from wr3_api.models import Finding as FindingRow
from wr3_api.models import Scan as ScanRow
from wr3_api.services import incident_repository as inc_repo
from wr3_api.services import scan_repository as repo

router = APIRouter()


@router.get("/scans")
async def list_public_scans(
    limit: int = Query(default=50, ge=1, le=200),
    min_score: float | None = Query(default=None, ge=0, le=100),
) -> list[dict[str, Any]]:
    """Top-scoring public scans for the leaderboard.

    No authentication required. Opted-out users (preferences.anonymous_in_public)
    are excluded.
    """
    return await repo.public_scans(limit=limit, min_score=min_score)


@router.get("/stats")
async def public_stats() -> dict[str, Any]:
    """Aggregate counters for the public landing.

    All cheap aggregates: total completed scans, average score, count of
    HIGH/CRITICAL findings shipped, distinct networks observed.
    """
    async with SessionFactory() as session:
        total_scans = (
            await session.execute(
                select(func.count(ScanRow.id)).where(ScanRow.stage == "done")
            )
        ).scalar() or 0
        avg_score = (
            await session.execute(
                select(func.avg(ScanRow.score)).where(ScanRow.stage == "done")
            )
        ).scalar()
        critical_findings = (
            await session.execute(
                select(func.count(FindingRow.id)).where(
                    FindingRow.severity == "critical", FindingRow.dismissed.is_(False)
                )
            )
        ).scalar() or 0
        high_findings = (
            await session.execute(
                select(func.count(FindingRow.id)).where(
                    FindingRow.severity == "high", FindingRow.dismissed.is_(False)
                )
            )
        ).scalar() or 0
        networks_count = (
            await session.execute(
                select(func.count(func.distinct(ScanRow.network))).where(
                    ScanRow.stage == "done"
                )
            )
        ).scalar() or 0

    return {
        "total_scans": int(total_scans),
        "avg_score": round(float(avg_score), 1) if avg_score is not None else None,
        "critical_findings": int(critical_findings),
        "high_findings": int(high_findings),
        "networks_count": int(networks_count),
    }


@router.get("/incidents")
async def public_incidents(
    limit: int = Query(default=10, ge=1, le=50),
    days: int = Query(default=60, ge=1, le=365),
) -> dict[str, Any]:
    """Recent real-world exploit reports, deduplicated across sources.

    Sources: Rekt News RSS, SlowMist Medium RSS, DefiLlama Hacks API.
    Dedup runs server-side via cosine similarity on api.navy embeddings.
    """
    rows = await inc_repo.list_recent(limit=limit, max_age_days=days)
    total = await inc_repo.count_total()
    return {
        "incidents": [inc_repo.incident_to_dict(r) for r in rows],
        "total": total,
    }
