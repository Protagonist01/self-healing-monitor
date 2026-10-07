# Project assessment — 11 September 2026

Scope: working tree and the fetched `origin/main`, including pre-existing uncommitted
features. Target: one Docker host with a private API. Changes have not been pushed.

| Question | Finding |
| --- | --- |
| Production ready? | **Not yet.** Concrete code and configuration defects were fixed, but live Docker acceptance and full dependency/image security checks remain release gates. |
| Professional README? | **Improved.** Replaced the long, stale overview with concise setup, supported behavior, limits, and documentation links. |
| Ready for open source? | **Suitable as a clearly labeled pre-production project after checks pass.** Added the missing MIT license, contribution/security guidance, CI, and dependency-update configuration. |
| Appropriate files for GitHub? | **The tracked file categories are appropriate.** Source, tests, configuration templates, docs, lockfiles, and small demo media belong in Git. Local secrets, runtime state, builds, and publishing drafts are excluded. |

## Defects fixed

- Removed shell-based Docker scaling and implicit successful mock repairs. Exact
  container names and an explicit allowlist are required for restart. Unsupported
  Docker scaling/rollback report that status instead of pretending to work.
- Removed invented metrics, OOM logs, deployment history, and confident mock diagnoses.
- Enabled approval by default; preserved the original policy decision when a human
  approves. Approval status is validated before mutation, and an atomic claim prevents
  concurrent approvals from executing twice. SQLite approval handling now works.
- Added verification after human-approved execution and stopped treating command success
  as proof of recovery. Notifications report missing configuration and HTTP failures.
- Fixed the deduplication cutoff and serialized durable intake to suppress concurrent
  pending duplicates. Interrupted work is quarantined instead of blindly replayed.
- Replaced the PostgreSQL pool with its thread-safe variant and fixed connection returns
  in feedback and correlation. Shutdown waits for the worker before closing the pool.
- Restricted CORS, rate-limited synthetic intake, bounded the limiter's client map,
  corrected streaming updates after the first five records, and disabled demo intake
  unless explicitly enabled.
- Bound Compose ports to localhost, added generated file secrets and Alertmanager bearer
  authentication, forwarded safety settings, and added dashboard key entry in memory.
- Fixed ServiceDown target attribution and the error-demo alert name. Dashboard image
  builds now use `npm ci` and accept the API address at build time.
- Added dependency pins, CI, Docker build exclusions, and portable Make commands.

## Verification

The first corrected backend run passed **63 tests**, including concurrent approval,
concurrent intake, interrupted work, invalid approval, missing telemetry, and API auth.
All **4 evaluation fixtures** passed action and policy checks. Compose configuration
validated with `.env.example` and generated secrets. Dependency and final build results
are recorded below as they complete.

A file-name and common-secret-pattern scan found no tracked runtime databases, `.env`,
virtual environments, dependency directories, or builds. No matching secret patterns
were found in the current publishable files or the **3 available Git commits**. This
was a limited pattern scan, not a guarantee that all sensitive data is absent. Demo
media totals approximately **4.99 MiB**; the existing media was retained as historical
documentation and was not exhaustively reviewed frame by frame.

## Remaining release gates

1. Start Docker and run the acceptance steps in [deployment](deployment.md), including
   authenticated Alertmanager delivery, exactly one disposable-container restart,
   observable recovery, queue interruption, and PostgreSQL outage/restore exercises.
2. Complete Python vulnerability scanning and container-image scans, and validate the
   pinned Python dependencies on Linux/Python 3.11. CI is provided but has not run on
   GitHub in this assessment.
3. Configure real service names, telemetry, retention, backups, and credential rotation.
   The supplied faulty services are demonstration targets. Loki has no log shipper and
   deployment history has no provider. Recovery checks support the supplied alert rules.
4. Review the complete working-tree diff, including features that were already uncommitted,
   before publishing. Enable GitHub secret scanning/private reporting and review the demo
   recordings for sensitive content. No repository settings were changed remotely.

The API should remain private because it can control Docker containers. The application
allowlist does not contain a compromised process with socket access; see
[Docker's security model](https://docs.docker.com/engine/security/).

## Final local verification

- Backend: **63 passed**, with 3 dependency deprecation warnings, after the final code fixes.
- Evaluations: **4/4** action choices and **4/4** policy decisions.
- Compose: configuration validation passed; no running Docker engine was available.
- Documentation: local Markdown links and `git diff --check` passed.
- Dashboard: final TypeScript and Vite production build **passed** on 12 September.
- Frontend dependencies: update succeeded and npm audit reported **0 vulnerabilities**.
- Python dependencies: **116 exact pins** resolved for Python 3.11 and platform markers.
  The pinned set installed successfully on Windows/Python 3.13 after retrying downloads.
  Linux/Python 3.11 validation remains a CI release gate.
- Python vulnerability scans: incomplete after repeated registry timeouts. No clean
  Python audit is claimed.
