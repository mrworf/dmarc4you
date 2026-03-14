"""CSRF protection: double-submit cookie pattern enforcement tests."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin


@pytest.fixture
def csrf_app_client(temp_db_path: str):
    """Prepare app with temp DB, bootstrap admin, one domain, and one API key."""
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None
    config = Config(
        database_path=temp_db_path,
        log_level="INFO",
        session_secret="test-secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
        csrf_cookie_name="dmarc_csrf",
    )
    app.state.config = config
    conn = get_connection(temp_db_path)
    conn.execute(
        "INSERT INTO domains (id, name, status, created_at, archived_at, archived_by_user_id, retention_days, retention_delete_at, retention_paused, retention_paused_at, retention_pause_reason, retention_remaining_seconds) VALUES (?, ?, 'active', '2026-01-01T00:00:00Z', NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL)",
        ("dom_example", "example.com"),
    )
    conn.commit()
    conn.close()
    yield TestClient(app), password, config
    app.state.config = None


def test_login_sets_csrf_cookie(csrf_app_client) -> None:
    """Login should set both session and CSRF cookies."""
    client, password, config = csrf_app_client
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    assert response.status_code == 200
    assert config.session_cookie_name in response.cookies
    assert config.csrf_cookie_name in response.cookies
    csrf_token = response.cookies.get(config.csrf_cookie_name)
    assert csrf_token and len(csrf_token) > 20


def test_me_sets_csrf_cookie_if_missing(csrf_app_client) -> None:
    """GET /me should set CSRF cookie if session exists but CSRF cookie is missing."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    session_cookie = login_resp.cookies.get(config.session_cookie_name)
    client.cookies.clear()
    client.cookies.set(config.session_cookie_name, session_cookie)
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert config.csrf_cookie_name in me_resp.cookies


def test_post_with_valid_csrf_succeeds(csrf_app_client) -> None:
    """POST request with matching CSRF header should succeed."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    csrf_token = login_resp.cookies.get(config.csrf_cookie_name)
    response = client.post(
        "/api/v1/domains",
        json={"name": "new.example.com"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code in (200, 201)


def test_post_without_csrf_header_fails(csrf_app_client) -> None:
    """POST request without CSRF header should return 403."""
    client, password, config = csrf_app_client
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    response = client.post(
        "/api/v1/domains",
        json={"name": "new.example.com"},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json().get("detail", "")


def test_post_with_wrong_csrf_token_fails(csrf_app_client) -> None:
    """POST request with mismatched CSRF token should return 403."""
    client, password, config = csrf_app_client
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    response = client.post(
        "/api/v1/domains",
        json={"name": "new.example.com"},
        headers={"X-CSRF-Token": "wrong-token"},
    )
    assert response.status_code == 403
    assert "CSRF" in response.json().get("detail", "")


def test_get_without_csrf_succeeds(csrf_app_client) -> None:
    """GET requests should not require CSRF token."""
    client, password, config = csrf_app_client
    client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    response = client.get("/api/v1/domains")
    assert response.status_code == 200


def test_delete_without_csrf_fails(csrf_app_client) -> None:
    """DELETE request without CSRF header should return 403."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    csrf_token = login_resp.cookies.get(config.csrf_cookie_name)
    create_resp = client.post(
        "/api/v1/domains",
        json={"name": "todelete.example.com"},
        headers={"X-CSRF-Token": csrf_token},
    )
    domain_id = create_resp.json()["domain"]["id"]
    client.post(
        f"/api/v1/domains/{domain_id}/archive",
        headers={"X-CSRF-Token": csrf_token},
    )
    response = client.delete(f"/api/v1/domains/{domain_id}")
    assert response.status_code == 403


def test_delete_with_valid_csrf_succeeds(csrf_app_client) -> None:
    """DELETE request with valid CSRF should succeed."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    csrf_token = login_resp.cookies.get(config.csrf_cookie_name)
    create_resp = client.post(
        "/api/v1/domains",
        json={"name": "todelete2.example.com"},
        headers={"X-CSRF-Token": csrf_token},
    )
    domain_id = create_resp.json()["domain"]["id"]
    client.post(
        f"/api/v1/domains/{domain_id}/archive",
        headers={"X-CSRF-Token": csrf_token},
    )
    response = client.delete(
        f"/api/v1/domains/{domain_id}",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 204


def test_api_key_auth_skips_csrf(csrf_app_client) -> None:
    """API key authenticated requests should skip CSRF validation."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    csrf_token = login_resp.cookies.get(config.csrf_cookie_name)
    key_resp = client.post(
        "/api/v1/apikeys",
        json={
            "nickname": "test-key",
            "domain_ids": ["dom_example"],
            "scopes": ["reports:ingest"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert key_resp.status_code == 201
    api_key = key_resp.json()["key"]
    client.cookies.clear()
    ingest_resp = client.post(
        "/api/v1/reports/ingest",
        json={
            "source": "test",
            "reports": [
                {
                    "content_type": "application/xml",
                    "content_encoding": "",
                    "content_transfer_encoding": "base64",
                    "content": "PHRlc3Q+PC90ZXN0Pg==",
                }
            ],
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    assert ingest_resp.status_code in (200, 202)


def test_logout_clears_csrf_cookie(csrf_app_client) -> None:
    """Logout should clear both session and CSRF cookies."""
    client, password, config = csrf_app_client
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": password},
    )
    csrf_token = login_resp.cookies.get(config.csrf_cookie_name)
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_resp.status_code == 200
    me_resp = client.get("/api/v1/auth/me")
    assert me_resp.status_code == 401
