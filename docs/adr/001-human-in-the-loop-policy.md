# ADR-001: Human-in-the-Loop Policy for Autonomous Remediation

## Status
Accepted

## Context
The healer agent can execute actions against live infrastructure. The central design question is: when should it act autonomously, and when should it require human approval?

Two failure modes exist:
1. **Too conservative** — agent routes everything to humans, providing no automation value
2. **Too aggressive** — agent auto-executes high-impact actions based on wrong diagnoses, causing outages worse than the original incident

Both are real risks. The policy must explicitly choose a position on this tradeoff and document it.

## Decision
Implement a **Policy Gate** as an explicit, independently-testable node in the LangGraph state machine. The gate enforces four conditions for autonomous execution, all of which must be satisfied:

**Condition 1 — Confidence threshold:**
The LLM's diagnosis confidence score must be ≥ 0.75. This threshold was chosen based on eval set calibration: at 0.75+, the agent's action accuracy is ~85%; below 0.75 it drops to ~52%.

**Condition 2 — Action allowlist:**
The selected action must be in `config.ALLOWED_AUTO_ACTIONS`. The default allowlist is:
- `RESTART_CONTAINER` (low blast radius, reversible)
- `NOTIFY_ONLY` (no infrastructure change)

Not in the default allowlist (requires human approval):
- `SCALE_REPLICAS` (cost impact, capacity implications)
- `ROLLBACK_DEPLOY` (interrupts in-flight traffic, may lose state)

Operators can extend the allowlist via the `ALLOWED_AUTO_ACTIONS` environment variable as their trust in the system grows.

**Condition 3 — Impact level:**
Any action classified as `impact: high` by the Action Planner always routes to human approval, regardless of confidence or allowlist membership.

**Condition 4 — Override flag:**
Setting `REQUIRE_HUMAN_APPROVAL=true` in the environment disables all autonomous execution system-wide. This is the recommended setting for first deployment.

## Consequences

**Gained:**
- The policy is code, not documentation — it's enforced, tested (40+ unit tests in `test_policy_gate.py`), and audited
- Operators have a clear, tunable lever (the allowlist) to expand autonomy incrementally as trust is established
- The `REQUIRE_HUMAN_APPROVAL` flag provides a hard kill switch without code changes
- Every policy gate decision is logged with the specific condition that triggered routing — the audit log shows not just what happened but why the agent acted or deferred
- The policy is documented in `docs/policy.md` independently of the code — non-engineers can read and understand what the agent is permitted to do

**Trade-offs:**
- The confidence threshold (0.75) is empirical, not theoretically grounded — it should be re-calibrated if the LLM or prompt changes
- The allowlist approach requires operators to actively extend permissions; some teams may find this overly conservative out of the box
- A binary auto-execute vs. queue decision loses nuance — future work could implement "act and notify" as a middle tier

**Alternatives considered:**
- **No gate, full automation** — rejected; unacceptable risk for infrastructure actions
- **No gate, notify only** — provides observability value but no automation value
- **Confidence-only gate** — rejected; confidence calibration alone is insufficient since even a well-calibrated 0.8-confidence rollback can be catastrophic if wrong
- **Risk score composite** — considered but deferred; too complex to reason about and test at this stage
