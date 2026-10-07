# High Memory Usage Runbook

## Symptoms
- Prometheus alert `HighMemoryUsage` firing.
- The supplied demo alert uses allocated blocks above 60,000,000 bytes. Real
  services require a working-set metric and their own tested thresholds.
- Loki logs show repeated `OOMKilled` or `OutOfMemory` errors.

## Root Cause Diagnosis
1. **Memory Leak**: Gradual increase in memory usage over time, often correlating with recent deployments. Look for deployment logs in the last 1 hour.
2. **Traffic Spike**: Temporary surge in memory due to concurrent request spikes. Compare memory usage with request volume metrics.

## Remediation Steps
- **Temporary relief**: An approved `RESTART_CONTAINER` clears the demo's allocated
  memory. Check fresh telemetry afterwards; a restart may interrupt requests or lose
  in-memory state and does not fix the underlying leak.
- **Scaling**: For real traffic pressure, use operator deployment tooling after review.
  `SCALE_REPLICAS` is unsupported in this Docker workflow.
- **Permanent fix**: Investigate and repair the code. A justified rollback requires
  operator tooling; `ROLLBACK_DEPLOY` is unsupported in this Docker workflow.
