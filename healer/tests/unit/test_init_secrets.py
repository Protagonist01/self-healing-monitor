import os
import stat

import pytest

from scripts.init_secrets import initialize_secrets


def test_secret_generation_preserves_credentials_and_does_not_print_them(tmp_path, capsys):
    root = tmp_path / ".secrets"
    initialize_secrets(root)
    first = {path.name: path.read_text() for path in root.iterdir()}
    assert len(first) == 3
    assert all(len(value) >= 32 for value in first.values())
    initialize_secrets(root)
    assert first == {path.name: path.read_text() for path in root.iterdir()}
    output = capsys.readouterr().out
    assert all(value not in output for value in first.values())


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes are not Windows ACLs")
def test_private_directory_and_readable_service_mounts(tmp_path):
    root = tmp_path / ".secrets"
    initialize_secrets(root)
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o644 for path in root.iterdir())
