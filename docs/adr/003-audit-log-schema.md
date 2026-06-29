# ADR-003: Audit Log Schema and Storage

## Status
Accepted

## Context
Every decision the healer makes — diagnosis, planned action, policy gate outcome, execution result — must be recorded with enough fidelity to:
1. Answer "why did the agent do that?" after the fact
2. Provide training data for future eval set construction
3. Support compliance and incident post-mortems
4. Enable confidence calibration analysis over time

The design questions were: what to store, how to structure it, and where to persist it.

## Decision

### Schema
Each audit record is a single JSON document with this structure:

```json
{
  "incident_id": "uuid",
  "alert": {
    "name": "HighMemoryUsage",
    "service": "payment-service",
    "severity": "warning",
    "labels": {},
    "received_at": "ISO8601"
  },
  "context": {
    "metrics_window_minutes": 30,
    "metrics_summary": "memory_usage peaked at 94% at 14:32:01",
    "log_lines_count": 147,
    "log_summary": "repeated OOMKilled events in last 10 minutes",
    "recent_deploys": ["v2.4.1 deployed 47 minutes ago"],
    "runbook_matched": "high_memory.md",
    "runbook_excerpt": "first 200 chars of matched runbook section"
  },
  "diagnosis": {
    "root_cause": "Memory leak in request handler introduced in v2.4.1",
    "confidence": 0.82,
    "supporting_evidence": ["94% memory at spike", "OOMKilled in logs", "deploy 47min ago"],
    "llm_model": "claude-3-5-sonnet",
    "llm_tokens_used": 1842
  },
  "action_plan": [
    {"action": "RESTART_CONTAINER", "impact": "low", "reasoning": "..."},
    {"action": "ROLLBACK_DEPLOY", "impact": "high", "reasoning": "..."}
  ],
  "selected_action": "RESTART_CONTAINER",
  "policy_gate": {
    "decision": "auto_execute",
    "checks": {
      "confidence_threshold": {"passed": true, "value": 0.82, "threshold": 0.75},
      "allowlist": {"passed": true, "action": "RESTART_CONTAINER"},
      "impact_level": {"passed": true, "level": "low"},
      "override_flag": {"passed": true, "require_human": false}
    }
  },
  "execution": {
    "status": "success",
    "started_at": "ISO8601",
    "completed_at": "ISO8601",
    "duration_seconds": 3.2,
    "output": "Container payment-service restarted successfully",
    "alert_resolved": true,
    "resolution_confirmed_at": "ISO8601"
  },
  "total_duration_seconds": 9.7
}
```

### Storage
Audit records are written to **PostgreSQL** using a single `audit_log` table with a `JSONB` column for the full record plus indexed scalar columns for common query patterns:

```sql
CREATE TABLE audit_log (
  id              UUID PRIMARY KEY,
  incident_id     UUID NOT NULL,
  service         TEXT NOT NULL,
  alert_name      TEXT NOT NULL,
  decision        TEXT NOT NULL,  -- auto_execute | human_approval | notify_only
  confidence      FLOAT,
  selected_action TEXT,
  alert_resolved  BOOLEAN,
  received_at     TIMESTAMPTZ NOT NULL,
  completed_at    TIMESTAMPTZ,
  record          JSONB NOT NULL
);

CREATE INDEX idx_audit_service ON audit_log(service);
CREATE INDEX idx_audit_received ON audit_log(received_at DESC);
CREATE INDEX idx_audit_decision ON audit_log(decision);
```

The `record` JSONB column stores the full document. Scalar columns are duplicated for query performance without schema migration every time the JSONB structure evolves.

## Consequences

**Why PostgreSQL over a log file or time-series DB:**
- Audit records must be queryable by service, time range, decision type, and outcome — SQL is the right tool
- JSONB allows schema evolution (new fields added to the record without migrations) while indexed scalars keep common queries fast
- PostgreSQL's ACID guarantees mean a failed write is surfaced as an error, not silently dropped — audit log integrity is critical
- Already in the stack for other state; no additional operational dependency

**Why store the full LLM reasoning, not just the action:**
The value of the audit log is answering "why" — not just "what". Storing the full context, diagnosis text, confidence score, and policy gate check breakdown means post-mortems have the complete picture. The storage cost (a few KB per incident) is negligible.

**Trade-offs:**
- JSONB schema evolution is permissive — a bug could write malformed records that are hard to query. Mitigated by a Pydantic `AuditRecord` model that validates every record before write
- Duplicate scalar columns and JSONB creates a consistency risk if the write code diverges. Mitigated by a single `audit_logger.py` function as the only write path — never write directly to the table elsewhere
- PostgreSQL adds an operational dependency. For simpler deployments, the `AUDIT_BACKEND=sqlite` env var switches to a local SQLite file — documented in `docs/setup.md`
