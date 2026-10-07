# Security

This is pre-production software. No stable production release is currently supported.
Use a private network or SSH tunnel, authenticated operator access, and a dedicated
Docker host. Docker socket access can grant control of the host; the application's
container allowlist is not an isolation boundary against a compromised healer.

Never post API keys, database credentials, customer logs, or exploitable vulnerability
details in public issues. Use GitHub private vulnerability reporting when enabled:
https://github.com/Protagonist01/self-healing-monitor/security/advisories/new
If private reporting is unavailable, open a public issue requesting a private contact
without including vulnerability details. No response-time guarantee is offered.

Include affected versions, reproduction steps using synthetic data, and expected
impact. Rotate exposed credentials immediately; deleting a file does not remove it
from Git history.

Known dependency findings and their exact, expiring exceptions are documented in
[the dependency security review](docs/dependency-security.md). Chroma server mode
is disabled; the scan reports these findings instead of hiding them.
