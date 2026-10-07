# Architecture

The project is a local SRE demo stack for receiving Prometheus Alertmanager webhooks, gathering incident context, selecting a low-risk remediation path, and preserving an audit trail.

## Runtime Flow

```mermaid
flowchart TD
  alert["Alertmanager webhook"] --> api["Healer FastAPI API"]
  api --> intake["Durable incident queue"]
  intake --> context["Context gather"]
  context --> diagnose["Diagnosis"]
  diagnose --> planner["Action planner"]
  planner --> gate["Policy gate"]
  gate --> exec["Executor"]
  gate --> queue["Approval queue"]
  exec --> retry["Prepare retry"]
  retry --> exec
  exec --> verify["Verify recovery"]
  verify --> audit["Audit log"]
  queue --> audit
  audit --> dashboard["Dashboard/API views"]
```

## Components

- `healer/src/main.py` exposes webhook, audit, approval, health, and demo endpoints.
- `healer/src/agent/graph.py` defines the LangGraph state machine and one retry for failed auto-execution.
- `healer/src/agent/nodes/` contains context gathering, diagnosis, action planning, and policy gating.
- `healer/src/audit/` writes audit and approval records to PostgreSQL or SQLite.
- `healer/src/rag/runbook_indexer.py` indexes markdown runbooks with ChromaDB. It uses OpenAI embeddings when `OPENAI_API_KEY` is present and local deterministic hash embeddings otherwise.
- `demo_services/` contains intentionally faulty FastAPI services that expose Prometheus metrics.
- `infra/` contains Docker Compose, Prometheus, Alertmanager, Loki, runbooks, and Grafana dashboard configuration.
- `dashboard/` contains the React operator UI.

## Local Demo Modes

The default Docker Compose mode uses PostgreSQL. For a lighter local API-only run, set:

```env
AUDIT_BACKEND=sqlite
ENVIRONMENT=development
SQLITE_PATH=./healer_audit.db
```

Without `OPENROUTER_API_KEY`, diagnosis reports unavailable at zero confidence. Without `OPENAI_API_KEY`, runbook retrieval uses local hash embeddings.

The diagram omits the dashboard's approval POST: it atomically claims the pending
snapshot, calls execution and verification, then writes another audit row. Retries
apply to automatic execution only. Exhausted failures are audited, not re-queued.
Nodes perform side effects; there is no LangGraph checkpointer, per-node timing
instrumentation, or live deployment-history provider. SQL stores incident-level state.

Chroma runs embedded. Server mode is rejected at startup; see the
[dependency security review](dependency-security.md). Recovery requires a healthy
metric and `timestamp(up)` after command completion. The dashboard polls every
eight seconds; `/events/stream` is an optional API endpoint.
