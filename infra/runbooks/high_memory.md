# High Memory Usage Runbook

## Symptoms
- Prometheus alert `HighMemoryUsage` firing.
- Container memory usage exceeding 90%.
- Loki logs show repeated `OOMKilled` or `OutOfMemory` errors.

## Root Cause Diagnosis
1. **Memory Leak**: Gradual increase in memory usage over time, often correlating with recent deployments. Look for deployment logs in the last 1 hour.
2. **Traffic Spike**: Temporary surge in memory due to concurrent request spikes. Compare memory usage with request volume metrics.

## Remediation Steps
- **Immediate (Safe)**: Restart the container to flush memory. Use the `RESTART_CONTAINER` action. This resolves the immediate outage.
- **Scaling**: If the memory usage spike is driven by traffic, scale up replicas. Use `SCALE_REPLICAS`.
- **Permanent Fix**: If a code bug or leak was introduced, rollback the recent deploy using `ROLLBACK_DEPLOY`.
