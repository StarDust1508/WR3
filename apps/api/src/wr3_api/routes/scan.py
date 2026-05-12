import asyncio
import json
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from wr3_api.auth import current_user_optional, current_user_required
from wr3_api.models import User
from wr3_api.services import scan_repository as repo
from wr3_api.workers.scan_worker import enqueue_scan, get_scan_progress

logger = structlog.get_logger()
router = APIRouter()

Network = Literal["ethereum", "base", "arbitrum", "bsc", "solana"]


class ScanRequest(BaseModel):
    address: str = Field(..., min_length=1, max_length=1024)
    network: Network
    source_code: str | None = Field(default=None, max_length=500_000)


class ScanResponse(BaseModel):
    job_id: str
    status: Literal["queued"]


@router.post("", response_model=ScanResponse)
async def create_scan(
    req: ScanRequest,
    user: User | None = Depends(current_user_optional),
) -> ScanResponse:
    if not req.address.strip():
        raise HTTPException(status_code=400, detail="address required")

    job_id = str(uuid4())
    await enqueue_scan(
        job_id=job_id,
        address=req.address.strip(),
        network=req.network,
        source=req.source_code,
        user_id=user.id if user else None,
    )
    logger.info(
        "scan.enqueued",
        job_id=job_id,
        network=req.network,
        address=req.address,
        user_id=str(user.id) if user else None,
    )
    return ScanResponse(job_id=job_id, status="queued")


@router.get("/{job_id}/events")
async def scan_events(job_id: str) -> EventSourceResponse:
    async def event_stream():
        while True:
            progress = await get_scan_progress(job_id)
            if progress is None:
                yield {"event": "message", "data": json.dumps({"stage": "error", "progress": 0, "message": "job not found"})}
                return

            yield {"event": "message", "data": json.dumps(progress)}

            if progress.get("stage") in ("done", "error"):
                return

            await asyncio.sleep(1.0)

    return EventSourceResponse(event_stream())


# IMPORTANT: declare /me before /{scan_id} so it isn't shadowed by UUID parsing.
@router.get("/me")
async def list_my_scans(
    limit: int = 20,
    user: User = Depends(current_user_required),
) -> list[dict[str, Any]]:
    rows = await repo.recent_scans(limit=min(max(limit, 1), 100), user_id=user.id)
    return [
        {
            "id": str(s.id),
            "address": s.address,
            "network": s.network,
            "stage": s.stage,
            "progress": s.progress,
            "score": s.score,
            "tier": s.tier,
            "created_at": s.created_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in rows
    ]


@router.get("/{scan_id}")
async def get_scan_report(scan_id: UUID) -> dict[str, Any]:
    """Return the persisted scan + findings."""
    result = await repo.get_scan_with_findings(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="scan not found")
    scan, findings = result
    return {
        "id": str(scan.id),
        "address": scan.address,
        "network": scan.network,
        "stage": scan.stage,
        "progress": scan.progress,
        "score": scan.score,
        "tier": scan.tier,
        "report": scan.report,
        "duration_seconds": scan.duration_seconds,
        "created_at": scan.created_at.isoformat(),
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "findings": [
            {
                "id": str(f.id),
                "title": f.title,
                "description": f.description,
                "severity": f.severity,
                "source_engine": f.source_engine,
                "file": f.file,
                "line": f.line,
                "confidence": f.confidence,
                "dismissed": f.dismissed,
                "poc_validated": f.poc_validated,
                "poc_path": f.poc_path,
            }
            for f in findings
        ],
    }


@router.get("")
async def list_recent_scans(
    limit: int = 20,
    mine: bool = False,
    user: User | None = Depends(current_user_optional),
) -> list[dict[str, Any]]:
    """When `mine=true` and authed, scope to caller; otherwise: global recent."""
    user_id = user.id if (mine and user is not None) else None
    rows = await repo.recent_scans(limit=min(max(limit, 1), 100), user_id=user_id)
    return [
        {
            "id": str(s.id),
            "address": s.address,
            "network": s.network,
            "stage": s.stage,
            "score": s.score,
            "tier": s.tier,
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]
