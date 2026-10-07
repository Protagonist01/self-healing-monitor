"""Create local Compose credentials without overwriting existing secrets."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1] / ".secrets"
root.mkdir(mode=0o700, exist_ok=True)
for name in ("healer_api_key", "postgres_password", "grafana_password"):
    path = root / name
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"Kept existing {name}")
        continue
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(secrets.token_urlsafe(48))
    print(f"Created {name}")
print("Credentials are in .secrets/. Keep this directory private and out of Git.")
