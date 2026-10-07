# Dependency security review — 7 October 2026

Run `python scripts/audit_dependencies.py` after installing `pip-audit`. The raw
report is saved under ignored `output/`. Network/scanner failures fail the check;
they never reuse an old report. Every new finding blocks CI.

## Reviewed upstream exceptions

ChromaDB 1.5.9 has four distinct server advisories with no patched release reported
by the advisory database during this audit:

| Advisory | Affected surface |
| --- | --- |
| [CVE-2026-45829](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c) | Collection creation API with remote model code |
| [CVE-2026-45833](https://github.com/advisories/GHSA-36p7-vc44-83pf) | Collection update API with remote model code |
| [CVE-2026-45831](https://github.com/advisories/GHSA-xph7-9rjv-w5fr) | Server RBAC scope |
| [CVE-2026-45830](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr) | Server tenant authorization |

The supported app uses `chromadb.PersistentClient` inside the healer process and
does not run a Chroma HTTP server. It creates one local runbook collection using
the project's own hash/OpenAI embedding classes. It accepts no embedding-provider,
remote model-repository, or `trust_remote_code` configuration from alerts. Settings
reject a nonempty `CHROMA_SERVER_URL` in every environment.

**Assessment:** the documented server entry points are absent in this deployment.
This is a reachability assessment, not a fix to ChromaDB and not proof that the
package is vulnerability-free. Do not expose a Chroma server with these pins.

The machine-readable exceptions apply only to the exact package, version, and
advisory IDs. They expire on **6 November 2026**. Review upstream fixes before
renewing them; changing the package version invalidates them automatically.
The check prints all accepted findings. It never claims zero vulnerabilities.
Its tests prove that new, expired, and wrong-version findings fail the review.

## Updates in this audit

The lockfiles update `source-map-js`, `multidict`, `oauthlib`, and `urllib3` to
resolve the fixable findings returned by the scans. Container-image findings and
live provider quality require their own checks; a Python scan does not cover them.
