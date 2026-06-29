# ADR-002: Model the Healing Pipeline as a LangGraph State Machine

## Status
Accepted

## Context
The healing pipeline has multiple sequential steps with conditional branching:
- Context gathering can partially fail (Loki down, Prometheus timeout) and the pipeline should continue with degraded context rather than abort
- After diagnosis, the pipeline branches based on confidence and action type
- Failed auto-executions should retry once before routing to human approval
- Every state transition must be logged for the audit trail

This could be implemented as a plain imperative Python function. The question was whether the added structure of a graph-based framework justifies the dependency.

## Decision
Use **LangGraph** to model the pipeline as an explicit directed graph with typed state, named nodes, and conditional edges.

The graph structure:

```
START
  │
  ▼
context_gather ──(partial failure ok)──▶ diagnose
                                              │
                                    ┌─────────┴──────────┐
                                    ▼                    ▼
                              (confidence            (confidence
                               ≥ threshold)           < threshold)
                                    │                    │
                                    ▼                    ▼
                            action_planner         policy_gate
                                    │               (→ queue)
                                    ▼
                              policy_gate
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
                      executor            approval_queue
                          │
                   ┌──────┴──────┐
                   ▼             ▼
               (success)     (failure)
                   │             │
                   ▼             ▼
              audit_log    retry → audit_log
```

## Consequences

**Gained:**
- Each node is a pure function `(state: HealerState) -> HealerState` — independently unit-testable without running the full pipeline
- Conditional edges make branching logic explicit and auditable — a reviewer reading `graph.py` understands the full flow without reading every node's implementation
- LangGraph's built-in state checkpointing means the full pipeline state at every node is available for debugging failed incidents
- Node-level timing is automatically available as a Prometheus metric via a thin wrapper — no manual instrumentation needed
- Partial failure handling in `context_gather` is a conditional edge, not a try/except buried inside a function — the degraded-context path is visible in the graph

**Trade-offs:**
- Adds `langgraph` dependency for what is ultimately a ~6-node pipeline
- Contributors unfamiliar with LangGraph need to understand graph concepts before contributing new nodes
- LangGraph's state serialization adds ~5ms overhead per node transition — negligible for an 8s pipeline but worth noting

**Mitigation:**
`docs/architecture.md` includes the graph diagram above with a plain-English description of each node. New nodes can be contributed by following the pattern in any existing node file — the interface is just a typed function signature.
