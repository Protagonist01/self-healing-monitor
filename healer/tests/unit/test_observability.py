from unittest.mock import patch

import pytest

from healer.src.agent.graph import audit_log_node


@pytest.mark.parametrize("resolved", [True, False])
def test_resolution_counter_uses_verified_outcome(base_state, resolved):
    base_state["execution"] = {"status": "success", "alert_resolved": resolved}
    with (
        patch("healer.src.agent.graph.write_audit_record"),
        patch("healer.src.agent.graph.record_outcome"),
        patch("healer.src.agent.graph.RESOLVED_COUNTER") as counter,
    ):
        audit_log_node(base_state)
    assert counter.labels.return_value.inc.call_count == int(resolved)


def test_multiple_rows_for_one_service_are_not_cascading(base_state):
    from healer.src.agent.nodes.correlation import get_correlation_context
    from healer.src.audit.logger import write_audit_record

    base_state["alert"]["service"] = "dependency"
    from datetime import datetime, timezone

    base_state["alert"]["received_at"] = datetime.now(timezone.utc).isoformat()
    write_audit_record(base_state)
    write_audit_record(base_state)
    result = get_correlation_context("caller", "HighMemoryUsage")
    assert len(result["related_incidents"]) == 2
    assert result["is_cascading"] is False
