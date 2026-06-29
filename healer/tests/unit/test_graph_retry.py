from healer.src.agent.graph import prepare_retry_node, route_after_execution


def test_failed_execution_routes_to_retry_once(base_state):
    base_state["execution"] = {
        "status": "failure",
        "started_at": "2026-06-23T22:00:00+00:00",
        "completed_at": "2026-06-23T22:00:01+00:00",
        "duration_seconds": 1.0,
        "output": "container not found",
        "alert_resolved": False,
    }
    base_state["retry_count"] = 0

    assert route_after_execution(base_state) == "prepare_retry"


def test_second_failed_execution_routes_to_audit(base_state):
    base_state["execution"] = {
        "status": "failure",
        "started_at": "2026-06-23T22:00:00+00:00",
        "completed_at": "2026-06-23T22:00:01+00:00",
        "duration_seconds": 1.0,
        "output": "container not found",
        "alert_resolved": False,
    }
    base_state["retry_count"] = 1

    assert route_after_execution(base_state) == "audit_log"


def test_prepare_retry_records_failure(base_state):
    base_state["execution"] = {"status": "failure", "output": "container not found"}

    state = prepare_retry_node(base_state)

    assert state["retry_count"] == 1
    assert "container not found" in state["errors"][0]
