import time
from datetime import datetime, timezone
from langgraph.graph import StateGraph, END

from healer.src.config import settings
from healer.src.agent.state import HealerState
from healer.src.agent.nodes.context_gather import context_gather_node
from healer.src.agent.nodes.diagnose import diagnose_node
from healer.src.agent.nodes.action_planner import action_planner_node
from healer.src.agent.nodes.policy_gate import policy_gate_node
from healer.src.agent.nodes.verify_action import verify_action_node

from healer.src.executor.docker_executor import docker_executor
from healer.src.audit.logger import write_audit_record, queue_human_approval
from healer.src.feedback import record_outcome
from healer.src.metrics import RESOLVED_COUNTER, QUEUE_COUNTER


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
        res = docker_executor.scale_replicas(service, replicas=2)
        status = res["status"]
        output = res["output"]
    elif action == "ROLLBACK_DEPLOY":
        status = "skipped"
        output = "Rollback is unsupported for this Docker deployment. Use your deployment tooling."
    elif action == "NOTIFY_ONLY":
        print(f"Executing NOTIFY_ONLY. Notifying operators of '{service}' alert...")
        output = _send_notification(service, state["incident_id"])
        status = (
            "success"
            if output.startswith("Slack notification sent")
            else "skipped"
            if not settings.SLACK_WEBHOOK_URL
            else "failure"
        )
    else:
        status = "failure"
        output = f"Unknown action: '{action}'."

    completed_at = datetime.now(timezone.utc).isoformat()
    duration = time.time() - start_time

    # Preliminary resolution flag — will be corrected by verify_action_node
    alert_resolved = False

    state["execution"] = {
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "duration_seconds": round(duration, 3),
        "output": output,
        "alert_resolved": alert_resolved,
    }

    return state


def _send_notification(service: str, incident_id: str) -> str:
    """
    Sends a real notification if SLACK_WEBHOOK_URL is configured,
    otherwise reports that no provider is configured.
    """
    if not settings.SLACK_WEBHOOK_URL:
        return f"No notification provider configured. Incident {incident_id} is recorded locally."

    try:
        import httpx

        response = httpx.post(
            settings.SLACK_WEBHOOK_URL,
            json={
                "text": f"Self-Healing Monitor alert: service '{service}' incident {incident_id}. Action: NOTIFY_ONLY.",
            },
            timeout=5.0,
        )
        response.raise_for_status()
        return f"Slack notification sent for incident {incident_id}."
    except Exception as e:
        return f"Failed to send Slack notification: {e}. Incident {incident_id}."


def prepare_retry_node(state: HealerState) -> HealerState:
    """
    LangGraph node: prepare_retry.
    Records a failed auto-execution and allows additional executor attempts.
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
        "alert_resolved": False,
    }

    return state


def audit_log_node(state: HealerState) -> HealerState:
    """
    LangGraph node: audit_log.
    Writes the final outcome to the audit log database and records the
    incident outcome for the feedback loop.
    """
    write_audit_record(state)
    record_outcome(state)
    execution = state.get("execution") or {}
    service = state["alert"]["service"]
    if execution.get("alert_resolved"):
        RESOLVED_COUNTER.labels(service=service, action=state["selected_action"]).inc()
    if execution.get("status") == "pending":
        QUEUE_COUNTER.labels(service=service, reason="human_approval").inc()
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
    Retry a failed auto-execution up to MAX_AUTO_EXECUTION_RETRIES times,
    then route to verification.
    """
    execution = state.get("execution") or {}
    max_retries = settings.MAX_AUTO_EXECUTION_RETRIES
    if execution.get("status") == "failure" and state.get("retry_count", 0) < max_retries:
        return "prepare_retry"
    return "verify_action"


def build_healer_graph():
    # Setup the StateGraph
    workflow = StateGraph(HealerState)

    workflow.add_node("context_gather", context_gather_node)
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("action_planner", action_planner_node)
    workflow.add_node("policy_gate", policy_gate_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("prepare_retry", prepare_retry_node)
    workflow.add_node("verify_action", verify_action_node)
    workflow.add_node("approval_queue", approval_queue_node)
    workflow.add_node("audit_log", audit_log_node)

    workflow.set_entry_point("context_gather")
    workflow.add_edge("context_gather", "diagnose")
    workflow.add_edge("diagnose", "action_planner")
    workflow.add_edge("action_planner", "policy_gate")

    # Policy Gate routing
    workflow.add_conditional_edges(
        "policy_gate",
        route_after_gate,
        {"executor": "executor", "approval_queue": "approval_queue"},
    )

    # Retry failed auto-execution then verify
    workflow.add_conditional_edges(
        "executor",
        route_after_execution,
        {"prepare_retry": "prepare_retry", "verify_action": "verify_action"},
    )
    workflow.add_edge("prepare_retry", "executor")
    workflow.add_edge("verify_action", "audit_log")
    workflow.add_edge("approval_queue", "audit_log")
    workflow.add_edge("audit_log", END)

    return workflow.compile()


healer_app = build_healer_graph()
