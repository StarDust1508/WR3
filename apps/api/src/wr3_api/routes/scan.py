import asyncio
import json
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

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
async def create_scan(req: ScanRequest) -> ScanResponse:
    if not req.address.strip():
        raise HTTPException(status_code=400, detail="address required")

    job_id = str(uuid4())
    await enqueue_scan(
        job_id=job_id,
        address=req.address.strip(),
        network=req.network,
        source=req.source_code,
    )
    logger.info("scan.enqueued", job_id=job_id, network=req.network, address=req.address)
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
            }
            for f in findings
        ],
    }


@router.get("")
async def list_recent_scans(limit: int = 20) -> list[dict[str, Any]]:
    rows = await repo.recent_scans(limit=min(max(limit, 1), 100))
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
