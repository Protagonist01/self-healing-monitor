# Policy

The policy gate is the boundary between recommendation and autonomous infrastructure action. It is implemented in `healer/src/agent/nodes/policy_gate.py`.

## Autonomous Execution Requirements

All of these checks must pass before the healer auto-executes an action:

| Check | Default |
| --- | --- |
| Confidence threshold | `confidence >= 0.75` |
| Action allowlist | `RESTART_CONTAINER`, `NOTIFY_ONLY` |
| Impact level | only explicit `low` impact can auto-execute |
| Global override | `REQUIRE_HUMAN_APPROVAL=true` (operator approval required) |

`NOTIFY_ONLY` is always allowed because it does not change infrastructure.

## Default Action Risk

| Action | Impact | Default route |
| --- | --- | --- |
| `RESTART_CONTAINER` | low | human approval by default |
| `NOTIFY_ONLY` | low | auto |
| `SCALE_REPLICAS` | medium | human approval; unsupported on Docker |
| `ROLLBACK_DEPLOY` | high | human approval |

## Tuning

Use `.env` to adjust the gate:

```env
CONFIDENCE_THRESHOLD=0.75
ALLOWED_AUTO_ACTIONS=["RESTART_CONTAINER","NOTIFY_ONLY"]
REQUIRE_HUMAN_APPROVAL=false
```

Human approval is enabled by default. The example above explicitly enables autonomous repairs. Notification-only actions bypass approval because they cannot modify infrastructure. Docker scaling and rollback remain unsupported even after approval.

## Audit Requirements

Every incident writes a complete record containing alert metadata, gathered context, diagnosis, action plan, selected action, policy decision, execution result, and total duration. Pending human approvals also store a state snapshot so approved actions can resume from the exact decision point.
