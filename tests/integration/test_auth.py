"""Auth slice: login, logout, me, session cookie, audit."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def auth_app_client(temp_db_path: str):
    """Prepare app with temp DB (migrations + bootstrap admin), set app.state.config, yield client and admin password."""
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None
    app.state.config = Config(
        database_path=temp_db_path,
        log_level="INFO",
        session_secret="test-secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
    )
    yield wrap_client_with_csrf(TestClient(app)), password
    app.state.config = None


def test_login_success_returns_user_and_sets_cookie(auth_app_client) -> None:
    client, password = auth_app_client
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "super-admin"
    assert "id" in data["user"]
    assert "dmarc_session" in response.cookies


def test_login_wrong_password_returns_401(auth_app_client) -> None:
    client, _ = auth_app_client
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    assert "dmarc_session" not in response.cookies or not response.cookies.get("dmarc_session")


def test_login_invalid_username_returns_401(auth_app_client) -> None:
    client, password = auth_app_client
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "bad user!", "password": password},
    )
    assert response.status_code == 401


def test_logout_clears_session(auth_app_client) -> None:
    client, password = auth_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401


def test_me_with_valid_session_returns_user_and_domain_visibility(auth_app_client) -> None:
    client, password = auth_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["username"] == "admin"
    assert data["user"]["role"] == "super-admin"
    assert data["all_domains"] is True
    assert "domain_ids" in data


def test_me_without_session_returns_401(auth_app_client) -> None:
    client, _ = auth_app_client
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_returns_optional_profile_fields(auth_app_client, temp_db_path: str) -> None:
    client, password = auth_app_client
    conn = get_connection(temp_db_path)
    conn.execute(
        "UPDATE users SET full_name = ?, email = ? WHERE username = 'admin'",
        ("Bootstrap Admin", "admin@example.com"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["full_name"] == "Bootstrap Admin"
    assert data["user"]["email"] == "admin@example.com"


def test_update_me_updates_optional_profile_fields(auth_app_client) -> None:
    client, password = auth_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.put(
        "/api/v1/auth/me",
        json={"full_name": "Updated Admin", "email": "updated@example.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["full_name"] == "Updated Admin"
    assert data["user"]["email"] == "updated@example.com"


def test_audit_has_login_event(auth_app_client, temp_db_path: str) -> None:
    client, password = auth_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT action_type, outcome FROM audit_log WHERE action_type IN ('login_success', 'login_failure') ORDER BY timestamp"
        )
        rows = cur.fetchall()
        assert len(rows) >= 1
        assert any(r[0] == "login_success" and r[1] == "success" for r in rows)
    finally:
        conn.close()
