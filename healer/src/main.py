import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import make_asgi_app, Counter

from healer.src.config import settings
from healer.src.audit.db import init_db, get_db_connection
from healer.src.audit.logger import get_audit_logs, get_approval_queue, write_audit_record
from healer.src.agent.graph import healer_app, executor_node, audit_log_node
from healer.src.agent.state import HealerState
from healer.src.audit.db import is_sqlite_backend

# Initialize FastAPI app
app = FastAPI(title="Self-Healing Microservices Monitor Healer API")

# Add CORS middleware to allow connection from React dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus metrics endpoint
metrics_asgi_app = make_asgi_app()
app.mount("/metrics", metrics_asgi_app)

# Prometheus metrics
INCIDENT_COUNTER = Counter("incident_intake_total", "Total incidents received", ["alert_name", "service"])
RESOLVED_COUNTER = Counter("incident_resolved_total", "Total incidents resolved", ["service", "action"])
QUEUE_COUNTER = Counter("incident_queued_total", "Total incidents queued for human approval", ["service", "reason"])

@app.on_event("startup")
def startup_event():
    # Initialize DB schema
    init_db()

class AlertPayload(BaseModel):
    # Alertmanager webhook payload structure
    receiver: str = "healer"
    status: str = "firing"
    alerts: List[Dict[str, Any]] = []

class ApprovalRequest(BaseModel):
    incident_id: str
    status: str  # approved | rejected

class DemoIncidentRequest(BaseModel):
    service: str = "leaky_service"
    alert_name: str = "HighMemoryUsage"
    severity: str = "warning"

def is_firing_alert(payload_status: str, alert: Dict[str, Any]) -> bool:
    return alert.get("status", payload_status) == "firing"

def run_healer_pipeline(state: HealerState):
    """
    Executes the LangGraph pipeline asynchronously in a background task.
    """
    try:
        print(f"Starting healing pipeline for incident: {state['incident_id']}...")
        healer_app.invoke(state)
        print(f"Finished healing pipeline for incident: {state['incident_id']}.")
    except Exception as e:
        print(f"Error executing healer pipeline for incident {state['incident_id']}: {e}")

@app.post("/webhook/alert")
def alert_webhook(payload: AlertPayload, background_tasks: BackgroundTasks):
    """
    Alertmanager Webhook endpoint. Extracts alerts, builds initial HealerState,
    and launches the LangGraph workflow in the background.
    """
    alerts = [alert for alert in payload.alerts if is_firing_alert(payload.status, alert)]
    if not alerts:
        return {"status": "ignored", "reason": "No firing alerts found in payload.", "incident_ids": []}

    incident_ids = []
    
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alert_name = labels.get("alertname", "UnknownAlert")
        service = labels.get("service", "unknown-service")
        severity = labels.get("severity", "warning")
        
        INCIDENT_COUNTER.labels(alert_name=alert_name, service=service).inc()

        incident_id = str(uuid.uuid4())
        incident_ids.append(incident_id)

        # Build initial HealerState
        initial_state: HealerState = {
            "incident_id": incident_id,
            "alert": {
                "name": alert_name,
                "service": service,
                "severity": severity,
                "labels": labels,
                "annotations": annotations,
                "received_at": datetime.now(timezone.utc).isoformat()
            },
            "context": None,
            "diagnosis": None,
            "action_plan": None,
            "selected_action": None,
            "policy_gate": None,
            "execution": None,
            "retry_count": 0,
            "errors": []
        }

        # Run pipeline in background
        background_tasks.add_task(run_healer_pipeline, initial_state)

    return {"status": "accepted", "incident_ids": incident_ids}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "audit_backend": settings.audit_backend_name,
        "rag_embedding": "openai" if settings.OPENAI_API_KEY else "local_hash"
    }

@app.get("/events")
def fetch_events(limit: int = Query(25, ge=1, le=100)):
    """
    Dashboard-friendly event feed derived from recent audit records.
    """
    return get_audit_logs(limit)

@app.post("/demo/incident")
def trigger_demo_incident(req: DemoIncidentRequest, background_tasks: BackgroundTasks):
    """
    Convenience endpoint for local demos without needing Alertmanager to fire first.
    """
    payload = AlertPayload(
        alerts=[
            {
                "labels": {
                    "alertname": req.alert_name,
                    "service": req.service,
                    "severity": req.severity
                },
                "annotations": {
                    "summary": f"Demo {req.alert_name} for {req.service}",
                    "description": "Synthetic incident submitted through /demo/incident."
                }
            }
        ]
    )
    return alert_webhook(payload, background_tasks)

@app.get("/audit")
def fetch_audit(limit: int = Query(50, ge=1, le=100)):
    """
    Get recent audit logs.
    """
    return get_audit_logs(limit)

@app.get("/approval/queue")
def fetch_approval_queue():
    """
    Get items currently pending in the human approval queue.
    """
    return get_approval_queue()

@app.post("/approval/action")
def process_approval(req: ApprovalRequest):
    """
    Approve or reject a pending action in the queue.
    """
    conn = get_db_connection()
    state_snapshot_json = None
    action = None
    service = None

    try:
        with conn.cursor() as cur:
            # Check if pending entry exists
            placeholder = "?" if is_sqlite_backend() else "%s"
            cur.execute(f"""
                SELECT state_snapshot, action, service
                FROM approval_queue
                WHERE incident_id = {placeholder} AND status = 'pending'
            """, (req.incident_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Incident not found in approval queue or already processed.")
            
            state_snapshot_json, action, service = row
            
            # Update status in the queue
            cur.execute(f"""
                UPDATE approval_queue
                SET status = {placeholder}, updated_at = {placeholder}
                WHERE incident_id = {placeholder}
            """, (
                req.status,
                datetime.now(timezone.utc).isoformat() if is_sqlite_backend() else datetime.now(timezone.utc),
                req.incident_id
            ))
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

    # Reconstruct state from snapshot
    state: HealerState = json.loads(state_snapshot_json) if isinstance(state_snapshot_json, str) else state_snapshot_json

    if req.status == "approved":
        print(f"Incident {req.incident_id} APPROVED by human. Executing action: {action}...")
        
        # Override policy decision to auto_execute since human approved it
        state["policy_gate"]["decision"] = "auto_execute"
        
        # Run execution
        state = executor_node(state)
        
        # Update/Write completed audit log record
        audit_log_node(state)
        
        RESOLVED_COUNTER.labels(service=service, action=action).inc()
        return {"status": "executed", "execution": state["execution"]}
        
    elif req.status == "rejected":
        print(f"Incident {req.incident_id} REJECTED by human.")
        
        # Mark as rejected
        state["execution"] = {
            "status": "rejected",
            "started_at": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 0.0,
            "output": "Rejected by operator.",
            "alert_resolved": False
        }
        
        # Update/Write completed audit log record
        audit_log_node(state)
        return {"status": "rejected"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'approved' or 'rejected'.")
