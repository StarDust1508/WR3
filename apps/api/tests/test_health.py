from fastapi.testclient import TestClient

from wr3_api.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version() -> None:
    client = TestClient(app)
    r = client.get("/v1/version")
    assert r.status_code == 200
    assert "version" in r.json()
