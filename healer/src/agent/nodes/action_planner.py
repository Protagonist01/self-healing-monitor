from typing import List
from healer.src.agent.state import HealerState, PlannedAction
from healer.src.agent.actions.registry import get_keyword_map


def action_planner_node(state: HealerState) -> HealerState:
    """
    LangGraph node: action_planner.
    Plans and ranks possible remediation actions based on the LLM diagnosis.
    Uses the configurable keyword map from the action registry, and supports
    cascading-failure awareness via correlation context.
    The safest action is selected as `selected_action`.
    """
    diagnosis = state["diagnosis"]
    if not diagnosis:
        state["errors"].append("Action planner node failed: no diagnosis available.")
        return state

    root_cause = diagnosis["root_cause"].lower()
    planned_actions: List[PlannedAction] = []

    keyword_map = get_keyword_map()

    for entry in keyword_map:
        if any(keyword in root_cause for keyword in entry["keywords"]):
            planned_actions = list(entry["actions"])
            break

    if not planned_actions:
        planned_actions = [
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Standard low-risk container restart to clear transient issues.",
            },
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operations for manual investigation as root cause is ambiguous.",
            },
        ]

    # If correlation indicates a cascading failure, prefer NOTIFY_ONLY first
    context = state.get("context") or {}
    correlation = context.get("correlation") or {}
    if correlation.get("is_cascading"):
        planned_actions.insert(
            0,
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Cascading failure detected across multiple services — notify operators before taking action.",
            },
        )

    state["action_plan"] = planned_actions

    if planned_actions:
        state["selected_action"] = planned_actions[0]["action"]
    else:
        state["selected_action"] = "NOTIFY_ONLY"

    return state
