# Build Book — Self-Healing Monitor

A journal of implementation decisions and verification.

## Index
- [Entry 1 — Make remediation fail safely](#entry-1--make-remediation-fail-safely)
- [Entry 2 — Separate dependency evidence from code tests](#entry-2--separate-dependency-evidence-from-code-tests)
- [Entry 3 — Require fresh recovery evidence](#entry-3--require-fresh-recovery-evidence)
- [Entry 4 — Make file secrets usable by non-root services](#entry-4--make-file-secrets-usable-by-non-root-services)


## Entry 1 — Make remediation fail safely

The September 2026 assessment found that missing Docker access produced fake success,
approval processing used a cursor context manager unsupported by SQLite, and a
read-then-update approval could execute twice. The selected deployment is one Docker
host with a private API.

### Why

An executor result must describe a real operation. Keeping implicit mocks would
make an incident look repaired when nothing happened. Tests should supply their own
fake clients. Scaling this Compose demo is not supported: its services use fixed
container names and host ports. Returning an explicit unsupported result is safer
than invoking a shell with alert-controlled input.

### How to build it

1. Return failure when Docker is unavailable; select exactly one container by its
   exact name, and reject targets outside the configured allowlist.
2. Replace the shell-based scaling path with an explicit unsupported result.
3. Validate approval status before opening a transaction. Claim a pending row with
   `UPDATE ... WHERE status = 'pending' RETURNING ...`, so concurrent requests cannot
   both win. Close the cursor explicitly for PostgreSQL and SQLite compatibility.
4. Execute the claimed action, verify recovery, then persist the result. Command
   success alone must never increment a recovery counter.
5. Test with temporary SQLite databases and fake Docker clients. Keep external
   network calls and developer credentials out of the test environment.

### Investigation so far

The initial test run failed and attempted external dependencies because several
tests patched the defining module rather than the module that imported the symbol.
The run was stopped. Regression tests will patch call sites and use an isolated
database. Docker's engine is currently unavailable, so live restart and recovery
remain unverified.

## Verification update

The corrected test run passed 63 tests. The socket-level test network block initially
broke Windows asyncio, whose internal wake-up pipe uses a local socket pair. Blocking
HTTP transport instead preserves that runtime mechanism while stopping external HTTP
requests. All four fixed-policy evaluation fixtures passed and Compose validated.

## Entry 2 — Separate dependency evidence from code tests

The frontend audit found seven dependency findings. Updating within the existing
package ranges returned zero findings, but npm omitted a platform-specific Rollup
binary. A clean `npm ci --include=optional` is being used to restore the install from
the lockfile. Do not interpret a clean audit as a successful build.

The Python requirements used only lower bounds. `uv pip compile --universal
--python-version 3.11` now resolves exact direct and transitive versions, including
platform markers. The existing environment is Python 3.13, so the Linux 3.11 CI build
remains a separate check. Registry timeouts have blocked Python vulnerability scans;
those are recorded as incomplete, not passed.

## Entry 3 — Require fresh recovery evidence
**Date:** 7 October 2026. **Files touched:** `healer/src/agent/nodes/verify_action.py`,
`healer/src/agent/nodes/diagnose.py`, `healer/tests/integration/test_verify_action.py`.

### Context

The follow-up audit found that verification accepted any below-threshold Prometheus
result. An instant query can return a cached sample from before a restart, so a
successful Docker command plus that value does not prove recovery.

### Before you read on

How would you prove that telemetry came from the service after the command completed?
Consider the difference between a query timestamp and the timestamp of a scrape.

### Options considered

- Compare the timestamp on an instant-vector result. Rejected: it is the query
  evaluation time, which can be fresh even when the underlying scrape is old.
- Require `timestamp(up)` after execution completion, plus `up == 1` and a healthy
  metric value. Chosen: Prometheus itself can check source-sample freshness.

### Why

A cached healthy sample must not turn an unknown outcome into a successful repair.
Missing telemetry leaves the action unverified. Sending a notification also cannot
count as repairing infrastructure.

### How to build it

1. Store an ISO UTC `completed_at` on every executor result.
2. Add `_has_fresh_scrape(service, completed_at) -> bool`. Convert completion to Unix
   seconds and query `(up{job="service"} == 1) and
   (timestamp(up{job="service"}) > completion_seconds)`. Encode the service with
   `json.dumps` before embedding it in PromQL.
3. Set verification true only when the threshold check passes and that query has a
   result. Missing completion time, API failures, and an empty result return false.
4. Skip repair verification for `NOTIFY_ONLY`. It never increments resolved counts.
5. Validate provider JSON with a Pydantic schema: finite confidence from zero to one,
   a nonempty root cause, and at most five string evidence items. Failed responses
   produce zero confidence and no invented supporting evidence.
6. Run `python -m pytest healer/tests -q`. Regression cases cover cached telemetry,
   notifications, missing completion times, and malformed provider JSON.

### Investigation so far

The baseline passed 63 tests. Dependency scans then found a frontend advisory and
Python advisories missed by the older assessment. Updates and deployment checks are
in progress; a clean build alone is not evidence of clean dependencies.

## Entry 4 — Make file secrets usable by non-root services
**Date:** 7 October 2026. **Files touched:** `scripts/init_secrets.py`,
`healer/tests/unit/test_init_secrets.py`.

### Context

The generator created mode-0600 files owned by the host operator. Compose file secrets
are bind mounts: the secret's `uid`, `gid`, and `mode` do not remap the source file.
Grafana and PostgreSQL use other user IDs, so private host files can become unreadable
inside these services even though the same stack works with Windows bind mounts.

### Before you read on

How can the host protect credential files while separate service users read their mounts?

### Options considered

Running every service as root would avoid the mismatch but discard their normal user
separation. Chosen: a host directory with mode 0700 and credential files with mode 0644.
Other host users cannot traverse the private directory. Compose mounts only the needed
files read-only into each service, where the service user can read them.

### How to build it

1. Put generation in `initialize_secrets(root: Path)` and invoke it only from `__main__`.
2. Reject symlink directories and files; create the directory and enforce 0700 on POSIX.
3. Open each credential with `O_CREAT | O_EXCL` so reruns preserve existing contents.
4. Use 0644 on POSIX credential files, including existing files, to make mounts readable
   without remapping ownership. Preserve Windows ACL handling; do not claim POSIX modes
   secure a Windows directory. Keep Windows directory access restricted manually.
5. Test generation, reruns, absence of credential values in stdout, and POSIX permissions
   in temporary directories. Reuse generated credentials for container smoke checks.

### Investigation so far

This permission issue was found while reviewing the Linux CI path. The host uses Windows,
so its successful generation does not prove Linux service access. Linux permission tests
and actual startup checks are separate evidence.

## Entry 5 — Check the OS inside the deployment images
**Date:** 7 October 2026. **Files touched:** the four project Dockerfiles,
`infra/docker-compose.yml`, `.github/workflows/ci.yml`.

### Context

The Python and npm dependency checks do not inspect operating-system packages.
Trivy reported 50 high/critical fixed vulnerability entries in the original demo
image, despite its pinned official Python base. Pinning identifies a base precisely;
it does not keep the packages inside it patched.

### How to build it

1. Build all four images with Compose. Mount the Docker socket and a dedicated cache
   volume into the pinned Trivy image. Select `--pkg-types os`, `HIGH,CRITICAL`, and
   `--ignore-unfixed`; use `--exit-code 1` so fixable findings fail CI.
2. Give the scanner `--timeout 15m`. Its first database download exceeded its default
   timeout on this host, so the first scan failed before producing a useful result.
3. Add `apt-get update && apt-get upgrade -y` to each Debian runtime before application
   layers, then remove package indexes. Use `apk upgrade --no-cache` in the Alpine
   dashboard image and restore its non-root user after upgrading.
4. Rebuild and scan the actual resulting images. OS repository updates mean these
   layers vary with build date; record the built image digest for a release.
5. Check Prometheus rules with `promtool` and Alertmanager with `amtool`. Use a separate
   Compose project and alternate localhost ports for smoke testing. Keep existing
   data volumes intact. Allow PostgreSQL an initialization period before health retries.

The gate covers fixable high/critical OS findings in project images. It does not
cover every severity, unpatched finding, Python/npm dependency, or third-party service image.

### Verification and dependency follow-through

The updated GitHub run passed all three jobs, including all four OS scans and the
Alertmanager-to-approval-to-restart smoke test. Windows passed 91 backend tests with
one POSIX test skipped; the Linux image passed all 92. The local stack separately
proved fresh recovery, a persisted audit record, and rejection of duplicate approval.
The browser proved connection, rejection, disconnect clearing, and mobile sizing.

The demo services still had minimum-version requirements. Add small `requirements.in`
files, pin their three direct dependencies to the healer's tested versions, and compile
their 14-package lockfiles with `--constraint healer/requirements.txt`. Include these
locks in `audit_dependencies.py` so future demo-only updates are scanned as well.
