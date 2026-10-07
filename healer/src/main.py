import json
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from prometheus_client import make_asgi_app
from starlette.concurrency import run_in_threadpool

from healer.src.config import settings
from healer.src.auth import verify_api_key
from healer.src.audit.db import init_db, get_db_connection, return_db_connection, close_pg_pool
from healer.src.audit.logger import get_audit_logs, get_approval_queue
from healer.src.agent.graph import executor_node, audit_log_node
from healer.src.agent.nodes.verify_action import verify_action_node
from healer.src.agent.state import HealerState
from healer.src.audit.db import is_sqlite_backend
from healer.src.queue.worker import enqueue_incident, start_worker, stop_worker
from healer.src.security.rate_limit import enforce_rate_limit
from healer.src.metrics import INCIDENT_COUNTER


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_worker()
    try:
        yield
    finally:
        stop_worker()
        close_pg_pool()


app = FastAPI(title="Self-Healing Microservices Monitor Healer API", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-API-Key"],
)

metrics_asgi_app = make_asgi_app()
app.mount("/metrics", metrics_asgi_app)


class AlertPayload(BaseModel):
    receiver: str = "healer"
    status: str = "firing"
    alerts: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)

    @field_validator("alerts")
    @classmethod
    def validate_alert_maps(cls, alerts):
        for alert in alerts:
            for name in ("labels", "annotations"):
                values = alert.get(name, {})
                if not isinstance(values, dict) or any(
                    not isinstance(key, str)
                    or not isinstance(value, str)
                    or len(key) > 256
                    or len(value) > 4096
                    for key, value in values.items()
                ):
                    raise ValueError(f"{name} must contain bounded string keys and values")
        return alerts


class ApprovalRequest(BaseModel):
    incident_id: str
    status: Literal["approved", "rejected"]


class DemoIncidentRequest(BaseModel):
    service: str = Field(
        default="leaky_service",
        min_length=1,
        max_length=128,
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$",
    )
    alert_name: str = Field(default="HighMemoryUsage", min_length=1, max_length=128)
    severity: Literal["info", "warning", "critical"] = "warning"


def is_firing_alert(payload_status: str, alert: Dict[str, Any]) -> bool:
    return alert.get("status", payload_status) == "firing"


def is_duplicate_alert(alert_name: str, service: str) -> bool:
    """
    Checks the audit log for a recent incident with the same alert+service
    within the configured dedup window. Prevents duplicate healing cycles
    when Alertmanager resends the same firing alert.
    """
    if settings.DEDUP_WINDOW_SECONDS <= 0:
        return False

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        placeholder = "?" if is_sqlite_backend() else "%s"
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=settings.DEDUP_WINDOW_SECONDS)
        ).isoformat()
        cur.execute(
            f"""
            SELECT 1 FROM audit_log
            WHERE alert_name = {placeholder}
              AND service = {placeholder}
              AND received_at >= {placeholder}
            LIMIT 1
            """,
            (alert_name, service, cutoff),
        )
        return cur.fetchone() is not None
    except Exception as e:
        print(f"Dedup check error (allowing through): {e}")
        return False
    finally:
        cur.close()
        return_db_connection(conn)


@app.post("/webhook/alert")
def alert_webhook(
    payload: AlertPayload,
    _api_key: str = Security(verify_api_key),
    _rate: None = Security(enforce_rate_limit),
):
    """
    Alertmanager webhook endpoint. Deduplicates, then enqueues incidents
    in the durable work queue for processing by the background worker.
    """
    alerts = [alert for alert in payload.alerts if is_firing_alert(payload.status, alert)]
    if not alerts:
        return {
            "status": "ignored",
            "reason": "No firing alerts found in payload.",
            "incident_ids": [],
        }

    incident_ids = []

    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alert_name = labels.get("alertname", "UnknownAlert")
        service = labels.get("service", "unknown-service")
        severity = labels.get("severity", "warning")

        if is_duplicate_alert(alert_name, service):
            print(f"Duplicate alert suppressed: {alert_name} on {service}")
            continue

        INCIDENT_COUNTER.labels(alert_name=alert_name, service=service).inc()

        incident_id = str(uuid.uuid4())

        initial_state: HealerState = {
            "incident_id": incident_id,
            "alert": {
                "name": alert_name,
                "service": service,
                "severity": severity,
                "labels": labels,
                "annotations": annotations,
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
            "context": None,
            "diagnosis": None,
            "action_plan": None,
            "selected_action": None,
            "policy_gate": None,
            "execution": None,
            "retry_count": 0,
            "errors": [],
        }

        if enqueue_incident(initial_state) is not None:
            incident_ids.append(incident_id)

    return {"status": "accepted", "incident_ids": incident_ids}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "audit_backend": settings.audit_backend_name,
        "rag_embedding": "openai" if settings.OPENAI_API_KEY else "local_hash",
        "auth_enabled": bool(settings.HEALER_API_KEY),
        "demo_enabled": settings.ENABLE_DEMO_ENDPOINT,
    }


