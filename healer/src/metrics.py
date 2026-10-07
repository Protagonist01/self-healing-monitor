"""Shared metrics, independent of the API module to avoid circular imports."""

from prometheus_client import Counter

INCIDENT_COUNTER = Counter(
    "incident_intake_total", "Total incidents received", ["alert_name", "service"]
)
RESOLVED_COUNTER = Counter(
    "incident_resolved_total", "Total verified incident repairs", ["service", "action"]
)
QUEUE_COUNTER = Counter(
    "incident_queued_total", "Total incidents queued for human approval", ["service", "reason"]
)
