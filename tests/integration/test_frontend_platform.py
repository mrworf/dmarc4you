"""Tests for the frontend migration platform slice."""

import anyio
from pathlib import Path
from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request
import yaml

from backend.app import app
from backend.api.errors import http_exception_handler
from backend.api.v1.handlers.auth import LoginBody, auth_login
from backend.config import load_config
from backend.config.schema import Config
from backend.services.health_service import readiness_status
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
    _make_client(temp_db_path)
    data = app.openapi()
    schemas = data["components"]["schemas"]
    assert "AuthLoginResponse" in schemas
    assert "AuthMeResponse" in schemas
    assert "DomainsListResponse" in schemas
    assert "ReadinessResponse" in schemas


def _build_request() -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_auth_errors_use_standardized_envelope(monkeypatch, temp_db_path: str) -> None:
    monkeypatch.setattr("backend.api.v1.handlers.auth.login", lambda *args, **kwargs: (None, None, None))
    _make_client(temp_db_path)
    request = _build_request()
    response = Response()

    try:
        auth_login(request, response, LoginBody(username="admin", password="wrong"), app.state.config)
    except Exception as exc:
        handled = anyio.run(http_exception_handler, request, exc)
    else:
        raise AssertionError("Expected auth_login to raise for invalid credentials")

    assert handled.status_code == 401
    data = handled.body.decode("utf-8")
    import json
    data = json.loads(data)
    assert data["detail"] == "Invalid credentials"
    assert data["error"]["code"] == "invalid_credentials"
    assert data["error"]["message"] == "Invalid credentials"


def test_auth_cookie_policy_comes_from_config(monkeypatch, temp_db_path: str) -> None:
    monkeypatch.setattr(
        "backend.api.v1.handlers.auth.login",
        lambda *args, **kwargs: (
            {
                "id": "usr_test",
                "username": "admin",
                "role": "super-admin",
                "full_name": None,
                "email": None,
            },
            "session_test",
            None,
        ),
    )
    _make_client(
        temp_db_path,
        session_cookie_secure=True,
        session_cookie_same_site="none",
        csrf_cookie_same_site="lax",
    )
    request = _build_request()
    response = Response()

    payload = auth_login(request, response, LoginBody(username="admin", password="ignored"), app.state.config)
    assert payload["user"]["id"] == "usr_test"
    set_cookie_headers = response.headers.getlist("set-cookie")
    assert any("samesite=none" in header.lower() for header in set_cookie_headers)
    assert any("secure" in header.lower() for header in set_cookie_headers)


def test_readiness_endpoint_reports_database_status(temp_db_path: str) -> None:
    _make_client(temp_db_path)
    data = readiness_status(app.state.config)
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


def test_load_config_allows_env_to_override_file_endpoint_settings(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "database": {"path": str(tmp_path / "test.db")},
                "log": {"level": "INFO"},
                "auth": {"session_secret": "file-secret"},
                "server": {"host": "0.0.0.0", "port": 8000},
                "frontend": {"public_origin": "http://file-frontend:3000"},
                "api": {"public_url": "http://file-api:8000"},
                "cors": {"allowed_origins": ["http://file-frontend:3000"]},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DMARC_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("DMARC_SERVER_PORT", "8111")
    monkeypatch.setenv("DMARC_FRONTEND_PUBLIC_ORIGIN", "http://127.0.0.1:3111")
    monkeypatch.setenv("DMARC_API_PUBLIC_URL", "http://127.0.0.1:8111")
    monkeypatch.setenv("DMARC_CORS_ALLOWED_ORIGINS", "http://127.0.0.1:3111")

    config = load_config(config_path=config_path)

    assert config.server_host == "127.0.0.1"
    assert config.server_port == 8111
    assert config.frontend_public_origin == "http://127.0.0.1:3111"
    assert config.api_public_url == "http://127.0.0.1:8111"
    assert config.cors_allowed_origins == ("http://127.0.0.1:3111",)
