"""Tests for the frontend migration platform slice."""

from fastapi.testclient import TestClient

from backend.app import app
from backend.config import load_config
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations
from backend.auth.bootstrap import ensure_bootstrap_admin
from tests.conftest import wrap_client_with_csrf


def _make_client(temp_db_path: str, **config_overrides) -> tuple[TestClient, str]:
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None
    app.state.config = Config(
        database_path=temp_db_path,
        log_level="INFO",
        session_secret="test-secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
        **config_overrides,
    )
    return wrap_client_with_csrf(TestClient(app)), password


def test_openapi_exposes_auth_domain_and_health_contracts(temp_db_path: str) -> None:
    client, _ = _make_client(temp_db_path)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    schemas = data["components"]["schemas"]
    assert "AuthLoginResponse" in schemas
    assert "AuthMeResponse" in schemas
    assert "DomainsListResponse" in schemas
    assert "ReadinessResponse" in schemas


def test_auth_errors_use_standardized_envelope(temp_db_path: str) -> None:
    client, _ = _make_client(temp_db_path)
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Invalid credentials"
    assert data["error"]["code"] == "invalid_credentials"
    assert data["error"]["message"] == "Invalid credentials"


def test_auth_cookie_policy_comes_from_config(temp_db_path: str) -> None:
    client, password = _make_client(
        temp_db_path,
        session_cookie_secure=True,
        session_cookie_same_site="none",
        csrf_cookie_same_site="lax",
    )
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    assert response.status_code == 200
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("samesite=none" in header.lower() for header in set_cookie_headers)
    assert any("secure" in header.lower() for header in set_cookie_headers)


def test_readiness_endpoint_reports_database_status(temp_db_path: str) -> None:
    client, _ = _make_client(temp_db_path)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "api"
    assert data["checks"] == [{"name": "database", "status": "ok"}]


def test_load_config_parses_split_origin_settings(monkeypatch) -> None:
    monkeypatch.setenv("DMARC_FRONTEND_PUBLIC_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("DMARC_CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    monkeypatch.setenv("DMARC_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("DMARC_SERVER_PORT", "8001")
    monkeypatch.setenv("DMARC_SESSION_COOKIE_SECURE", "true")
    monkeypatch.setenv("DMARC_SESSION_COOKIE_SAME_SITE", "none")
    monkeypatch.setenv("DMARC_CSRF_COOKIE_SAME_SITE", "lax")
    config = load_config(config_path="/tmp/does-not-exist.yaml")
    assert config.frontend_public_origin == "http://localhost:3000"
    assert config.server_host == "127.0.0.1"
    assert config.server_port == 8001
    assert config.session_cookie_secure is True
    assert config.session_cookie_same_site == "none"
    assert config.csrf_cookie_same_site == "lax"
    assert "http://localhost:3000" in config.cors_allowed_origins


def test_load_config_defaults_server_bind_settings() -> None:
    config = load_config(config_path="/tmp/does-not-exist.yaml")
    assert config.server_host == "0.0.0.0"
    assert config.server_port == 8000
