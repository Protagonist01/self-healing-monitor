import httpx
import os
import json
from typing import Dict, Any, List
from healer.src.config import settings
from healer.src.agent.state import HealerState, GatheredContext
from healer.src.rag.runbook_indexer import indexer
from healer.src.agent.nodes.correlation import get_correlation_context


def get_prometheus_metrics(service: str, alert_name: str) -> Dict[str, Any]:
    """
    Fetch metrics; missing telemetry remains explicitly unavailable.
    """
    url = f"{settings.PROMETHEUS_URL}/api/v1/query"
    # Query: CPU or memory usage of containers for the service
    query = f"container_memory_working_set_bytes{{container={json.dumps(service)}}}"
    if "Cpu" in alert_name or "CPU" in alert_name:
        query = f"container_cpu_usage_seconds_total{{container={json.dumps(service)}}}"
    elif "error" in alert_name.lower():
        query = f'sum(rate(http_requests_total{{status="500",service={json.dumps(service)}}}[1m]))'
    elif "down" in alert_name.lower():
        query = f"up{{job={json.dumps(service)}}}"

    try:
        response = httpx.get(url, params={"query": query}, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                val = data["data"]["result"][0]["value"][1]
                return {
                    "metrics_summary": f"Active metric value: {val}",
                    "metrics_raw": data["data"]["result"],
                }
    except Exception as e:
        print(f"Error querying Prometheus: {e}")

    return {
        "metrics_summary": "Metrics unavailable or empty. Do not infer a cause from missing telemetry.",
        "metrics_raw": [],
    }


def get_loki_logs(service: str) -> Dict[str, Any]:
    """
    Fetch logs; never fabricate evidence when Loki is unavailable.
    """
    url = f"{settings.LOKI_URL}/loki/api/v1/query_range"
    query = f"{{container={json.dumps(service)}}}"
    try:
        response = httpx.get(url, params={"query": query, "limit": 20}, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                logs = []
                for stream in data["data"]["result"]:
                    for val in stream.get("values", []):
                        logs.append(val[1])
                summary = "Recent log lines retrieved; no known error signature matched."
                if any("OOMKilled" in line or "Out of memory" in line for line in logs):
                    summary = "Repeated OOMKilled events detected in container logs."
                elif any("500" in line or "Internal Server Error" in line for line in logs):
                    summary = "High frequency of HTTP 500 errors in service logs."
                return {"log_lines_count": len(logs), "log_summary": summary, "log_raw": logs}
    except Exception as e:
        print(f"Error querying Loki: {e}")

    return {"log_lines_count": 0, "log_summary": "Logs unavailable or empty.", "log_raw": []}


def get_recent_deploys(service: str) -> List[str]:
    """
    No deployment-history source is configured.
    """
    return []


def get_keyword_runbook(alert_name: str, log_summary: str) -> Dict[str, str]:
    """
    Deterministic first pass for obvious demo incidents before semantic search.
    """
    text = f"{alert_name} {log_summary}".lower()
    candidates = [
        (("memory", "oom", "leak"), "high_memory.md"),
        (("500", "error", "exception"), "high_error_rate.md"),
        (("down", "restart", "crash"), "service_restart.md"),
    ]

    for keywords, filename in candidates:
        if any(keyword in text for keyword in keywords):
            filepath = os.path.join(settings.RUNBOOKS_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return {
                        "runbook_matched": filename,
                        "runbook_excerpt": f.read()[:500],
                    }

    return {}


def context_gather_node(state: HealerState) -> HealerState:
    """
    LangGraph node: context_gather.
    Gathers metrics, logs, recent deployments, and retrieves the matching runbook from the index.
    """
    alert = state["alert"]
    service = alert.get("service") or alert["labels"].get("service", "unknown-service")
    alert_name = alert.get("name") or alert["labels"].get("alertname", "UnknownAlert")

    # 1. Fetch metrics
    metrics_data = get_prometheus_metrics(service, alert_name)

    # 2. Fetch logs
    logs_data = get_loki_logs(service)

    # 3. Fetch recent deployments
    deploys = get_recent_deploys(service)

    # 3.5 Multi-service incident correlation
    correlation = get_correlation_context(service, alert_name)

    # 4. Semantic Runbook Retrieval via RAG
    # Construct a search query incorporating alert details and log snippet
    rag_query = f"Alert: {alert_name} on service: {service}. Logs: {logs_data['log_summary']}"

    runbook_matched = "none"
    runbook_excerpt = "No matching runbooks found."

    keyword_match = get_keyword_runbook(alert_name, logs_data["log_summary"])
    if keyword_match:
        runbook_matched = keyword_match["runbook_matched"]
        runbook_excerpt = keyword_match["runbook_excerpt"]
    else:
        try:
            # Pre-index if needed (handles changes automatically)
            indexer.index_runbooks()

            matches = indexer.search(rag_query, limit=1)
            if matches:
                top_match = matches[0]
                runbook_matched = top_match["metadata"]["source"]
                runbook_excerpt = top_match["document"][:500]  # Excerpt
        except Exception as e:
            print(f"Error querying ChromaDB runbooks: {e}")
            runbook_excerpt = f"Failed to retrieve runbook from index: {str(e)}"

    context: GatheredContext = {
        "metrics_window_minutes": 1 if "error" in alert_name.lower() else 0,
        "metrics_summary": metrics_data["metrics_summary"],
        "metrics_raw": metrics_data["metrics_raw"],
        "log_lines_count": logs_data["log_lines_count"],
        "log_summary": logs_data["log_summary"],
        "log_raw": logs_data["log_raw"],
        "recent_deploys": deploys,
        "runbook_matched": runbook_matched,
        "runbook_excerpt": runbook_excerpt,
        "correlation": correlation,
    }

    state["context"] = context
    return state
