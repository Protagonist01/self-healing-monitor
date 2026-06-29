# Service Restart Runbook

## Symptoms
- Alert `ServiceDown` firing.
- Service container has stopped or is unhealthy.
- Connection timeouts to the service port.

## Root Cause Diagnosis
1. **Host Crash**: Physical host or node failure.
2. **Process Panic**: Application code panicked and exited, or docker daemon restarted.

## Remediation Steps
- **Immediate Action**: Restart the service container using `RESTART_CONTAINER`.
- **Scaling**: If the container crashed due to overload, scale up using `SCALE_REPLICAS`.
- **Escalation**: If restart fails repeatedly, notify operators.
