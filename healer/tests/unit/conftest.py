import pytest


@pytest.fixture
def base_state():
    return {
        "incident_id": "test-id-123",
        "alert": {
            "name": "HighMemoryUsage",
            "service": "payment-service",
            "severity": "warning",
            "labels": {"alertname": "HighMemoryUsage", "service": "payment-service"},
            "annotations": {},
            "received_at": "2026-06-23T22:00:00+00:00"
        },
        "context": None,
        "diagnosis": {
            "root_cause": "Memory leak detected",
            "confidence": 0.85,
            "supporting_evidence": ["Evidence 1"],
            "llm_model": "test-model",
            "llm_tokens_used": 100
        },
        "action_plan": [
            {"action": "RESTART_CONTAINER", "impact": "low", "reasoning": "Reason 1"},
            {"action": "SCALE_REPLICAS", "impact": "medium", "reasoning": "Reason 2"},
            {"action": "ROLLBACK_DEPLOY", "impact": "high", "reasoning": "Reason 3"}
        ],
        "selected_action": "RESTART_CONTAINER",
        "policy_gate": None,
        "execution": None,
        "retry_count": 0,
        "errors": []
    }
