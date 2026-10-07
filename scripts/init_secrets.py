"""Generate Compose credentials; preserve contents and protect the host directory."""

import os
import secrets
from pathlib import Path


def initialize_secrets(root: Path):
    if root.is_symlink():
        raise ValueError("The secrets directory must not be a symlink")
    root.mkdir(mode=0o700, exist_ok=True)
    if os.name == "posix":
        root.chmod(0o700)
    for name in ("healer_api_key", "postgres_password", "grafana_password"):
        path = root / name
        if path.is_symlink():
            raise ValueError(f"Secret {name} must not be a symlink")
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            print(f"Kept existing {name}")
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(48))
            print(f"Created {name}")
        # Compose file secrets are bind mounts; uid/gid/mode cannot remap the
        # source file's ownership. Non-root service users must be able to read it.
        # The 0700 host directory prevents other host users traversing to it.
        if os.name == "posix":
            path.chmod(0o644)
    print("Credentials are in .secrets/. Keep this directory private and out of Git.")


if __name__ == "__main__":
    initialize_secrets(Path(__file__).resolve().parents[1] / ".secrets")
