import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.clients.postgres_client import get_repository
from app.services.registry_service import RegisterResult


class FakeRepo:
    async def get_registry(self):
        return {"browser": "string"}

    async def current_version(self):
        return 1

    async def register_fields(self, fields, description):
        return RegisterResult(version=2, inserted=dict(fields))


@pytest.fixture
def client():
    with patch("app.main.start_postgres", new_callable=AsyncMock), \
         patch("app.main.stop_postgres", new_callable=AsyncMock):
        from app.main import app

        app.dependency_overrides[get_repository] = lambda: FakeRepo()
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "intelligence"}


def test_infer_registers_new_field(client):
    resp = client.post("/v1/infer", json={"samples": {"age": [30], "browser": ["x"]}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == 2
    assert body["registered"] == [{"name": "age", "type": "int"}]
    assert body["existing"] == [{"name": "browser", "type": "string"}]


def test_infer_rejects_unsafe_name(client):
    resp = client.post("/v1/infer", json={"samples": {"x`; DROP TABLE t; --": ["v"]}})
    assert resp.status_code == 200
    assert resp.json()["rejected"][0]["reason"] == "invalid_name"


def test_infer_rejects_empty_samples(client):
    assert client.post("/v1/infer", json={"samples": {}}).status_code == 422


def test_infer_rejects_missing_body(client):
    assert client.post("/v1/infer", json={}).status_code == 422