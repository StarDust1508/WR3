"""Scan worker — orchestrates audit-engine pipeline and reports progress via Redis."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
import structlog

from audit_engine.pipeline import AuditPipeline, PipelineEvent
from wr3_api.config import get_settings
from wr3_api.workers.celery_app import celery_app

logger = structlog.get_logger()
settings = get_settings()

_PROGRESS_KEY = "wr3:scan:progress:{job_id}"
_PROGRESS_TTL = 3600  # 1h


async def _redis() -> aioredis.Redis:
    return await aioredis.from_url(settings.redis_url, decode_responses=True)


async def enqueue_scan(job_id: str, address: str, network: str, source: str | None) -> None:
    r = await _redis()
    initial = {"stage": "queued", "progress": 0, "address": address, "network": network}
    await r.setex(_PROGRESS_KEY.format(job_id=job_id), _PROGRESS_TTL, json.dumps(initial))
    await r.aclose()

    run_audit_pipeline.delay(job_id=job_id, address=address, network=network, source=source)


async def get_scan_progress(job_id: str) -> dict[str, Any] | None:
    r = await _redis()
    raw = await r.get(_PROGRESS_KEY.format(job_id=job_id))
    await r.aclose()
    if raw is None:
        return None
    return json.loads(raw)


async def _publish_progress(job_id: str, event: PipelineEvent) -> None:
    r = await _redis()
    payload = {
        "stage": event.stage,
        "progress": event.progress,
        "message": event.message,
        **(event.data or {}),
    }
    await r.setex(_PROGRESS_KEY.format(job_id=job_id), _PROGRESS_TTL, json.dumps(payload))
    await r.aclose()


@celery_app.task(name="wr3_api.workers.scan_worker.run_audit_pipeline", bind=True)
def run_audit_pipeline(self, job_id: str, address: str, network: str, source: str | None) -> dict[str, Any]:
    """Run the full audit pipeline; publish stage transitions to Redis."""

    async def _run() -> dict[str, Any]:
        pipeline = AuditPipeline(network=network)

        async for event in pipeline.run(address=address, source=source):
            await _publish_progress(job_id, event)
            logger.info("scan.progress", job_id=job_id, stage=event.stage, progress=event.progress)

        result = pipeline.result()
        return result

    return asyncio.run(_run())
