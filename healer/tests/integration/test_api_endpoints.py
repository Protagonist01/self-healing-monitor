"""
Integration tests for the webhook API endpoints using FastAPI TestClient.

These tests cover the webhook intake, demo incident trigger, health endpoint,
and auth enforcement.
"""

from unittest.mock import patch
from fastapi.testclient import TestClient


def _create_client_with_no_auth():
    from healer.src.main import app

    return TestClient(app)


def test_health_endpoint():
    client = _create_client_with_no_auth()
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "audit_backend" in data
    assert "auth_enabled" in data


def test_webhook_ignores_resolved_alerts():
    client = _create_client_with_no_auth()
    payload = {
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {"alertname": "HighMemoryUsage", "service": "leaky_service"},
                "annotations": {},
            }
        ],
    }
    with patch("healer.src.main.enqueue_incident") as mock_enqueue:
        response = client.post("/webhook/alert", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        mock_enqueue.assert_not_called()


def test_webhook_accepts_firing_alert():
    client = _create_client_with_no_auth()
    payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "HighMemoryUsage", "service": "leaky_service"},
                "annotations": {"summary": "Memory is high"},
            }
        ],
    }
    with patch("healer.src.main.enqueue_incident") as mock_enqueue:
        response = client.post("/webhook/alert", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        assert len(response.json()["incident_ids"]) == 1
        mock_enqueue.assert_called_once()


def test_webhook_auth_enforced_when_key_set():
    from healer.src.config import settings
    from healer.src.main import app

    with patch.object(settings, "HEALER_API_KEY", "secret-key-123"):
        client = TestClient(app)
        assert client.post("/webhook/alert", json={"alerts": []}).status_code == 401
        for headers in (
            {"X-API-Key": "secret-key-123"},
            {"Authorization": "Bearer secret-key-123"},
        ):
            assert (
                client.post("/webhook/alert", json={"alerts": []}, headers=headers).status_code
                == 200
            )


def test_demo_incident_creates_incident():
    client = _create_client_with_no_auth()
    from healer.src.config import settings

    with (
        patch.object(settings, "ENABLE_DEMO_ENDPOINT", True),
        patch("healer.src.main.enqueue_incident") as mock_enqueue,
    ):
        response = client.post("/demo/incident", json={"service": "flaky_service"})
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        mock_enqueue.assert_called_once()
