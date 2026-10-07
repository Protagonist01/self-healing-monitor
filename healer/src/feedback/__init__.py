import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from healer.src.audit.db import get_db_connection, is_sqlite_backend, return_db_connection
from healer.src.agent.state import HealerState


def record_outcome(state: HealerState):
    """
    Records the outcome of an incident (action taken, whether it resolved the
    alert, verification status) into the incident_outcomes table.
    This feeds the feedback loop so future diagnoses can reference past outcomes.
    """
    execution = state.get("execution") or {}
    verification = state.get("verification") or {}
    diagnosis = state.get("diagnosis") or {}

    action_taken = state.get("selected_action", "unknown")
    alert_resolved = execution.get("alert_resolved", False)
    verified = verification.get("verified", False)
    root_cause = diagnosis.get("root_cause", "")

    feedback_label = "resolved" if alert_resolved and verified else "unresolved"

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        outcome_id = str(uuid.uuid4())
        placeholders_count = 8
        token = "?" if is_sqlite_backend() else "%s"
        placeholders = ", ".join([token] * placeholders_count)
        cur.execute(
            f"""
            INSERT INTO incident_outcomes (
                id, incident_id, action_taken, alert_resolved, verified,
                root_cause, feedback_label, created_at
            ) VALUES ({placeholders})
            """,
            (
                outcome_id,
                state["incident_id"],
                action_taken,
                int(alert_resolved) if is_sqlite_backend() else alert_resolved,
                int(verified) if is_sqlite_backend() else verified,
                root_cause,
                feedback_label,
                datetime.now(timezone.utc).isoformat()
                if is_sqlite_backend()
                else datetime.now(timezone.utc),
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error recording outcome: {e}")
    finally:
        cur.close()
        return_db_connection(conn)


def get_similar_outcomes(root_cause: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves past incident outcomes with similar root causes to use as
    few-shot examples in the diagnosis prompt.
    Returns a list of dicts with action_taken, alert_resolved, root_cause, feedback_label.
    """
    if not root_cause:
        return []

    conn = get_db_connection()
    cur = conn.cursor()
    results = []
    try:
        token = "?" if is_sqlite_backend() else "%s"
        cur.execute(
            f"""
            SELECT action_taken, alert_resolved, verified, root_cause, feedback_label
            FROM incident_outcomes
            WHERE root_cause LIKE {token}
            ORDER BY created_at DESC
            LIMIT {token}
            """,
            (f"%{root_cause[:100]}%", limit),
        )
        rows = cur.fetchall()
        for row in rows:
            results.append(
                {
                    "action_taken": row[0],
                    "alert_resolved": bool(row[1]),
                    "verified": bool(row[2]),
                    "root_cause": row[3],
                    "feedback_label": row[4],
                }
            )
    except Exception as e:
        print(f"Error fetching similar outcomes: {e}")
    finally:
        cur.close()
        return_db_connection(conn)
    return results


def format_feedback_for_prompt(outcomes: List[Dict[str, Any]]) -> str:
    """
    Formats past outcomes into a string suitable for inclusion in the diagnosis prompt.
    """
    if not outcomes:
        return ""

    lines = ["Past similar incidents and their outcomes:"]
    for o in outcomes:
        status = "resolved" if o["alert_resolved"] and o.get("verified") else "unresolved"
        lines.append(
            f'  - Root cause: "{o["root_cause"]}" | Action: {o["action_taken"]} | Outcome: {status}'
        )
    return "\n".join(lines)
