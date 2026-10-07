# Deployment

## Supported scope

One Docker host, one healer process, a private operator API, and PostgreSQL. This is
a pre-production deployment template, not a completed production acceptance test.
Do not run multiple healer replicas: startup recovery assumes one worker owns the
queue. Use an SSH tunnel for remote access, for example:

```sh
ssh -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000 operator@your-host
```

Then use the dashboard at localhost:3000. For a shared private domain, terminate TLS,
set `CORS_ALLOWED_ORIGINS` and rebuild the dashboard with `VITE_HEALER_API_URL` set to
the private HTTPS API address. Do not put an API key in a Vite build variable.

## Configure

1. Copy `.env.example` to `.env` and run `python scripts/init_secrets.py`.
2. Keep `.secrets/` readable only by administrators. Compose mounts credentials in
   the healer, Alertmanager, PostgreSQL, and Grafana as needed. The API accepts the
   operator's `X-API-Key` header and Alertmanager's bearer token.

   On POSIX hosts, the initializer sets the directory to `0700` and files to `0644`.
   The protected directory restricts host access; readable files let the containers'
   different service users read their individual read-only secret mounts. On Windows,
   restrict the directory with filesystem ACLs.
3. Keep `ENVIRONMENT=production`, `ENABLE_DEMO_ENDPOINT=false`, and
   `REQUIRE_HUMAN_APPROVAL=true`. Production startup rejects a missing/short API key,
   an empty container allowlist, SQLite, or an enabled demo endpoint.
4. Set `DOCKER_ALLOWED_SERVICES` to exact container names you own. The supplied names
   refer to intentionally faulty demo services. Replace their scrape targets and
   alert rules before monitoring a real application. Do not run fault-injection
   demo services beside business workloads.
5. Add provider keys only if needed. Logs and runbook excerpts may be sent to those
   providers; remove private data before enabling them.
6. Start with the README Compose command. All published ports bind to `127.0.0.1`.

The Docker socket permits host-level control. A private API and application allowlist
reduce exposure but do not contain a compromised healer. Use a dedicated host and
restrict who can access the socket. See [Docker's security guidance](https://docs.docker.com/engine/security/).

Existing PostgreSQL volumes keep their original passwords. Generating a new secret
file does not rotate the database password: use an administrator connection to rotate
it deliberately and update the matching secret. Never delete a data volume to fix auth.

## Acceptance before production

- Build and scan all container images. Resolve critical/high findings and review
  lower-severity findings; mutable image tags need a verified release digest.
- Verify an unauthenticated request to `/audit` returns 401, and that Alertmanager
  successfully delivers an authenticated firing alert.
- Submit a disposable service incident, approve it, and verify exactly one restart,
  fresh Prometheus samples, and a persisted audit record. Attempt a disallowed target.
- Stop the healer during processing. On restart the interrupted item must be failed
  for review, while pending items remain available. Check `incident_queue` for failures.
- Exercise a database outage and restoration. Test PostgreSQL backups on a separate
  restore target and define retention for audit, queue, and outcome tables.
- Confirm firewall rules, TLS or SSH access, credential rotation, disk alerts, and
  an operator response process. Run a representative load test.

`/health` is a liveness/configuration endpoint, not proof that Docker, PostgreSQL,
Prometheus, or the worker is healthy. Monitor these dependencies separately.

## Operational limits

Only exact-name container restart is implemented in the Docker execution path.
Scale and rollback require operator deployment tooling. The Kubernetes module is
experimental and disconnected from this path.

Recovery checks use the supplied memory/error/down thresholds. They are not a general
alert-expression evaluator; adapt and test them with any new alert rules. Missing
metrics leave recovery unverified. Loki has no log collector in this template, and
deployment history has no provider; absent data is reported honestly.

A crash after a command and before its audit write has an uncertain outcome. The
queue does not claim exactly-once delivery; interrupted work requires investigation.
Approved actions are claimed before execution to prevent double approval. If execution
or auditing is interrupted, inspect the approved row and actual service state before
submitting another incident. Human decisions use a shared operator key, not individual
user identities. Per-user roles and a separate webhook-only credential are future work.
