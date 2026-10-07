"""
Scenario tests: end-to-end pipeline tests with mocked external dependencies.

These tests run the full LangGraph pipeline through healer_app.invoke() with
mocked Prometheus, Loki, LLM, and Docker to verify the complete flow from
alert intake through audit logging.
"""

from unittest.mock import patch
from healer.src.agent.graph import build_healer_graph


def _mock_context_data():
    return {
        "metrics_window_minutes": 30,
        "metrics_summary": "Memory usage at 94.2%",
        "metrics_raw": [],
        "log_lines_count": 3,
        "log_summary": "Repeated OOMKilled events detected in container logs.",
        "log_raw": ["OOMKilled", "container restarting", "memory limit exceeded"],
        "recent_deploys": ["v2.4.1 deployed 47 minutes ago"],
        "runbook_matched": "high_memory.md",
        "runbook_excerpt": "## High Memory Response\nRestart the container.",
    }


def _base_incident_state():
    return {
        "incident_id": "scenario-test-001",
        "alert": {
            "name": "HighMemoryUsage",
            "service": "leaky_service",
            "severity": "warning",
            "labels": {"alertname": "HighMemoryUsage", "service": "leaky_service"},
            "annotations": {"summary": "Memory high"},
            "received_at": "2026-06-23T22:00:00+00:00",
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


def test_scenario_high_memory_auto_execute():
    """
    Scenario: High memory alert with high-confidence OOM diagnosis.
    Expected: auto_execute -> RESTART_CONTAINER -> success -> verified.
    """
    state = _base_incident_state()

    mock_diagnosis = {
        "root_cause": "oom memory leak detected in request handler",
        "confidence": 0.90,
        "supporting_evidence": ["OOMKilled log lines"],
        "llm_model": "test",
        "llm_tokens_used": 0,
    }

    with (
        patch("healer.src.agent.nodes.policy_gate.settings") as mock_settings,
        patch(
            "healer.src.agent.nodes.context_gather.get_prometheus_metrics",
            return_value={"metrics_summary": "94.2%", "metrics_raw": []},
        ),
        patch(
            "healer.src.agent.nodes.context_gather.get_loki_logs",
            return_value={
                "log_lines_count": 1,
                "log_summary": "OOMKilled",
                "log_raw": ["OOMKilled"],
            },
        ),
        patch("healer.src.agent.nodes.context_gather.get_recent_deploys", return_value=[]),
        patch(
            "healer.src.agent.nodes.context_gather.get_keyword_runbook",
            return_value={
                "runbook_matched": "high_memory.md",
                "runbook_excerpt": "Restart container",
            },
        ),
        patch("healer.src.agent.graph.diagnose_node") as mock_diag,
        patch(
            "healer.src.executor.docker_executor.docker_executor.restart_container",
            return_value={"status": "success", "output": "Container restarted."},
        ),
        patch("healer.src.agent.graph.write_audit_record"),
        patch("healer.src.agent.graph.record_outcome"),
    ):
        mock_settings.CONFIDENCE_THRESHOLD = 0.75
        mock_settings.ALLOWED_AUTO_ACTIONS = ["RESTART_CONTAINER", "NOTIFY_ONLY"]
        mock_settings.REQUIRE_HUMAN_APPROVAL = False
        mock_settings.MAX_AUTO_EXECUTION_RETRIES = 1
        mock_settings.VERIFY_DELAY_SECONDS = 0
        mock_settings.PROMETHEUS_URL = "http://localhost:9090"
        mock_settings.audit_backend_name = "sqlite"
        mock_settings.allowed_actions_set = {"RESTART_CONTAINER", "NOTIFY_ONLY"}
        mock_settings.DOCKER_ALLOWED_SERVICES = ""

        def diag_side_effect(s):
            s["diagnosis"] = mock_diagnosis
            return s

        mock_diag.side_effect = diag_side_effect

        with patch("healer.src.agent.nodes.verify_action._query_prometheus", return_value=[]):
            result = build_healer_graph().invoke(state)

    assert result["policy_gate"]["decision"] == "auto_execute"
    assert result["selected_action"] == "RESTART_CONTAINER"
    assert result["execution"]["status"] == "success"


def test_scenario_low_confidence_routes_to_approval():
    """
    Scenario: Alert with low-confidence diagnosis.
    Expected: human_approval -> queued, no execution.
    """
    state = _base_incident_state()
    state["incident_id"] = "scenario-test-002"

    mock_diagnosis = {
        "root_cause": "uncertain - possible memory issue",
        "confidence": 0.50,
        "supporting_evidence": ["insufficient data"],
        "llm_model": "test",
        "llm_tokens_used": 0,
    }

    with (
        patch("healer.src.agent.nodes.policy_gate.settings") as mock_settings,
        patch(
            "healer.src.agent.nodes.context_gather.get_prometheus_metrics",
            return_value={"metrics_summary": "94.2%", "metrics_raw": []},
        ),
        patch(
            "healer.src.agent.nodes.context_gather.get_loki_logs",
            return_value={
                "log_lines_count": 1,
                "log_summary": "OOMKilled",
                "log_raw": ["OOMKilled"],
            },
        ),
        patch("healer.src.agent.nodes.context_gather.get_recent_deploys", return_value=[]),
        patch(
            "healer.src.agent.nodes.context_gather.get_keyword_runbook",
            return_value={"runbook_matched": "high_memory.md", "runbook_excerpt": "Restart"},
        ),
        patch("healer.src.agent.graph.diagnose_node") as mock_diag,
        patch("healer.src.agent.graph.write_audit_record"),
        patch("healer.src.agent.graph.queue_human_approval"),
        patch("healer.src.agent.graph.record_outcome"),
    ):
        mock_settings.CONFIDENCE_THRESHOLD = 0.75
        mock_settings.ALLOWED_AUTO_ACTIONS = ["RESTART_CONTAINER", "NOTIFY_ONLY"]
        mock_settings.REQUIRE_HUMAN_APPROVAL = False
        mock_settings.MAX_AUTO_EXECUTION_RETRIES = 1
        mock_settings.VERIFY_DELAY_SECONDS = 0
        mock_settings.PROMETHEUS_URL = "http://localhost:9090"
        mock_settings.audit_backend_name = "sqlite"
        mock_settings.allowed_actions_set = {"RESTART_CONTAINER", "NOTIFY_ONLY"}

        def diag_side_effect(s):
            s["diagnosis"] = mock_diagnosis
            return s

        mock_diag.side_effect = diag_side_effect

        result = build_healer_graph().invoke(state)

    assert result["policy_gate"]["decision"] == "human_approval"
    assert result["execution"]["status"] == "pending"


def test_scenario_global_override_routes_all_to_approval():
    """
    Scenario: REQUIRE_HUMAN_APPROVAL=True forces everything to human approval.
    """
    state = _base_incident_state()
    state["incident_id"] = "scenario-test-003"

    mock_diagnosis = {
        "root_cause": "oom memory leak",
        "confidence": 0.95,
        "supporting_evidence": ["OOMKilled"],
        "llm_model": "test",
        "llm_tokens_used": 0,
    }

    with (
        patch("healer.src.agent.nodes.policy_gate.settings") as mock_settings,
        patch(
            "healer.src.agent.nodes.context_gather.get_prometheus_metrics",
            return_value={"metrics_summary": "94.2%", "metrics_raw": []},
        ),
        patch(
            "healer.src.agent.nodes.context_gather.get_loki_logs",
            return_value={
                "log_lines_count": 1,
                "log_summary": "OOMKilled",
                "log_raw": ["OOMKilled"],
            },
        ),
        patch("healer.src.agent.nodes.context_gather.get_recent_deploys", return_value=[]),
        patch(
            "healer.src.agent.nodes.context_gather.get_keyword_runbook",
            return_value={"runbook_matched": "high_memory.md", "runbook_excerpt": "Restart"},
        ),
        patch("healer.src.agent.graph.diagnose_node") as mock_diag,
        patch("healer.src.agent.graph.write_audit_record"),
        patch("healer.src.agent.graph.queue_human_approval"),
        patch("healer.src.agent.graph.record_outcome"),
    ):
        mock_settings.CONFIDENCE_THRESHOLD = 0.75
        mock_settings.ALLOWED_AUTO_ACTIONS = ["RESTART_CONTAINER", "NOTIFY_ONLY"]
        mock_settings.REQUIRE_HUMAN_APPROVAL = True
        mock_settings.MAX_AUTO_EXECUTION_RETRIES = 1
        mock_settings.VERIFY_DELAY_SECONDS = 0
        mock_settings.PROMETHEUS_URL = "http://localhost:9090"
        mock_settings.audit_backend_name = "sqlite"
        mock_settings.allowed_actions_set = {"RESTART_CONTAINER", "NOTIFY_ONLY"}

        def diag_side_effect(s):
            s["diagnosis"] = mock_diagnosis
            return s

        mock_diag.side_effect = diag_side_effect

        result = build_healer_graph().invoke(state)

    assert result["policy_gate"]["decision"] == "human_approval"
    assert result["execution"]["status"] == "pending"
