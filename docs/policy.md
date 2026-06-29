# Policy

The policy gate is the boundary between recommendation and autonomous infrastructure action. It is implemented in `healer/src/agent/nodes/policy_gate.py`.

## Autonomous Execution Requirements

All of these checks must pass before the healer auto-executes an action:

| Check | Default |
| --- | --- |
| Confidence threshold | `confidence >= 0.75` |
| Action allowlist | `RESTART_CONTAINER`, `NOTIFY_ONLY` |
| Impact level | anything marked `high` requires human approval |
| Global override | `REQUIRE_HUMAN_APPROVAL=false` |

`NOTIFY_ONLY` is always allowed because it does not change infrastructure.

## Default Action Risk

| Action | Impact | Default route |
| --- | --- | --- |
| `RESTART_CONTAINER` | low | auto when confidence passes |
| `NOTIFY_ONLY` | low | auto |
| `SCALE_REPLICAS` | medium | human approval unless allowlisted |
| `ROLLBACK_DEPLOY` | high | human approval |

## Tuning

Use `.env` to adjust the gate:

```env
CONFIDENCE_THRESHOLD=0.75
ALLOWED_AUTO_ACTIONS=["RESTART_CONTAINER","NOTIFY_ONLY"]
REQUIRE_HUMAN_APPROVAL=false
```

Set `REQUIRE_HUMAN_APPROVAL=true` for first deployment or demos where you want every action reviewed.

## Audit Requirements

Every incident writes a complete record containing alert metadata, gathered context, diagnosis, action plan, selected action, policy decision, execution result, and total duration. Pending human approvals also store a state snapshot so approved actions can resume from the exact decision point.
