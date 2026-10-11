from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

SAMPLE_EVENT = {
    "event_type": "page_view",
    "user_id": "user-1",
    "session_id": "session-1",
    "url": "https://example.com/pricing",
    "timestamp": "2026-09-13T10:00:00Z",
    "properties": {"browser": "chrome", "referrer": "google"},
}


@pytest.fixture
def client():
    # Kafka producer lifecycle and the actual publish call are mocked so
    # these tests run with no live Kafka broker.
    with patch("app.main.start_producer", new_callable=AsyncMock), \
         patch("app.main.stop_producer", new_callable=AsyncMock), \
         patch("app.api.routes.publish_raw_event", new_callable=AsyncMock):
        from app.main import app

        with TestClient(app) as c:
            yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ingest_event_rejects_missing_api_key(client):
    response = client.post("/events", json=SAMPLE_EVENT)
    assert response.status_code == 401


def test_ingest_event_rejects_wrong_api_key(client):
    response = client.post("/events", json=SAMPLE_EVENT, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401


def test_ingest_event_success(client):
    response = client.post("/events", json=SAMPLE_EVENT, headers={"X-API-Key": "dev-key-123"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert "event_id" in body