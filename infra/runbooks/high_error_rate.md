# High Error Rate Runbook

## Symptoms
- Prometheus alert `HighErrorRate` firing.
- HTTP 500 status codes spike in Loki logs.
- Client requests failing with bad response status codes.

## Root Cause Diagnosis
1. **Broken Release**: A code bug introduced in the latest deployment causing uncaught exceptions or database failures.
2. **Dependent Service Down**: Downstream dependencies or database connections timing out.

## Remediation Steps
- **Code Bug**: If it's a broken release, trigger an immediate rollback using `ROLLBACK_DEPLOY`.
- **Transient State**: Try restarting the service container using `RESTART_CONTAINER` in case of connection pools leakage or deadlocks.
- **Notification**: Notify the team immediately if downstream dependencies are down.
