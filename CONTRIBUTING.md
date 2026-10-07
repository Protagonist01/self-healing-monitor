# Contributing

Open an issue describing the problem before proposing a large change. For a small
fix, a focused pull request with a clear explanation is welcome.

1. Fork the repository and create a branch.
2. Follow the development commands in the README.
3. Add regression tests for behavior changes. Mock infrastructure actions in tests.
4. Run Python lint/format checks, backend tests, policy evaluations, dependency
   review, dashboard format/build checks, and npm audit (commands in the README).
5. Describe the change, checks run, and any remaining limitations in your pull request.

Keep secrets, runtime databases, virtual environments, generated builds, and local
publishing drafts out of commits. Keep sample media small and free of private data.
Changes to remediation permissions need explicit tests for denied actions.

Contributions are made under the repository's MIT license. Be respectful and keep
review discussions focused on the work.

## Dependency updates

Edit `healer/requirements.in`, then regenerate `healer/requirements.txt` with uv:

```sh
uv pip compile healer/requirements.in --universal --python-version 3.11 -o healer/requirements.txt
```

Install the resulting pins and rerun checks before proposing the update. The lockfile
includes transitive dependencies; do not replace it with a freeze of a developer's
unrelated tools. Dashboard dependencies are locked by `dashboard/package-lock.json`.

The two demo services have small input files and complete transitive pins. Regenerate
them against the healer's tested versions:

```sh
uv pip compile demo_services/leaky_service/requirements.in --python-version 3.11 --constraint healer/requirements.txt -o demo_services/leaky_service/requirements.txt
uv pip compile demo_services/flaky_service/requirements.in --python-version 3.11 --constraint healer/requirements.txt -o demo_services/flaky_service/requirements.txt
```

The dependency review scans all three Python lockfiles.

Base images and telemetry images are pinned by digest. Update the readable tag and
its matching digest together, then build and run the deployment smoke checks.
GitHub Actions are pinned to verified commit SHAs, following
[GitHub's secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use).
Dependency exceptions must name an exact version and advisory, explain reachability,
and have a review expiry. They are reported by CI, not silently suppressed.
