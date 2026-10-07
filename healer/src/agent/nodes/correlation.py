"""
Multi-service incident correlation.

Detects cascading failures by checking for recent incidents on related services
within a configurable time window. When multiple services trigger alerts in a
short period, the correlation metadata is added to the incident state so the
diagnosis node can consider broader context.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from healer.src.config import settings
from healer.src.audit.db import get_db_connection, is_sqlite_backend, return_db_connection


def get_correlation_context(service: str, alert_name: str) -> Dict[str, Any]:
    """
    Queries the audit log for recent incidents on other services within the
    correlation window. Returns a dict with related incidents and a cascading
    flag if multiple services are affected simultaneously.
    """
    window_seconds = getattr(settings, "CORRELATION_WINDOW_SECONDS", 120)
    if window_seconds <= 0:
        return {"related_incidents": [], "is_cascading": False}

    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()

    conn = get_db_connection()
    cur = conn.cursor()
    related = []
    try:
        token = "?" if is_sqlite_backend() else "%s"
        cur.execute(
            f"""
            SELECT incident_id, service, alert_name, decision, selected_action, received_at
            FROM audit_log
            WHERE received_at >= {token}
              AND service != {token}
            ORDER BY received_at DESC
            LIMIT 10
            """,
            (cutoff, service),
        )
        rows = cur.fetchall()
        for row in rows:
            related.append(
                {
                    "incident_id": str(row[0]),
                    "service": row[1],
                    "alert_name": row[2],
                    "decision": row[3],
                    "selected_action": row[4],
                    "received_at": row[5].isoformat()
                    if hasattr(row[5], "isoformat")
                    else str(row[5]),
                }
            )
    except Exception as e:
        print(f"Correlation query error: {e}")
    finally:
        cur.close()
        return_db_connection(conn)

    # Repeated audit rows for one service do not indicate multiple dependencies.
    is_cascading = len({incident["service"] for incident in related}) >= 2

    return {
        "related_incidents": related,
        "is_cascading": is_cascading,
        "correlation_window_seconds": window_seconds,
    }


def format_correlation_for_prompt(correlation: Dict[str, Any]) -> str:
    """
    Formats correlation context into a string suitable for the diagnosis prompt.
    """
    if not correlation or not correlation.get("related_incidents"):
        return ""

    lines = ["Recent incidents on other services (possible cascading failure):"]
    for inc in correlation["related_incidents"]:
        lines.append(
            f"  - {inc['service']}: {inc['alert_name']} ({inc['decision']}, action: {inc['selected_action'] or 'none'})"
        )
    if correlation.get("is_cascading"):
        lines.append("WARNING: Multiple services affected — likely cascading failure.")
    return "\n".join(lines)
