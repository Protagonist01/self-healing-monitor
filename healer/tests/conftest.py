"""Keep test imports and runtime isolated from developer secrets and services."""

import os
import tempfile
from pathlib import Path

import pytest

_test_dir = tempfile.TemporaryDirectory(prefix="healer-tests-", ignore_cleanup_errors=True)
for key, value in {
    "ENVIRONMENT": "development",
    "OPENAI_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "HEALER_API_KEY": "",
    "SLACK_WEBHOOK_URL": "",
    "AUDIT_BACKEND": "sqlite",
    "CHROMA_DB_DIR": str(Path(_test_dir.name) / "chroma"),
    "CHROMA_SERVER_URL": "",
    "SQLITE_PATH": str(Path(_test_dir.name) / "audit.db"),
    "REQUIRE_HUMAN_APPROVAL": "true",
    "VERIFY_DELAY_SECONDS": "0",
}.items():
    os.environ[key] = value


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    from healer.src.config import settings
    from healer.src.audit.db import init_db
    from healer.src.security import rate_limit
    import httpx

    monkeypatch.setattr(settings, "AUDIT_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setattr(rate_limit, "_rate_limiter", None)
    init_db()

    def no_network(*args, **kwargs):
        raise RuntimeError("External network access is disabled in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)


@pytest.fixture
def base_state():
    return {
        "incident_id": "test-incident",
        "alert": {
            "name": "HighMemoryUsage",
            "service": "leaky_service",
            "labels": {},
            "received_at": "2026-09-11T00:00:00+00:00",
        },
        "context": None,
        "diagnosis": None,
        "action_plan": None,
        "selected_action": None,
        "policy_gate": None,
        "execution": None,
        "retry_count": 0,
        "errors": [],
    }
