# High Error Rate Runbook

## Symptoms
- Prometheus alert `HighErrorRate` firing.
- HTTP 500 status codes spike in Loki logs.
- Client requests failing with bad response status codes.

## Root Cause Diagnosis
1. **Broken Release**: A code bug introduced in the latest deployment causing uncaught exceptions or database failures.
2. **Dependent Service Down**: Downstream dependencies or database connections timing out.

## Remediation Steps
- **Code Bug**: Review evidence and use operator tooling for a justified rollback.
  `ROLLBACK_DEPLOY` is unsupported in this Docker workflow.
- **Transient State**: Try restarting the service container using `RESTART_CONTAINER` in case of connection pools leakage or deadlocks.
- **Notification**: Notify the team immediately if downstream dependencies are down.
