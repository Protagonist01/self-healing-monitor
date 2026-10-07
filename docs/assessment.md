# Project assessment — 7 October 2026

This audit covers the full working tree, including the substantial safety and feature
changes already present before the audit, the three existing Git commits, public
GitHub metadata, CI/deployment records, and local packaging. The supported target is
one private Docker host and one healer process. There is no public URL.

## Recruiter readiness

The README now explains the problem, engineering decisions, stack, setup, actual demo,
and limits. The code includes safeguards that are worth discussing in an interview:
atomic approval claims, durable intake, duplicate suppression, fail-safe execution,
and recovery verification using fresh telemetry. Historical media is labeled honestly.

The project is suitable for a portfolio as **pre-production software**. It is not
presented as an accepted production service or a validated autonomous SRE system.

## Findings and changes

- Preserved and reviewed existing uncommitted work instead of resetting it.
- Added bounded webhook/demo input and safety configuration validation. Invalid
  provider JSON, nonfinite confidence, and failed diagnosis produce zero confidence.
- Require explicit low impact for automatic infrastructure action. Notifications
  cannot count as repairs. Cached metrics cannot prove post-restart recovery.
- Count verified automatic and approved repairs through one metrics path. Distinct
  services, rather than repeated audit rows, determine cascading context.
- Remove deleted runbooks from the index; bound embedding request timeouts.
- Format Python consistently and add lint/format checks. Format and typecheck the UI;
  prevent responses from an old connection from restoring data after disconnect.
- Provision Grafana data sources and dashboard. Persist telemetry state, allow local
  port overrides, update telemetry images, and pin image and Actions references.
- Package the dashboard as a non-root container and keep build tools out of the
  healer runtime stage. Exclude secrets, caches, and build output from Git/images.
- Correct documentation claims about calibrated accuracy, checkpoints, pure nodes,
  node timing, embeddings, runbook updates, and unsupported remediation.
- Add a portable deployment smoke script and GitHub checks for the disposable
  Alertmanager-to-approval-to-restart path. No public deployment is created.

## Verified evidence

| Check | Result |
| --- | --- |
| Local backend, Windows/Python 3.13 | 91 tests passed; POSIX permission test skipped; one upstream warning |
| Backend in Linux/Python 3.11 image | 92 tests passed; one upstream warning |
| Fixed policy evaluations | 4/4 action selections and 4/4 policy decisions |
| Python lint and format | Passed |
| Dashboard formatting, typecheck, build | Passed |
| npm audit after updates | Zero reported vulnerabilities |
| Python dependency review | Fixable findings resolved; four reviewed upstream exceptions |
| Publish file and common-secret-pattern scan | No forbidden files or matching patterns in publishable files or Git history |
| Relative documentation links | Passed |
| Docker Compose configuration | Passed |
| Prometheus and Alertmanager configuration validation | Passed using their packaged validation tools |
| Browser with real development API | Connection, rejection, disconnect clearing, and mobile viewport checks passed |
| Local private Compose stack | Authentication, scrape targets, and Grafana provisioning passed |
| Local disposable restart | Alertmanager delivery, approval, real restart, fresh recovery, persisted audit, and duplicate approval denial passed |
| GitHub container build, image scan, full restart | [All jobs passed at ee85df0](https://github.com/Protagonist01/self-healing-monitor/actions/runs/37558642999) |

The image gate covers fixable high/critical OS vulnerabilities in the four project
images. The first scan found 50 such entries in the Python demo image; OS updates
resolved the gate's findings. Unpatched/lower-severity findings and third-party
telemetry/database images still require release review. Demo Python lockfiles now
use the healer's tested versions and are included in dependency review.

The secret scan is limited pattern matching, not proof that every possible sensitive
value is absent. Old demo recordings were retained as historical documentation and
were not exhaustively reviewed frame by frame.

## GitHub and deployment state

The public repository has a useful description and relevant topics. At the start of
this audit, `origin/main` was `68b1846`, there were no Actions runs, deployment records,
releases, or Pages site, and the local improvements had not been pushed. Anonymous
access could not inspect branch protection; no conclusion is drawn about those settings.
Changes are published on `codex/recruiter-ready-audit` in
[PR #1](https://github.com/Protagonist01/self-healing-monitor/pull/1). The default
branch has not been rewritten. The PR contains the updated recruiter-facing README,
deployment template, CI checks, and current screenshot.

## Remaining production work

- Address the [ChromaDB server advisories](dependency-security.md) through an upstream
  fix or reviewed replacement. Embedded-only exceptions expire on 6 November 2026;
  passing the review gate does not mean the package has zero vulnerabilities.
- Review findings outside the image gate and validate backups, retention, recovery during database
  outages, and representative load. A successful demo restart is not production acceptance.
- Configure real services, alert-specific verification, a log collector, and an actual
  deployment-history provider. The supplied services are intentionally faulty demos.
- Collect human-reviewed real incidents to evaluate diagnosis quality and calibrate
  confidence before allowing autonomous repairs. Four policy fixtures do not do that.
- Add per-user operator identities and scoped webhook credentials if the tool is shared.
  Keep Docker access on a dedicated private host with an operator response process.

The [September assessment](assessment-2026-09-11.md) records the earlier audit; its
verification and deployment statements are historical.
