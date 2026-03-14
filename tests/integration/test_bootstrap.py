"""Bootstrap admin: first run creates admin; second run does not; password is hashed."""

import pytest

from backend.storage.sqlite import get_connection, run_migrations
from backend.auth.bootstrap import ensure_bootstrap_admin, BOOTSTRAP_USERNAME, ROLE_SUPER_ADMIN
from backend.auth.password import verify_password


def test_first_run_creates_admin_and_returns_password(temp_db_path: str) -> None:
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (BOOTSTRAP_USERNAME,),
        )
        row = cur.fetchone()
        assert row is not None
        user_id, username, password_hash, role = row
        assert username == BOOTSTRAP_USERNAME
        assert role == ROLE_SUPER_ADMIN
        assert password_hash != password
        assert verify_password(password, password_hash)
    finally:
        conn.close()


def test_second_run_does_not_create_duplicate(temp_db_path: str) -> None:
    first = ensure_bootstrap_admin(temp_db_path)
    assert first is not None
    second = ensure_bootstrap_admin(temp_db_path)
    assert second is None
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM users")
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
