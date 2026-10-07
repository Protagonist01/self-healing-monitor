import time
import math
import json
from datetime import datetime, timezone
from typing import Dict, Any
import httpx

from healer.src.config import settings
from healer.src.agent.state import HealerState, VerificationData


def _query_prometheus(service: str, alert_name: str) -> Dict[str, Any]:
    """
    Queries Prometheus for the current metric value that triggered the alert.
    Returns the raw result or an empty dict on failure.
    """
    url = f"{settings.PROMETHEUS_URL}/api/v1/query"

    if "Memory" in alert_name or "memory" in alert_name.lower():
        query = f"container_memory_working_set_bytes{{container={json.dumps(service)}}}"
    elif "Cpu" in alert_name or "CPU" in alert_name:
        query = f"container_cpu_usage_seconds_total{{container={json.dumps(service)}}}"
    elif "Error" in alert_name or "error" in alert_name.lower():
        query = f'sum(rate(http_requests_total{{status="500",service={json.dumps(service)}}}[1m]))'
    else:
        query = f"up{{job={json.dumps(service)}}}"

    try:
        response = httpx.get(url, params={"query": query}, timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return data.get("data", {}).get("result", [])
    except Exception as e:
        print(f"Verification: Error querying Prometheus: {e}")

    return []


def _has_fresh_scrape(service: str, completed_at: str) -> bool:
    """Require a successful scrape taken after the command completed.

    Instant-vector result timestamps are query times, not scrape times. Use
    timestamp(up) to avoid accepting cached pre-restart samples as recovery.
    """
    try:
        completed = datetime.fromisoformat(completed_at).timestamp()
        selector = f"up{{job={json.dumps(service)}}}"
        query = f"({selector} == 1) and (timestamp({selector}) > {completed})"
        response = httpx.get(
            f"{settings.PROMETHEUS_URL}/api/v1/query",
            params={"query": query},
            timeout=3.0,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("data", {}).get("result", [])
        return payload.get("status") == "success" and bool(results)
    except (TypeError, ValueError, AttributeError, httpx.HTTPError):
        return False


def _is_alert_still_firing(service: str, alert_name: str, metrics_result: Any) -> bool:
    """
    Heuristic check based on the alert type and current metric values.
    """
    if not metrics_result:
        return True  # Can't verify — assume still firing to be safe

    try:
        value = float(metrics_result[0]["value"][1])
        if not math.isfinite(value):
            return True
        if "Memory" in alert_name or "memory" in alert_name.lower():
            val = float(metrics_result[0]["value"][1])
            return val > 60_000_000  # same threshold as alert_rules.yml
        elif "Error" in alert_name or "error" in alert_name.lower():
            val = float(metrics_result[0]["value"][1])
            return val > 0.1
        elif "ServiceDown" in alert_name or "down" in alert_name.lower():
            val = float(metrics_result[0]["value"][1])
            return val == 0
    except (IndexError, KeyError, ValueError, TypeError):
        pass

    return True  # Can't determine — assume still firing


def verify_action_node(state: HealerState) -> HealerState:
    """
    LangGraph node: verify_action.
    After execution, queries Prometheus to determine whether the alert
    condition has actually been resolved, rather than assuming that a
    successful command means the service recovered.
    """
    execution = state.get("execution") or {}
    alert = state.get("alert") or {}
    service = alert.get("service") or alert.get("labels", {}).get("service", "unknown-service")
    alert_name = alert.get("name") or alert.get("labels", {}).get("alertname", "UnknownAlert")

    # Only verify when an action was actually executed (not for pending/rejected)
    if execution.get("status") not in ("success", "failure"):
        return state

    if state.get("selected_action") == "NOTIFY_ONLY":
        execution["alert_resolved"] = False
        return state

    # Wait briefly for metrics to settle after the action
    if settings.VERIFY_DELAY_SECONDS > 0:
        time.sleep(settings.VERIFY_DELAY_SECONDS)

    metrics_result = _query_prometheus(service, alert_name)
    still_firing = _is_alert_still_firing(service, alert_name, metrics_result)

    fresh_scrape = not still_firing and _has_fresh_scrape(service, execution.get("completed_at"))
    verified = not still_firing and fresh_scrape
    metrics_summary = "No metrics returned from Prometheus"
    if metrics_result:
        try:
            metrics_summary = f"Current value: {metrics_result[0]['value'][1]}"
        except (IndexError, KeyError):
            metrics_summary = "Metrics returned but could not parse"
    if not fresh_scrape:
        metrics_summary += "; no successful scrape after action completion"

    verification: VerificationData = {
        "verified": verified,
        "alert_still_firing": still_firing,
        "metrics_after_action": metrics_summary,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "method": "prometheus_query",
    }

    state["verification"] = verification

    # Correct the alert_resolved flag based on actual verification
    if execution.get("status") == "success" and not verified:
        execution["alert_resolved"] = False
        execution["output"] += (
            " | Verification: recovery unverified (alert firing or fresh telemetry unavailable)."
        )
        state["errors"].append(
            f"Post-action verification failed: alert '{alert_name}' on '{service}' firing or fresh telemetry unavailable."
        )
    elif execution.get("status") == "success" and verified:
        execution["alert_resolved"] = True
        execution["output"] += " | Verification: alert resolved."

    state["execution"] = execution

    return state
