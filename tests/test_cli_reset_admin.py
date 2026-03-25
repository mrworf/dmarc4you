"""CLI break-glass reset-admin-password: temp DB, bootstrap admin, reset and verify login."""

import tempfile
from pathlib import Path

import pytest
import yaml

from backend.config import load_config
from backend.storage.sqlite import get_connection
from backend.storage.sqlite import run_migrations
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.services.auth_service import login as auth_login

from cli.commands import reset_admin_password


@pytest.fixture
def temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def temp_config_path(temp_db_path: str) -> str:
    """Write a temp config YAML pointing at temp DB; return path."""
    fd, path = tempfile.mkstemp(suffix=".yaml")
    import os
    os.close(fd)
    data = {"database": {"path": temp_db_path}, "log": {"level": "INFO"}, "auth": {"session_secret": "test"}}
    with open(path, "w") as f:
        yaml.safe_dump(data, f)
    yield path
    Path(path).unlink(missing_ok=True)


def test_reset_admin_password_success_and_login(temp_db_path: str, temp_config_path: str) -> None:
    run_migrations(temp_db_path)
    old_password = ensure_bootstrap_admin(temp_db_path)
    assert old_password is not None
    config = load_config(temp_config_path)
    new_password = reset_admin_password(Path(temp_config_path))
    assert new_password is not None
    assert new_password != old_password
    conn = get_connection(temp_db_path)
    row = conn.execute("SELECT must_change_password FROM users WHERE username = 'admin'").fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1
    user, _ = auth_login(config, "admin", new_password)
    assert user is not None
    user_old, _ = auth_login(config, "admin", old_password)
    assert user_old is None


def test_reset_admin_password_no_admin_returns_none(temp_config_path: str) -> None:
    """When no admin user exists, reset returns None and does not print a password (caller exits non-zero)."""
    config = load_config(temp_config_path)
    run_migrations(config.database_path)
    result = reset_admin_password(Path(temp_config_path))
    assert result is None
