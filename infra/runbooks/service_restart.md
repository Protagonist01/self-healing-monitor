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
- **Scaling**: Review capacity and use operator deployment tooling. `SCALE_REPLICAS`
  is unsupported in this Docker workflow.
- **Escalation**: If restart fails repeatedly, notify operators.
