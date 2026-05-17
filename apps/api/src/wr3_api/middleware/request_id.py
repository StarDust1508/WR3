"""Request-ID correlation middleware.

Why:
    structlog already gives us key=value lines, but without a request
    correlation token it's impossible to follow one user's flow across
    multiple log lines on a busy server. This middleware:

      1. Reads X-Request-Id from the incoming request, or generates a
         short opaque id if absent.
      2. Binds it as `request_id` on every log line via structlog
         contextvars for the lifetime of the request.
      3. Echoes the value back on the response as X-Request-Id so the
         caller (Mini App, CF Workers proxy, support tooling) can paste
         it into a bug report and we can grep the logs.

    The middleware is intentionally minimal — no body capture, no
    structured request logging here. Logs come from the route handlers
    using the bound request_id automatically.
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

# Cap the inbound header so a malicious caller can't poison logs with a
# 10 KB "request id". 64 chars is plenty for any reasonable trace id
# format (UUID, ksuid, Datadog, Lightstep…).
_MAX_INCOMING_LEN = 64


def _new_request_id() -> str:
    """Short opaque id — 22 chars of url-safe base64."""
    return uuid.uuid4().hex[:22]


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")[:_MAX_INCOMING_LEN].strip()
        request_id = incoming or _new_request_id()

        # Make it available to downstream handlers via request.state, and
        # bind it onto every structlog line emitted during this request.
        request.state.request_id = request_id
        bind = structlog.contextvars.bind_contextvars
        unbind = structlog.contextvars.unbind_contextvars
        bind(request_id=request_id, path=request.url.path, method=request.method)

        started = time.monotonic()
        try:
            response: Response = await call_next(request)
        except Exception:
            # Re-raise — FastAPI's exception handler logs the traceback.
            # We just make sure the contextvars are cleaned up.
            unbind("request_id", "path", "method")
            raise

        # Surface the id to the client.
        response.headers["X-Request-Id"] = request_id
        # One terse access-log line per request. Detailed traces live in
        # the route-level info logs; this is for ops dashboards.
        logger.info(
            "http.request",
            status=response.status_code,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        unbind("request_id", "path", "method")
        return response
