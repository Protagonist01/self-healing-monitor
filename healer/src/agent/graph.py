import time
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END

from healer.src.agent.state import HealerState
from healer.src.agent.nodes.context_gather import context_gather_node
from healer.src.agent.nodes.diagnose import diagnose_node
from healer.src.agent.nodes.action_planner import action_planner_node
from healer.src.agent.nodes.policy_gate import policy_gate_node

from healer.src.executor.docker_executor import docker_executor
from healer.src.executor.k8s_executor import k8s_executor
from healer.src.audit.logger import write_audit_record, queue_human_approval

MAX_AUTO_EXECUTION_RETRIES = 1

def executor_node(state: HealerState) -> HealerState:
    """
    LangGraph node: executor.
    Runs the selected remediation action and logs the results.
    """
    alert = state["alert"]
    service = alert.get("service") or alert["labels"].get("service", "unknown-service")
    action = state["selected_action"]
    
    start_time = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    
    output = ""
    status = "skipped"
    
    if action == "RESTART_CONTAINER":
        print(f"Executing RESTART_CONTAINER for service '{service}'...")
        res = docker_executor.restart_container(service)
        status = res["status"]
        output = res["output"]
    elif action == "SCALE_REPLICAS":
        print(f"Executing SCALE_REPLICAS for service '{service}'...")
        # Target scaling to 2 replicas by default
        res = docker_executor.scale_replicas(service, replicas=2)
        status = res["status"]
        output = res["output"]
    elif action == "ROLLBACK_DEPLOY":
        print(f"Executing ROLLBACK_DEPLOY for service '{service}'...")
        # Rollback deploy is high risk, k8s scaffold or docker mock
        res = k8s_executor.restart_deployment(service)
        status = res["status"]
        output = f"Rollback deploy skipped: {res['output']}"
    elif action == "NOTIFY_ONLY":
        print(f"Executing NOTIFY_ONLY. Notifying operators of '{service}' alert...")
        status = "success"
        output = f"Slack/PagerDuty notification sent to channel #alerts for incident."
    else:
        status = "failure"
        output = f"Unknown action: '{action}'."

    completed_at = datetime.now(timezone.utc).isoformat()
    duration = time.time() - start_time
    
    # Check if the alert is resolved. For demo purposes, if execution succeeded, we mark alert_resolved=True.
    alert_resolved = (status == "success")

    state["execution"] = {
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "output": output,
        "alert_resolved": alert_resolved
    }
    
    return state

def prepare_retry_node(state: HealerState) -> HealerState:
    """
    LangGraph node: prepare_retry.
    Records a failed auto-execution and allows one additional executor attempt.
    """
    retry_count = state.get("retry_count", 0) + 1
    state["retry_count"] = retry_count
    state["errors"].append(
        f"Auto-execution attempt {retry_count} failed: {state.get('execution', {}).get('output', 'no output')}"
    )
    return state

def approval_queue_node(state: HealerState) -> HealerState:
    """
    LangGraph node: approval_queue.
    Enqueues the incident in the human approval queue table.
    """
    queue_human_approval(state)
    
    state["execution"] = {
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "duration_seconds": 0.0,
        "output": "Queued for human approval.",
        "alert_resolved": False
    }
    
    return state

def audit_log_node(state: HealerState) -> HealerState:
    """
    LangGraph node: audit_log.
    Writes the final outcome to the audit log database.
    """
    write_audit_record(state)
    return state

def route_after_gate(state: HealerState) -> str:
    """
    Conditional router edge that branches based on the policy gate outcome.
    """
    decision = state["policy_gate"]["decision"]
    if decision in ["auto_execute", "notify_only"]:
        return "executor"
    else:
        return "approval_queue"

def route_after_execution(state: HealerState) -> str:
    """
    Retry a failed auto-execution once, then finalize through the audit log.
    """
    execution = state.get("execution") or {}
    if execution.get("status") == "failure" and state.get("retry_count", 0) < MAX_AUTO_EXECUTION_RETRIES:
        return "prepare_retry"
    return "audit_log"

# Setup the StateGraph
workflow = StateGraph(HealerState)

# Add all nodes
workflow.add_node("context_gather", context_gather_node)
workflow.add_node("diagnose", diagnose_node)
workflow.add_node("action_planner", action_planner_node)
workflow.add_node("policy_gate", policy_gate_node)
workflow.add_node("executor", executor_node)
workflow.add_node("prepare_retry", prepare_retry_node)
workflow.add_node("approval_queue", approval_queue_node)
workflow.add_node("audit_log", audit_log_node)

# Set links/transitions
workflow.set_entry_point("context_gather")
workflow.add_edge("context_gather", "diagnose")
workflow.add_edge("diagnose", "action_planner")
workflow.add_edge("action_planner", "policy_gate")

# Policy Gate routing
workflow.add_conditional_edges(
    "policy_gate",
    route_after_gate,
    {
        "executor": "executor",
        "approval_queue": "approval_queue"
    }
)

# Retry failed auto-execution once before final audit.
workflow.add_conditional_edges(
    "executor",
    route_after_execution,
    {
        "prepare_retry": "prepare_retry",
        "audit_log": "audit_log"
    }
)
workflow.add_edge("prepare_retry", "executor")
workflow.add_edge("approval_queue", "audit_log")
workflow.add_edge("audit_log", END)

# Compile the workflow
healer_app = workflow.compile()
