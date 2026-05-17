"""Request-ID middleware — correlation across logs and response.

We mount the middleware on a tiny FastAPI app (not the real one) so we
can probe header behaviour without needing Postgres / Redis up.
"""

from __future__ import annotations

import re

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from wr3_api.middleware.request_id import RequestIdMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/echo")
    async def echo(request: Request) -> dict:
        # Echo the bound request_id so we can assert end-to-end
        # propagation from the middleware into route handler state.
        return {"id": request.state.request_id}

    return app


def test_generates_id_when_header_absent() -> None:
    client = TestClient(_app())
    r = client.get("/echo")
    assert r.status_code == 200
    body_id = r.json()["id"]
    assert isinstance(body_id, str) and len(body_id) >= 10
    assert r.headers["x-request-id"] == body_id


def test_passes_through_caller_supplied_id() -> None:
    """Operators paste request ids from caller logs all the time —
    don't override them, just echo back."""
    client = TestClient(_app())
    r = client.get("/echo", headers={"X-Request-Id": "abc-correlation-123"})
    assert r.json()["id"] == "abc-correlation-123"
    assert r.headers["x-request-id"] == "abc-correlation-123"


def test_truncates_pathological_header() -> None:
    """A 10 KB request-id in logs is a poisoning vector — cap at 64."""
    client = TestClient(_app())
    huge = "x" * 1000
    r = client.get("/echo", headers={"X-Request-Id": huge})
    returned = r.headers["x-request-id"]
    assert len(returned) <= 64
    # First 64 chars should be ours
    assert returned == "x" * 64


def test_id_is_unique_per_request() -> None:
    """Two unauth'd requests get distinct ids — no caching mishap."""
    client = TestClient(_app())
    a = client.get("/echo").headers["x-request-id"]
    b = client.get("/echo").headers["x-request-id"]
    assert a != b


def test_id_format_when_generated() -> None:
    """Generated ids are short hex (22 chars), so they fit in log lines
    without wrapping — lock the format with a regex."""
    client = TestClient(_app())
    rid = client.get("/echo").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{22}", rid), f"unexpected id shape: {rid}"
