import asyncio
import json
from typing import Any, Literal
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from wr3_api.auth import current_user_optional, current_user_required
from wr3_api.config import get_settings
from wr3_api.models import User
from wr3_api.services import quota
from wr3_api.services import report_markdown as md
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
    request: Request,
    user: User | None = Depends(current_user_optional),
) -> ScanResponse:
    if not req.address.strip():
        raise HTTPException(status_code=400, detail="address required")

    tier = user.tier if user else "free"
    client_ip = _real_client_ip(request)

    settings = get_settings()
    if not settings.is_local:
        check = await quota.check_and_increment_scan(
            user_id=user.id if user else None,
            tier=tier,
            client_ip=client_ip,
        )
        if not check.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "tier_quota_exceeded",
                    "tier": check.tier,
                    "used": check.used,
                    "limit": check.limit,
                    "retry_after_seconds": check.retry_after_seconds,
                    "message": (
                        f"Лимит тарифа {check.tier!r} исчерпан "
                        f"({check.used}/{check.limit}). "
                        "Подождите или обновите тариф в Mini App."
                    ),
                },
                headers={"Retry-After": str(check.retry_after_seconds or 60)},
            )

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
        tier=tier,
    )
    return ScanResponse(job_id=job_id, status="queued")


def _real_client_ip(request: Request) -> str:
    """Best-effort client IP behind CF Workers / serveo / direct.

    CF Workers populates CF-Connecting-IP with the original visitor IP.
    serveo sets X-Forwarded-For. Falling back to the raw socket peer
    catches direct localhost dev calls. We DO trust these headers because
    the only path to our API in production is via CF → serveo, and both
    strip/overwrite client-supplied versions of these headers.
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/{job_id}/progress")
async def scan_progress(job_id: str) -> dict[str, Any]:
    """One-shot JSON snapshot of a scan's progress.

    Same data as the SSE stream but polled, not streamed. Useful for
    callers that don't speak text/event-stream (the MCP server, smoke
    scripts, anything that just wants `is it done yet?`). The SSE
    endpoint stays for the Mini App where progress animation matters.

    Returns 404 once the underlying Redis progress key has expired
    (TTL = 1 hour after the last update).
    """
    progress = await get_scan_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="job not found or expired")
    return progress


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
# Kept as an alias for backwards compatibility — Mini App may reference it.
@router.get("/me")
async def list_my_scans(
    limit: int = 20,
    user: User = Depends(current_user_required),
) -> list[dict[str, Any]]:
    return await _user_scans(user=user, limit=limit)


@router.get("/{scan_id}/report.md", response_class=PlainTextResponse)
async def get_scan_report_markdown(scan_id: UUID) -> PlainTextResponse:
    """Markdown export of a scan + findings. Public — same visibility as JSON.

    The file is named `report.md` so browsers offer a download. Useful for
    pasting into a GitHub issue or sharing with a developer who doesn't want
    to click through the Mini App.
    """
    result = await repo.get_scan_with_findings(scan_id)
    if result is None:
        raise HTTPException(status_code=404, detail="scan not found")
    scan, findings = result
    text = md.render_scan_markdown(scan, findings)
    return PlainTextResponse(
        content=text,
        headers={
            "Content-Type": "text/markdown; charset=utf-8",
            "Content-Disposition": f'inline; filename="wr3-{scan_id}.md"',
        },
    )


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
                # Enrichment metadata (e.g. similar_incidents from W12).
                # Lives in `extra` JSONB and surfaces through this field.
                "metadata": f.extra or {},
            }
            for f in findings
        ],
    }


@router.get("")
async def list_my_recent_scans(
    limit: int = 20,
    user: User = Depends(current_user_required),
) -> list[dict[str, Any]]:
    """Caller's own recent scans. Authenticated only."""
    return await _user_scans(user=user, limit=limit)


async def _user_scans(*, user: User, limit: int) -> list[dict[str, Any]]:
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
