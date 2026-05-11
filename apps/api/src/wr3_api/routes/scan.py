import asyncio
import json
from typing import Literal
from uuid import uuid4

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

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
    await enqueue_scan(job_id=job_id, address=req.address, network=req.network, source=req.source_code)
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
