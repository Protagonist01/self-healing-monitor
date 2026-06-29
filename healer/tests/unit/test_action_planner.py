from healer.src.agent.nodes.action_planner import action_planner_node


def test_memory_diagnosis_prefers_restart(base_state):
    base_state["diagnosis"]["root_cause"] = "OOMKilled after memory leak"

    state = action_planner_node(base_state)

    assert state["selected_action"] == "RESTART_CONTAINER"
    assert [item["action"] for item in state["action_plan"]] == [
        "RESTART_CONTAINER",
        "SCALE_REPLICAS",
        "ROLLBACK_DEPLOY",
    ]


def test_error_rate_diagnosis_routes_rollback_to_policy(base_state):
    base_state["diagnosis"]["root_cause"] = "Recent code bug causing HTTP 500 exceptions"

    state = action_planner_node(base_state)

    assert state["selected_action"] == "ROLLBACK_DEPLOY"
    assert state["action_plan"][0]["impact"] == "high"


def test_unknown_diagnosis_uses_low_risk_fallback(base_state):
    base_state["diagnosis"]["root_cause"] = "Ambiguous behavior with weak signal"

    state = action_planner_node(base_state)

    assert state["selected_action"] == "RESTART_CONTAINER"
    assert state["action_plan"][-1]["action"] == "NOTIFY_ONLY"
