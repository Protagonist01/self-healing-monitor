"""
Unit tests for the feedback loop module.
"""

from healer.src.feedback import format_feedback_for_prompt


def test_format_feedback_empty():
    assert format_feedback_for_prompt([]) == ""


def test_format_feedback_with_outcomes():
    outcomes = [
        {
            "root_cause": "memory leak",
            "action_taken": "RESTART_CONTAINER",
            "alert_resolved": True,
            "verified": True,
        },
        {
            "root_cause": "bad deploy",
            "action_taken": "ROLLBACK_DEPLOY",
            "alert_resolved": False,
            "verified": False,
        },
    ]
    result = format_feedback_for_prompt(outcomes)
    assert "Past similar incidents" in result
    assert "memory leak" in result
    assert "RESTART_CONTAINER" in result
    assert "resolved" in result
    assert "unresolved" in result


def test_format_feedback_truncates_long_list():
    outcomes = [
        {
            "root_cause": f"cause-{i}",
            "action_taken": "RESTART_CONTAINER",
            "alert_resolved": True,
            "verified": True,
        }
        for i in range(10)
    ]
    result = format_feedback_for_prompt(outcomes[:3])
    assert result.count("cause-") == 3
