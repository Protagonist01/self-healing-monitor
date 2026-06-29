from unittest.mock import patch
from healer.src.config import settings
from healer.src.agent.nodes.policy_gate import policy_gate_node

def test_policy_gate_auto_execute(base_state):
    """
    Confidence is 0.85 (>= 0.75), action RESTART_CONTAINER is allowed (low impact), override is False.
    Outcome: auto_execute
    """
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", False):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "auto_execute"
        assert state["policy_gate"]["checks"]["confidence_threshold"]["passed"] is True
        assert state["policy_gate"]["checks"]["allowlist"]["passed"] is True
        assert state["policy_gate"]["checks"]["impact_level"]["passed"] is True
        assert state["policy_gate"]["checks"]["override_flag"]["passed"] is True

def test_policy_gate_low_confidence(base_state):
    """
    Confidence is 0.65 (< 0.75).
    Outcome: human_approval
    """
    base_state["diagnosis"]["confidence"] = 0.65
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", False):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "human_approval"
        assert state["policy_gate"]["checks"]["confidence_threshold"]["passed"] is False

def test_policy_gate_not_in_allowlist(base_state):
    """
    Action SCALE_REPLICAS is selected but not in allowlist.
    Outcome: human_approval
    """
    base_state["selected_action"] = "SCALE_REPLICAS"
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", False):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "human_approval"
        assert state["policy_gate"]["checks"]["allowlist"]["passed"] is False

def test_policy_gate_high_impact(base_state):
    """
    Action ROLLBACK_DEPLOY has high impact.
    Outcome: human_approval
    """
    base_state["selected_action"] = "ROLLBACK_DEPLOY"
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER", "ROLLBACK_DEPLOY"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", False):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "human_approval"
        assert state["policy_gate"]["checks"]["impact_level"]["passed"] is False

def test_policy_gate_global_override(base_state):
    """
    REQUIRE_HUMAN_APPROVAL is set to True.
    Outcome: human_approval
    """
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", True):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "human_approval"
        assert state["policy_gate"]["checks"]["override_flag"]["passed"] is False

def test_policy_gate_notify_only(base_state):
    """
    Action is NOTIFY_ONLY.
    Outcome: notify_only (even if other gates would require approval, notify_only bypasses queue)
    """
    base_state["selected_action"] = "NOTIFY_ONLY"
    base_state["action_plan"].append({"action": "NOTIFY_ONLY", "impact": "low", "reasoning": "notify only"})
    with patch.object(settings, "CONFIDENCE_THRESHOLD", 0.75), \
         patch.object(settings, "ALLOWED_AUTO_ACTIONS", ["RESTART_CONTAINER"]), \
         patch.object(settings, "REQUIRE_HUMAN_APPROVAL", False):
        
        state = policy_gate_node(base_state)
        assert state["policy_gate"]["decision"] == "notify_only"
