from typing import Dict, Any
from healer.src.config import settings
from healer.src.agent.state import HealerState, PolicyGateDecision

def policy_gate_node(state: HealerState) -> HealerState:
    """
    LangGraph node: policy_gate.
    Enforces policies to decide if an action can be auto-executed or must go to a human approval queue.
    Checks:
    1. Confidence threshold (confidence >= settings.CONFIDENCE_THRESHOLD)
    2. Action allowlist (action in settings.ALLOWED_AUTO_ACTIONS)
    3. Action impact level (must not be 'high')
    4. Global override flag (settings.REQUIRE_HUMAN_APPROVAL must be False)
    """
    diagnosis = state["diagnosis"]
    selected_action = state["selected_action"]
    action_plan = state["action_plan"] or []

    if not diagnosis or not selected_action:
        # Fallback to human approval or notify only if state is missing
        state["policy_gate"] = {
            "decision": "human_approval",
            "checks": {
                "error": "Missing diagnosis or selected action"
            }
        }
        return state

    confidence = diagnosis["confidence"]
    confidence_threshold = settings.CONFIDENCE_THRESHOLD

    # Find the impact level of the selected action from the action plan
    impact = "low"
    for item in action_plan:
        if item["action"] == selected_action:
            impact = item["impact"]
            break

    # Check 1: Confidence
    confidence_passed = confidence >= confidence_threshold
    
    # Check 2: Action Allowlist
    allowlist_passed = selected_action in settings.allowed_actions_set
    
    # Check 3: Impact level (High impact always requires human approval)
    impact_passed = impact.lower() != "high"
    
    # Check 4: Global override (Require human approval)
    override_passed = not settings.REQUIRE_HUMAN_APPROVAL

    # Overall outcome
    all_checks_passed = (
        confidence_passed and 
        allowlist_passed and 
        impact_passed and 
        override_passed
    )

    decision = "auto_execute" if all_checks_passed else "human_approval"
    
    # If the action itself is just NOTIFY_ONLY, we don't need human approval to send a notification
    if selected_action == "NOTIFY_ONLY":
        decision = "notify_only"

    state["policy_gate"] = {
        "decision": decision,
        "checks": {
            "confidence_threshold": {
                "passed": confidence_passed,
                "value": confidence,
                "threshold": confidence_threshold
            },
            "allowlist": {
                "passed": allowlist_passed,
                "action": selected_action,
                "allowed": list(settings.allowed_actions_set)
            },
            "impact_level": {
                "passed": impact_passed,
                "level": impact
            },
            "override_flag": {
                "passed": override_passed,
                "require_human": settings.REQUIRE_HUMAN_APPROVAL
            }
        }
    }

    return state
