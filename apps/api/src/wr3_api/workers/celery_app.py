import os

from celery import Celery

from wr3_api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "wr3",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["wr3_api.workers.scan_worker"],
)

# Eager mode for dev/test: runs tasks inline in the calling process, so we
# don't need a separate Celery worker for a smoke run. NEVER enable in prod.
_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="wr3.default",
    task_routes={
        "wr3_api.workers.scan_worker.run_audit_pipeline": {"queue": "wr3.audit"},
    },
    task_always_eager=_eager,
    task_eager_propagates=_eager,
)
