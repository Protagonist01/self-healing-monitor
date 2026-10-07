import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from healer.src import main
from healer.src.audit.db import get_db_connection
from healer.src.audit.logger import queue_human_approval, write_audit_record
from healer.src.config import Settings, settings
from healer.src.queue.worker import enqueue_incident, reset_stale_incidents


def pending_state(base_state):
    state = copy.deepcopy(base_state)
    state.update(
        selected_action="RESTART_CONTAINER",
        diagnosis={"confidence": 0.85},
        policy_gate={"decision": "human_approval", "checks": {}},
    )
    state["alert"]["received_at"] = datetime.now(timezone.utc).isoformat()
    return state


def test_invalid_approval_does_not_consume_pending_action(base_state):
    state = pending_state(base_state)
    queue_human_approval(state)
    client = TestClient(main.app)
    assert (
        client.post(
            "/approval/action", json={"incident_id": state["incident_id"], "status": "typo"}
        ).status_code
        == 422
    )
    assert len(client.get("/approval/queue").json()) == 1


def test_concurrent_approvals_execute_once_and_verify(base_state):
    state = pending_state(base_state)
    queue_human_approval(state)

    def execute(s):
        s["execution"] = {"status": "success", "alert_resolved": False, "output": "Restarted"}
        return s

    def approve(_):
        return main.process_approval(
            main.ApprovalRequest(incident_id=state["incident_id"], status="approved")
        )

    with (
        patch.object(main, "executor_node", side_effect=execute) as action,
        patch.object(main, "verify_action_node", side_effect=lambda s: s) as verify,
    ):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve, i) for i in range(2)]
            outcomes = []
            for future in futures:
                try:
                    outcomes.append(future.result())
                except main.HTTPException as exc:
                    assert exc.status_code == 404
        assert len(outcomes) == 1
        action.assert_called_once()
        verify.assert_called_once()
        assert outcomes[0]["execution"]["alert_resolved"] is False


def test_pending_intake_deduplicates_concurrent_alerts(base_state):
    state = pending_state(base_state)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: enqueue_incident(state), range(2)))
    assert sum(result is not None for result in results) == 1


def test_dedup_uses_past_window(base_state):
    state = pending_state(base_state)
    state["alert"]["received_at"] = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    write_audit_record(state)
    assert main.is_duplicate_alert("HighMemoryUsage", "leaky_service")
    with patch.object(settings, "DEDUP_WINDOW_SECONDS", 1):
        assert not main.is_duplicate_alert("HighMemoryUsage", "leaky_service")


def test_interrupted_actions_are_not_replayed(base_state):
    enqueue_incident(pending_state(base_state))
    conn = get_db_connection()
    conn.execute("UPDATE incident_queue SET status = 'processing'")
    conn.commit()
    reset_stale_incidents()
    assert conn.execute("SELECT status FROM incident_queue").fetchone()[0] == "failed"
    conn.close()


def test_production_rejects_unsafe_settings():
    with pytest.raises(ValidationError, match="HEALER_API_KEY"):
        Settings(_env_file=None, ENVIRONMENT="production", HEALER_API_KEY="")
    with pytest.raises(ValidationError, match="DOCKER_ALLOWED_SERVICES"):
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            HEALER_API_KEY="x" * 48,
            DOCKER_ALLOWED_SERVICES="",
        )


def test_missing_telemetry_is_not_fabricated():
    from healer.src.agent.nodes.context_gather import (
        get_prometheus_metrics,
        get_loki_logs,
        get_recent_deploys,
    )

    with patch("httpx.get", side_effect=RuntimeError("offline")):
        assert get_prometheus_metrics("svc", "HighMemoryUsage")["metrics_raw"] == []
        assert get_loki_logs("svc")["log_raw"] == []
        assert get_recent_deploys("svc") == []


def test_disabled_demo_endpoint():
    with patch.object(settings, "ENABLE_DEMO_ENDPOINT", False):
        assert TestClient(main.app).post("/demo/incident", json={}).status_code == 404


def test_notifications_check_http_status():
    from healer.src.agent.graph import _send_notification
    import httpx

    response = httpx.Response(500, request=httpx.Request("POST", "https://example.invalid"))
    with (
        patch.object(settings, "SLACK_WEBHOOK_URL", "https://example.invalid"),
        patch("httpx.post", return_value=response),
    ):
        assert _send_notification("svc", "incident").startswith("Failed")


@pytest.mark.parametrize(
    "alerts",
    [
        [{"labels": None}],
        [{"labels": {"service": 42}}],
        [{"annotations": []}],
        [{"labels": {"service": "x" * 4097}}],
        [{}] * 101,
    ],
)
def test_malformed_alerts_rejected_before_intake(alerts):
    with patch.object(main, "enqueue_incident") as enqueue:
        response = TestClient(main.app).post("/webhook/alert", json={"alerts": alerts})
    assert response.status_code == 422
    enqueue.assert_not_called()


@pytest.mark.parametrize(
    "field,value",
    [
        ("CONFIDENCE_THRESHOLD", -1),
        ("CONFIDENCE_THRESHOLD", 2),
        ("RATE_LIMIT_PER_MINUTE", 0),
        ("MAX_AUTO_EXECUTION_RETRIES", 100),
        ("VERIFY_DELAY_SECONDS", -1),
    ],
)
def test_invalid_safety_configuration_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_chroma_server_mode_is_disabled():
    with pytest.raises(ValidationError, match="Chroma server mode"):
        Settings(_env_file=None, CHROMA_SERVER_URL="http://server.invalid")
