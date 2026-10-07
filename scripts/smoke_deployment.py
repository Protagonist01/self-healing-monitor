"""Check the local Compose stack; optionally exercise a disposable-container restart."""

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def local_url(name, default):
    return f"http://127.0.0.1:{os.environ.get(name, default)}"


def request(url, headers=None, payload=None, expected=200):
    body = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urlopen(req, timeout=90) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    if status != expected:
        raise RuntimeError(f"{url}: expected HTTP {expected}, received {status}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode()


def await_condition(check, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(2)
    raise RuntimeError("Timed out waiting for the stack condition")


def started_at():
    return subprocess.check_output(
        ["docker", "inspect", "--format", "{{.State.StartedAt}}", "leaky_service"],
        text=True,
    ).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exercise-restart",
        action="store_true",
        help="Allocate memory and approve one real restart of leaky_service",
    )
    args = parser.parse_args()
    key = (ROOT / ".secrets/healer_api_key").read_text().strip()
    headers = {"X-API-Key": key}
    api = local_url("HEALER_PORT", 8000)
    request(api + "/health")
    request(api + "/audit", expected=401)
    request(api + "/audit", headers)
    request(api + "/audit", {"Authorization": "Bearer " + key})
    request(api + "/demo/incident", headers, {}, expected=404)
    assert "root" in request(local_url("DASHBOARD_PORT", 3000))
    request(local_url("ALERTMANAGER_PORT", 9093) + "/api/v2/status")
    target_jobs = {"leaky_service", "flaky_service", "healer", "prometheus"}

    def targets_ready():
        targets = request(local_url("PROMETHEUS_PORT", 9090) + "/api/v1/targets")["data"][
            "activeTargets"
        ]
        healthy = {target["labels"]["job"] for target in targets if target["health"] == "up"}
        return target_jobs <= healthy

    await_condition(targets_ready)
    password = (ROOT / ".secrets/grafana_password").read_text().strip()
    basic = base64.b64encode(("admin:" + password).encode()).decode()
    grafana_headers = {"Authorization": "Basic " + basic}
    grafana = local_url("GRAFANA_PORT", 3001)
    request(grafana + "/api/datasources/uid/prometheus", grafana_headers)
    request(grafana + "/api/datasources/uid/loki", grafana_headers)
    dashboards = request(grafana + "/api/search?query=Self-Healing", grafana_headers)
    assert any(item["title"] == "Self-Healing Monitor" for item in dashboards)
    print(
        "PASS: connectivity, authentication, disabled demo endpoint, scrape targets, Grafana provisioning"
    )
    if not args.exercise_restart:
        return

    before = started_at()
    start = datetime.now(timezone.utc)
    for _ in range(12):
        request(local_url("LEAKY_PORT", 8080) + "/leak")

    def pending_incident():
        for incident in request(api + "/approval/queue", headers):
            created = datetime.fromisoformat(incident["created_at"].replace("Z", "+00:00"))
            if (
                incident["service"] == "leaky_service"
                and incident["alert_name"] == "HighMemoryUsage"
                and created >= start
            ):
                return incident
        return None

    incident = await_condition(pending_incident)
    assert incident["action"] == "RESTART_CONTAINER"
    payload = {"incident_id": incident["incident_id"], "status": "approved"}
    result = request(api + "/approval/action", headers, payload)
    assert result["execution"]["status"] == "success", "Restart command failed"
    assert result["execution"]["alert_resolved"], "Recovery was not verified"
    after = started_at()
    assert before != after, "Container did not restart"
    request(api + "/approval/action", headers, payload, expected=404)
    assert started_at() == after, "Repeated approval restarted the container twice"
    records = request(api + "/audit?limit=100", headers)
    assert any(
        row["incident_id"] == incident["incident_id"] and row["alert_resolved"] for row in records
    )
    print(
        "PASS: Alertmanager delivery, operator approval, real restart, fresh recovery, duplicate approval denied, persisted audit"
    )


if __name__ == "__main__":
    main()
