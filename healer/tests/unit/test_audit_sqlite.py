from healer.src.audit import db
from healer.src.audit.logger import (
    get_approval_queue,
    get_audit_logs,
    queue_human_approval,
    write_audit_record,
)
from healer.src.config import settings


def test_sqlite_audit_record_round_trip(monkeypatch, tmp_path, base_state):
    monkeypatch.setattr(settings, "AUDIT_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(tmp_path / "audit.db"))
    db.init_db()

    base_state["policy_gate"] = {"decision": "auto_execute", "checks": {}}
    base_state["execution"] = {
        "status": "success",
        "started_at": "2026-06-23T22:00:01+00:00",
        "completed_at": "2026-06-23T22:00:03+00:00",
        "duration_seconds": 2.0,
        "output": "Container restarted.",
        "alert_resolved": True,
    }

    write_audit_record(base_state)
    logs = get_audit_logs(limit=5)

    assert len(logs) == 1
    assert logs[0]["incident_id"] == "test-id-123"
    assert logs[0]["alert_resolved"] is True
    assert logs[0]["record"]["execution"]["output"] == "Container restarted."


def test_sqlite_approval_queue_round_trip(monkeypatch, tmp_path, base_state):
    monkeypatch.setattr(settings, "AUDIT_BACKEND", "sqlite")
    monkeypatch.setattr(settings, "SQLITE_PATH", str(tmp_path / "approval.db"))
    db.init_db()

    queue_human_approval(base_state)
    queue = get_approval_queue()

    assert len(queue) == 1
    assert queue[0]["incident_id"] == "test-id-123"
    assert queue[0]["action"] == "RESTART_CONTAINER"
