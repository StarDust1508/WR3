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

# Connection pool used across the whole module. Previously each _publish
# and get_scan_progress call did `from_url(...)` then `aclose()` — that's
# one TCP+AUTH per Redis op, which scales as O(SSE_clients × poll_freq).
# With this pool we open at most `max_connections` sockets total.
_redis_pool: aioredis.Redis | None = None


def _redis() -> aioredis.Redis:
    """Module-singleton Redis client. Lazy so we don't connect on import."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_pool


async def _user_prefs(user_id: uuid.UUID | None) -> dict[str, Any]:
    """Read the owner's feature toggles. Falls back to project defaults when
    the scan is anonymous (no user_id) so the pipeline still runs end-to-end.
    """
    from wr3_api.models.user import DEFAULT_PREFERENCES
    from wr3_api.services import user_repository as ur

    if user_id is None:
        return dict(DEFAULT_PREFERENCES)
    user = await ur.get_user(user_id)
    if user is None or not user.preferences:
        return dict(DEFAULT_PREFERENCES)
    return {**DEFAULT_PREFERENCES, **user.preferences}


async def enqueue_scan(
    *,
    job_id: str,
    address: str,
    network: str,
    source: str | None,
    user_id: uuid.UUID | None = None,
) -> str:
    """Persist Scan row + initial Redis progress, then dispatch to Celery.

    Returns the scan_id (UUID) — the API may want to expose it directly.
    """
    scan_id = await repo.create_scan(address=address, network=network, user_id=user_id)

    r = _redis()
    initial = {
        "stage": "queued",
        "progress": 0,
        "address": address,
        "network": network,
        "scan_id": str(scan_id),
    }
    await r.setex(_PROGRESS_KEY.format(job_id=job_id), _PROGRESS_TTL, json.dumps(initial))

    prefs = await _user_prefs(user_id)

    # Dispatch path differs between dev and prod:
    #   - Prod (real Celery worker process): `.delay()` enqueues on Redis
    #     broker, the worker picks it up out-of-band, HTTP returns instantly.
    #   - Dev (no separate worker): Celery eager mode would also work, but
    #     it runs the task synchronously *inside* `.delay()`, blocking this
    #     request handler for the whole scan (~60s) — curl times out
    #     before getting back a job_id. Instead we spawn the same coroutine
    #     as a fire-and-forget asyncio.Task on the FastAPI event loop.
    #     Progress is published to Redis the same way, so `/v1/scan/{id}/
    #     progress` polling still works.
    if celery_app.conf.task_always_eager:
        task = asyncio.create_task(
            run_audit_pipeline_async(
                job_id=job_id,
                scan_id=str(scan_id),
                address=address,
                network=network,
                source=source,
                prefs=prefs,
                user_id=str(user_id) if user_id else None,
            )
        )
        # Keep a hard reference so the GC doesn't kill the task mid-run.
        _inflight_tasks.add(task)
        task.add_done_callback(_inflight_tasks.discard)
    else:
        run_audit_pipeline.delay(
            job_id=job_id,
            scan_id=str(scan_id),
            address=address,
            network=network,
            source=source,
            prefs=prefs,
            user_id=str(user_id) if user_id else None,
        )
    return str(scan_id)


# Strong refs so asyncio doesn't garbage-collect in-flight background scans
# (asyncio.create_task only holds a weakref). Discarded when the task
# completes; empty at quiescence.
_inflight_tasks: set[asyncio.Task[Any]] = set()


async def get_scan_progress(job_id: str) -> dict[str, Any] | None:
    raw = await _redis().get(_PROGRESS_KEY.format(job_id=job_id))
    if raw is None:
        return None
    return json.loads(raw)


async def _publish(job_id: str, payload: dict[str, Any]) -> None:
    await _redis().setex(
        _PROGRESS_KEY.format(job_id=job_id),
        _PROGRESS_TTL,
        json.dumps(payload),
    )


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


async def run_audit_pipeline_async(
    *,
    job_id: str,
    scan_id: str,
    address: str,
    network: str,
    source: str | None,
    prefs: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Coroutine body of the scan task — usable both by Celery (sync wrapper
    below) and by the in-process dev path that spawns it as an asyncio.Task
    so the POST /v1/scan handler can return `job_id` immediately.

    Keeping this as a standalone async function means we run the same
    pipeline code in both paths; the Celery task is a thin wrapper that
    just bridges sync→async via `_run_async`.
    """
    scan_uuid = uuid.UUID(scan_id)
    from wr3_api.models.user import DEFAULT_PREFERENCES
    p = {**DEFAULT_PREFERENCES, **(prefs or {})}
    started = time.monotonic()
    try:
        pipeline = AuditPipeline(  # type: ignore[arg-type]
            network=network,
            scan_id=scan_id,
            multi_agent_triage=bool(p.get("multi_agent_triage", True)),
            poc_enabled=bool(p.get("auto_poc", True)),
            fuzzing_enabled=bool(p.get("auto_fuzzing", True)),
        )

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

        # Enrich HIGH/CRITICAL findings with similar historical incidents.
        # One round-trip to api.navy for the whole batch; vector search hits
        # the IVFFlat index on incidents.embedding. Failures here are
        # non-fatal — the scan still finalizes without the enrichment.
        try:
            from audit_engine.llm.router import LLMRouter

            from wr3_api.services import incident_search

            router = LLMRouter()
            await incident_search.enrich_report_with_similar_incidents(
                result, embed_batch=router.embed_batch
            )
        except Exception as e:
            logger.warning("scan.incident_enrich_failed", error=str(e))

        duration = time.monotonic() - started
        await repo.finalize_scan(
            scan_id=scan_uuid,
            report_dict=result,
            duration_seconds=duration,
        )

        # Auto-register for continuous monitoring when the user has it on.
        # Etherscan can't tell us about Solana, so we skip that network —
        # the watcher's poller wouldn't have anything to compare against.
        if user_id and network != "solana" and p.get("continuous_monitoring"):
            try:
                from wr3_api.services import watch_repository as watch_repo
                await watch_repo.ensure_watched(
                    user_id=uuid.UUID(user_id),
                    address=address,
                    network=network,
                )
            except Exception as e:
                logger.warning("scan.watch_register_failed", error=str(e))

        return result
    except Exception as e:
        # Without this guard a crash after stage=scoring (incident_search,
        # report_dict serialization, finalize_scan transaction conflict)
        # leaves the scan row stuck at whatever progress was last written
        # — typically 95%, no error_message — and the SSE consumer polls
        # forever. Mark explicitly failed so the UI can render the error
        # and the user can retry.
        logger.exception("scan.unhandled_error", job_id=job_id, scan_id=scan_id, error=str(e))
        try:
            import sentry_sdk as _sentry
            _sentry.capture_exception(e)
        except Exception:
            pass
        try:
            await _publish(job_id, {"stage": "error", "progress": 0,
                                    "message": str(e)[:300], "scan_id": scan_id})
            await repo.update_progress(
                scan_id=scan_uuid,
                stage="error",
                progress=0,
                error_message=str(e)[:500],
            )
        except Exception:
            logger.exception("scan.error_recording_failed")
        return {"status": "error", "error": str(e)[:300]}


@celery_app.task(name="wr3_api.workers.scan_worker.run_audit_pipeline", bind=True)
def run_audit_pipeline(
    self,
    job_id: str,
    scan_id: str,
    address: str,
    network: str,
    source: str | None,
    prefs: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Celery sync wrapper around `run_audit_pipeline_async`.

    `prefs` carries the owner's feature toggles. On success, if the user
    has `continuous_monitoring=True`, we register the contract for the
    periodic Etherscan-poll watcher.
    """

    async def _run() -> dict[str, Any]:
        return await run_audit_pipeline_async(
            job_id=job_id,
            scan_id=scan_id,
            address=address,
            network=network,
            source=source,
            prefs=prefs,
            user_id=user_id,
        )

    return _run_async(_run())
