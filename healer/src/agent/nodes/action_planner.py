import json
from typing import List
from healer.src.agent.state import HealerState, PlannedAction

def action_planner_node(state: HealerState) -> HealerState:
    """
    LangGraph node: action_planner.
    Plans and ranks possible remediation actions based on the LLM diagnosis.
    The safest action is selected as `selected_action`.
    """
    diagnosis = state["diagnosis"]
    if not diagnosis:
        state["errors"].append("Action planner node failed: no diagnosis available.")
        return state

    root_cause = diagnosis["root_cause"].lower()
    planned_actions: List[PlannedAction] = []

    # Map root causes to planned actions ranked by safety/risk
    if "oom" in root_cause or "memory" in root_cause or "leak" in root_cause:
        planned_actions = [
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Reclaim memory by restarting the container. This resolves the immediate crash loop."
            },
            {
                "action": "SCALE_REPLICAS",
                "impact": "medium",
                "reasoning": "Increase replica count to distribute load and slow down memory accumulation."
            },
            {
                "action": "ROLLBACK_DEPLOY",
                "impact": "high",
                "reasoning": "Rollback to the previous deployment version since a memory leak was introduced recently."
            }
        ]
    elif "500" in root_cause or "bug" in root_cause or "exception" in root_cause or "code" in root_cause:
        planned_actions = [
            {
                "action": "ROLLBACK_DEPLOY",
                "impact": "high",
                "reasoning": "Rollback the recent deployment which appears to have introduced an application-level bug or crash."
            },
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Attempt container restart to check if it recovers from corrupted application state."
            }
        ]
    elif "traffic" in root_cause or "load" in root_cause or "spike" in root_cause or "request" in root_cause:
        planned_actions = [
            {
                "action": "SCALE_REPLICAS",
                "impact": "medium",
                "reasoning": "Scale up the replicas to handle the elevated request traffic and load."
            },
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operators about the high traffic incident for capacity planning."
            }
        ]
    else:
        # Default safety fallback actions
        planned_actions = [
            {
                "action": "RESTART_CONTAINER",
                "impact": "low",
                "reasoning": "Standard low-risk container restart to clear transient issues."
            },
            {
                "action": "NOTIFY_ONLY",
                "impact": "low",
                "reasoning": "Notify operations for manual investigation as root cause is ambiguous."
            }
        ]

    state["action_plan"] = planned_actions
    
    # Select the first action as the default (safest/highest rank)
    if planned_actions:
        state["selected_action"] = planned_actions[0]["action"]
    else:
        state["selected_action"] = "NOTIFY_ONLY"
        
    return state
