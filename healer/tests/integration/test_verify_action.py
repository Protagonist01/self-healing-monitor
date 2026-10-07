"""
Integration tests for the post-action verification node.

These tests verify that the verification node correctly queries Prometheus
and updates the alert_resolved flag based on actual metrics.
"""

from unittest.mock import patch
from datetime import datetime, timezone

import httpx
import pytest
from healer.src.agent.nodes.verify_action import verify_action_node, _is_alert_still_firing


def test_verify_memory_alert_resolved(base_state):
    """When memory drops below threshold, verification passes."""
    base_state["execution"] = {
        "status": "success",
        "started_at": None,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 0.1,
        "output": "Container restarted.",
        "alert_resolved": True,
    }

    fake_metrics = [{"metric": {}, "value": ["1234", "40000000"]}]

    with patch("healer.src.config.settings") as mock_settings:
        mock_settings.VERIFY_DELAY_SECONDS = 0
        mock_settings.PROMETHEUS_URL = "http://localhost:9090"
        with (
            patch(
                "healer.src.agent.nodes.verify_action._query_prometheus", return_value=fake_metrics
            ),
            patch("healer.src.agent.nodes.verify_action._has_fresh_scrape", return_value=True),
        ):
            state = verify_action_node(base_state)

    assert state["verification"]["verified"] is True
    assert state["verification"]["alert_still_firing"] is False
    assert state["execution"]["alert_resolved"] is True


def test_verify_memory_alert_still_firing(base_state):
    """When memory is still above threshold, verification fails and corrects alert_resolved."""
    base_state["execution"] = {
        "status": "success",
        "started_at": None,
        "completed_at": None,
        "duration_seconds": 0.1,
        "output": "Container restarted.",
        "alert_resolved": True,
    }

    fake_metrics = [{"metric": {}, "value": ["1234", "80000000"]}]

    with patch("healer.src.config.settings") as mock_settings:
        mock_settings.VERIFY_DELAY_SECONDS = 0
        mock_settings.PROMETHEUS_URL = "http://localhost:9090"
        with patch(
            "healer.src.agent.nodes.verify_action._query_prometheus", return_value=fake_metrics
        ):
            state = verify_action_node(base_state)

    assert state["verification"]["verified"] is False
    assert state["verification"]["alert_still_firing"] is True
    assert state["execution"]["alert_resolved"] is False


def test_verify_skipped_for_pending_execution(base_state):
    """Verification is not performed when execution is pending."""
    base_state["execution"] = {"status": "pending", "output": "Queued."}

    with patch("healer.src.config.settings") as mock_settings:
        mock_settings.VERIFY_DELAY_SECONDS = 0
        state = verify_action_node(base_state)

    assert "verification" not in state or state.get("verification") is None


def test_is_alert_still_firing_memory():
    assert _is_alert_still_firing("svc", "HighMemoryUsage", [{"value": ["1", "40000000"]}]) is False
    assert _is_alert_still_firing("svc", "HighMemoryUsage", [{"value": ["1", "80000000"]}]) is True


def test_is_alert_still_firing_no_metrics():
    """When no metrics are returned, assume still firing (fail safe)."""
    assert _is_alert_still_firing("svc", "HighMemoryUsage", []) is True


def test_cached_metrics_do_not_prove_recovery(base_state):
    base_state["execution"] = {
        "status": "success",
        "output": "Restarted",
        "alert_resolved": False,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    with (
        patch(
            "healer.src.agent.nodes.verify_action._query_prometheus",
            return_value=[{"value": ["1", "40000000"]}],
        ),
        patch("healer.src.agent.nodes.verify_action._has_fresh_scrape", return_value=False),
    ):
        result = verify_action_node(base_state)
    assert result["verification"]["verified"] is False
    assert result["execution"]["alert_resolved"] is False


def test_notification_cannot_count_as_repair(base_state):
    base_state["selected_action"] = "NOTIFY_ONLY"
    base_state["execution"] = {"status": "success", "output": "Notified", "alert_resolved": False}
    with patch("healer.src.agent.nodes.verify_action._query_prometheus") as query:
        result = verify_action_node(base_state)
    query.assert_not_called()
    assert result["execution"]["alert_resolved"] is False


@pytest.mark.parametrize("results,expected", [([], False), ([{"value": ["1", "1"]}], True)])
def test_fresh_scrape_uses_source_timestamp(results, expected):
    from healer.src.agent.nodes.verify_action import _has_fresh_scrape

    response = httpx.Response(
        200,
        json={"status": "success", "data": {"result": results}},
        request=httpx.Request("GET", "http://prometheus.invalid"),
    )
    completed = "2026-10-07T12:00:00+00:00"
    with patch("httpx.get", return_value=response) as get:
        assert _has_fresh_scrape("svc", completed) is expected
    assert "timestamp(up" in get.call_args.kwargs["params"]["query"]
    assert (
        str(datetime.fromisoformat(completed).timestamp())
        in get.call_args.kwargs["params"]["query"]
    )


def test_fresh_scrape_rejects_missing_completion_time():
    from healer.src.agent.nodes.verify_action import _has_fresh_scrape

    assert _has_fresh_scrape("svc", None) is False
