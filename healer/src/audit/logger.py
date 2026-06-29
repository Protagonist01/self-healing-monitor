import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from healer.src.agent.state import HealerState
from healer.src.audit.db import get_db_connection, is_sqlite_backend, sql_placeholders

def parse_isoformat(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(timezone.utc)

def close_cursor(cur):
    try:
        cur.close()
    except Exception:
        pass

def write_audit_record(state: HealerState) -> str:
    """
    Saves the complete HealerState to the PostgreSQL audit_log table.
    """
    conn = get_db_connection()
    record_id = str(uuid.uuid4())
    placeholders = sql_placeholders(11)
    
    alert = state["alert"]
    policy_gate = state.get("policy_gate") or {"decision": "unknown", "checks": {}}
    execution = state.get("execution") or {}
    diagnosis = state.get("diagnosis") or {}
    
    service = alert.get("service") or alert.get("labels", {}).get("service", "unknown")
    alert_name = alert.get("name") or alert.get("labels", {}).get("alertname", "UnknownAlert")
    decision = policy_gate.get("decision", "unknown")
    confidence = diagnosis.get("confidence")
    selected_action = state.get("selected_action")
    alert_resolved = execution.get("alert_resolved", False)
    
    received_at = parse_isoformat(alert.get("received_at")) or datetime.now(timezone.utc)
    completed_at = parse_isoformat(execution.get("completed_at")) or datetime.now(timezone.utc)

    # Format the complete JSON record payload matching ADR-003 schema
    record_payload = {
        "incident_id": state["incident_id"],
        "alert": {
            "name": alert_name,
            "service": service,
            "severity": alert.get("severity", "warning"),
            "labels": alert.get("labels", {}),
            "received_at": alert.get("received_at")
        },
        "context": {
            "metrics_window_minutes": state["context"].get("metrics_window_minutes", 30) if state.get("context") else 30,
            "metrics_summary": state["context"].get("metrics_summary", "") if state.get("context") else "",
            "log_lines_count": state["context"].get("log_lines_count", 0) if state.get("context") else 0,
            "log_summary": state["context"].get("log_summary", "") if state.get("context") else "",
            "recent_deploys": state["context"].get("recent_deploys", []) if state.get("context") else [],
            "runbook_matched": state["context"].get("runbook_matched", "none") if state.get("context") else "none",
            "runbook_excerpt": state["context"].get("runbook_excerpt", "") if state.get("context") else ""
        } if state.get("context") else None,
        "diagnosis": {
            "root_cause": diagnosis.get("root_cause", ""),
            "confidence": confidence,
            "supporting_evidence": diagnosis.get("supporting_evidence", []),
            "llm_model": diagnosis.get("llm_model", ""),
            "llm_tokens_used": diagnosis.get("llm_tokens_used", 0)
        } if diagnosis else None,
        "action_plan": state.get("action_plan", []),
        "selected_action": selected_action,
        "policy_gate": policy_gate,
        "execution": {
            "status": execution.get("status", "skipped"),
            "started_at": execution.get("started_at"),
            "completed_at": execution.get("completed_at"),
            "duration_seconds": execution.get("duration_seconds"),
            "output": execution.get("output", ""),
            "alert_resolved": alert_resolved
        } if execution else None,
        "total_duration_seconds": (completed_at - received_at).total_seconds()
    }

    cur = conn.cursor()
    try:
        cur.execute(f"""
            INSERT INTO audit_log (
                id, incident_id, service, alert_name, decision, confidence, 
                selected_action, alert_resolved, received_at, completed_at, record
            ) VALUES ({placeholders})
        """, (
            record_id,
            state["incident_id"],
            service,
            alert_name,
            decision,
            confidence,
            selected_action,
            int(alert_resolved) if is_sqlite_backend() else alert_resolved,
            received_at.isoformat() if is_sqlite_backend() else received_at,
            completed_at.isoformat() if completed_at and is_sqlite_backend() else completed_at,
            json.dumps(record_payload)
        ))
        conn.commit()
        print(f"Audit log record {record_id} written successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error writing audit log record: {e}")
        raise
    finally:
        close_cursor(cur)
        conn.close()
        
    return record_id

def queue_human_approval(state: HealerState) -> str:
    """
    Inserts a pending action into the human approval queue.
    """
    conn = get_db_connection()
    queue_id = str(uuid.uuid4())
    placeholders = sql_placeholders(10)
    alert = state["alert"]
    service = alert.get("service") or alert.get("labels", {}).get("service", "unknown")
    alert_name = alert.get("name") or alert.get("labels", {}).get("alertname", "UnknownAlert")
    diagnosis = state.get("diagnosis") or {"confidence": 0.0, "root_cause": "Unknown"}
    
    # Selected planned action reasoning
    reasoning = "No action planned."
    for plan in (state.get("action_plan") or []):
        if plan["action"] == state.get("selected_action"):
            reasoning = plan["reasoning"]
            break

    cur = conn.cursor()
    try:
        cur.execute(f"""
            INSERT INTO approval_queue (
                id, incident_id, service, alert_name, action, confidence, reasoning, status, created_at, state_snapshot
            ) VALUES ({placeholders})
        """, (
            queue_id,
            state["incident_id"],
            service,
            alert_name,
            state["selected_action"],
            diagnosis.get("confidence", 0.0),
            reasoning,
            "pending",
            datetime.now(timezone.utc).isoformat() if is_sqlite_backend() else datetime.now(timezone.utc),
            json.dumps(state)
        ))
        conn.commit()
        print(f"Incident {state['incident_id']} placed in approval queue.")
    except Exception as e:
        conn.rollback()
        print(f"Error queueing approval action: {e}")
        raise
    finally:
        close_cursor(cur)
        conn.close()
        
    return queue_id

def get_approval_queue() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    queue_items = []
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, incident_id, service, alert_name, action, confidence, reasoning, status, created_at
            FROM approval_queue
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        for row in rows:
            queue_items.append({
                "id": row[0],
                "incident_id": row[1],
                "service": row[2],
                "alert_name": row[3],
                "action": row[4],
                "confidence": row[5],
                "reasoning": row[6],
                "status": row[7],
                "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else row[8]
            })
    except Exception as e:
        print(f"Error fetching approval queue: {e}")
    finally:
        close_cursor(cur)
        conn.close()
    return queue_items

def get_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    logs = []
    cur = conn.cursor()
    try:
        placeholder = "?" if is_sqlite_backend() else "%s"
        cur.execute(f"""
            SELECT id, incident_id, service, alert_name, decision, confidence, selected_action, alert_resolved, received_at, completed_at, record
            FROM audit_log
            ORDER BY received_at DESC
            LIMIT {placeholder}
        """, (limit,))
        rows = cur.fetchall()
        for row in rows:
            record = row[10]
            if isinstance(record, str):
                record = json.loads(record)

            logs.append({
                "id": row[0],
                "incident_id": row[1],
                "service": row[2],
                "alert_name": row[3],
                "decision": row[4],
                "confidence": row[5],
                "selected_action": row[6],
                "alert_resolved": bool(row[7]),
                "received_at": row[8].isoformat() if hasattr(row[8], "isoformat") else row[8],
                "completed_at": row[9].isoformat() if hasattr(row[9], "isoformat") else row[9],
                "record": record
            })
    except Exception as e:
        print(f"Error fetching audit logs: {e}")
    finally:
        close_cursor(cur)
        conn.close()
    return logs