@app.get("/events")
def fetch_events(limit: int = Query(25, ge=1, le=100), _api_key: str = Security(verify_api_key)):
    return get_audit_logs(limit)


async def _sse_event_stream(request: Request):
    """Generator that yields SSE events polling for new audit data every 3 seconds."""
    last_ids = None
    while not await request.is_disconnected():
        try:
            logs = await run_in_threadpool(get_audit_logs, limit=5)
            current_ids = tuple(log["id"] for log in logs)
            if current_ids != last_ids:
                import json as _json

                yield f"data: {_json.dumps(logs)}\n\n"
                last_ids = current_ids
        except Exception:
            pass
        await asyncio.sleep(3)


@app.get("/events/stream")
async def events_stream(request: Request, _api_key: str = Security(verify_api_key)):
    """Server-Sent Events stream for real-time audit updates."""
    return StreamingResponse(
        _sse_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/demo/incident")
def trigger_demo_incident(
    req: DemoIncidentRequest,
    _api_key: str = Security(verify_api_key),
    _rate: None = Security(enforce_rate_limit),
):
    """
    Convenience endpoint for local demos without needing Alertmanager to fire first.
    """
    if not settings.ENABLE_DEMO_ENDPOINT:
        raise HTTPException(status_code=404, detail="Demo endpoint disabled.")
    labels = {"alertname": req.alert_name, "service": req.service, "severity": req.severity}
    annotations = {
        "summary": f"Demo {req.alert_name} for {req.service}",
        "description": "Synthetic incident submitted through /demo/incident.",
    }

    INCIDENT_COUNTER.labels(alert_name=req.alert_name, service=req.service).inc()

    incident_id = str(uuid.uuid4())
    initial_state: HealerState = {
        "incident_id": incident_id,
        "alert": {
            "name": req.alert_name,
            "service": req.service,
            "severity": req.severity,
            "labels": labels,
            "annotations": annotations,
            "received_at": datetime.now(timezone.utc).isoformat(),
        },
        "context": None,
        "diagnosis": None,
        "action_plan": None,
        "selected_action": None,
        "policy_gate": None,
        "execution": None,
        "retry_count": 0,
        "errors": [],
    }
    if enqueue_incident(initial_state) is None:
        return {"status": "duplicate", "incident_id": None}

    return {"status": "accepted", "incident_id": incident_id}


@app.get("/audit")
def fetch_audit(limit: int = Query(50, ge=1, le=100), _api_key: str = Security(verify_api_key)):
    return get_audit_logs(limit)


@app.get("/approval/queue")
def fetch_approval_queue(_api_key: str = Security(verify_api_key)):
    return get_approval_queue()


@app.post("/approval/action")
def process_approval(req: ApprovalRequest, _api_key: str = Security(verify_api_key)):
    """
    Approve or reject a pending action in the queue.
    """
    conn = get_db_connection()
    state_snapshot_json = None
    action = None
    service = None

    cur = conn.cursor()
    try:
        placeholder = "?" if is_sqlite_backend() else "%s"
        cur.execute(
            f"""
            UPDATE approval_queue
            SET status = {placeholder}, updated_at = {placeholder}
            WHERE incident_id = {placeholder} AND status = 'pending'
            RETURNING state_snapshot, action, service
        """,
            (req.status, datetime.now(timezone.utc).isoformat(), req.incident_id),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404, detail="Incident not found in approval queue or already processed."
            )

        state_snapshot_json, action, service = row

        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Unable to process approval.") from e
    finally:
        cur.close()
        return_db_connection(conn)

    state: HealerState = (
        json.loads(state_snapshot_json)
        if isinstance(state_snapshot_json, str)
        else state_snapshot_json
    )

    if req.status == "approved":
        print(f"Incident {req.incident_id} APPROVED by human. Executing action: {action}...")

        state["policy_gate"]["approved_by"] = "operator_api_key"
        state = executor_node(state)
        state = verify_action_node(state)
        audit_log_node(state)

        return {"status": "executed", "execution": state["execution"]}

    elif req.status == "rejected":
        print(f"Incident {req.incident_id} REJECTED by human.")

        state["execution"] = {
            "status": "rejected",
            "started_at": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": 0.0,
            "output": "Rejected by operator.",
            "alert_resolved": False,
        }
        audit_log_node(state)
        return {"status": "rejected"}

    else:
        raise HTTPException(
            status_code=400, detail="Invalid status. Must be 'approved' or 'rejected'."
        )
