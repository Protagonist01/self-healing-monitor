# Build Book — Self-Healing Monitor

A journal of implementation decisions and verification.

## Index
- [Entry 1 — Make remediation fail safely](#entry-1--make-remediation-fail-safely)
- [Entry 2 — Separate dependency evidence from code tests](#entry-2--separate-dependency-evidence-from-code-tests)
- [Entry 3 — Require fresh recovery evidence](#entry-3--require-fresh-recovery-evidence)


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
