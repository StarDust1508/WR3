"""Scan worker — runs audit-engine pipeline, persists state to Postgres + Redis."""

from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from collections.abc import Coroutine
from typing import Any

import redis.asyncio as aioredis
import structlog
from audit_engine.pipeline import AuditPipeline, PipelineEvent

from wr3_api.config import get_settings
from wr3_api.services import scan_repository as repo
from wr3_api.workers.celery_app import celery_app


def _run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine to completion regardless of caller context.

    In normal Celery workers we just use asyncio.run(). In eager mode (used for
    dev/test, see celery_app.py) the task is invoked from an existing event
    loop (FastAPI handler), so asyncio.run() would error — we spin a dedicated
    loop in a background thread instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, T] = {}
    error: dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["v"] = asyncio.run(coro)
        except BaseException as exc:
            error["v"] = exc

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()
    if "v" in error:
        raise error["v"]
    return result["v"]

logger = structlog.get_logger()
settings = get_settings()

_PROGRESS_KEY = "wr3:scan:progress:{job_id}"
_PROGRESS_TTL = 3600  # 1h


async def _redis() -> aioredis.Redis:
    return await aioredis.from_url(settings.redis_url, decode_responses=True)


async def enqueue_scan(
    *, job_id: str, address: str, network: str, source: str | None
) -> str:
    """Persist Scan row + initial Redis progress, then dispatch to Celery.

    Returns the scan_id (UUID) — the API may want to expose it directly.
    """
    scan_id = await repo.create_scan(address=address, network=network)

    r = await _redis()
    initial = {
        "stage": "queued",
        "progress": 0,
        "address": address,
        "network": network,
        "scan_id": str(scan_id),
    }
    await r.setex(_PROGRESS_KEY.format(job_id=job_id), _PROGRESS_TTL, json.dumps(initial))
    await r.aclose()

    run_audit_pipeline.delay(
        job_id=job_id,
        scan_id=str(scan_id),
        address=address,
        network=network,
        source=source,
    )
    return str(scan_id)


async def get_scan_progress(job_id: str) -> dict[str, Any] | None:
    r = await _redis()
    raw = await r.get(_PROGRESS_KEY.format(job_id=job_id))
    await r.aclose()
    if raw is None:
        return None
    return json.loads(raw)


async def _publish(job_id: str, payload: dict[str, Any]) -> None:
    r = await _redis()
    await r.setex(_PROGRESS_KEY.format(job_id=job_id), _PROGRESS_TTL, json.dumps(payload))
    await r.aclose()


def _event_payload(event: PipelineEvent, *, scan_id: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": event.stage,
        "progress": event.progress,
        "scan_id": scan_id,
    }
    if event.message:
        payload["message"] = event.message
    if event.data:
        payload.update(event.data)
    return payload


@celery_app.task(name="wr3_api.workers.scan_worker.run_audit_pipeline", bind=True)
def run_audit_pipeline(
    self,
    job_id: str,
    scan_id: str,
    address: str,
    network: str,
    source: str | None,
) -> dict[str, Any]:
    """Run the full audit pipeline; publish events to Redis + persist final to PG."""

    async def _run() -> dict[str, Any]:
        scan_uuid = uuid.UUID(scan_id)
        pipeline = AuditPipeline(network=network, scan_id=scan_id)  # type: ignore[arg-type]
        started = time.monotonic()

        async for event in pipeline.run(address=address, source=source):
            payload = _event_payload(event, scan_id=scan_id)
            await _publish(job_id, payload)
            await repo.update_progress(
                scan_id=scan_uuid,
                stage=event.stage,
                progress=event.progress,
                error_message=event.message if event.stage == "error" else None,
            )
            logger.info(
                "scan.progress",
                job_id=job_id,
                scan_id=scan_id,
                stage=event.stage,
                progress=event.progress,
            )

        result = pipeline.result()
        if result.get("status") == "incomplete":
            return result

        duration = time.monotonic() - started
        await repo.finalize_scan(
            scan_id=scan_uuid,
            report_dict=result,
            duration_seconds=duration,
        )
        return result

    return _run_async(_run())
