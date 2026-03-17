"""Audit API: GET /api/v1/audit (super-admin only)."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def audit_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, config set."""
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None
    config = Config(
        database_path=temp_db_path,
        log_level="INFO",
        session_secret="test-secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
    )
    app.state.config = config
    yield wrap_client_with_csrf(TestClient(app)), password, config
    app.state.config = None


def test_get_audit_super_admin_200(audit_app_client) -> None:
    """Super-admin GET /api/v1/audit returns 200 and events array."""
    client, password, _ = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.get("/api/v1/audit")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert "available_action_types" in data
    assert isinstance(data["events"], list)
    assert isinstance(data["available_action_types"], list)
    # Login above wrote at least one audit event
    assert len(data["events"]) >= 1
    event = data["events"][0]
    assert "timestamp" in event
    assert "action_type" in event
    assert "outcome" in event
    assert "summary" in event


def test_get_audit_non_super_admin_403(audit_app_client, temp_db_path: str) -> None:
    """Non–super-admin GET /api/v1/audit returns 403."""
    client, password, config = audit_app_client
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_m", "manager1", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager1", "password": "m"})
    r = client.get("/api/v1/audit")
    assert r.status_code == 403


def test_get_audit_unauthorized_401(audit_app_client) -> None:
    """GET /api/v1/audit without session returns 401."""
    client, _, _ = audit_app_client
    r = client.get("/api/v1/audit")
    assert r.status_code == 401


def test_get_audit_filter_by_action_type(audit_app_client) -> None:
    """Filter by action_type returns only matching events."""
    client, password, _ = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.get("/api/v1/audit?action_type=login_success")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 2
    for e in events:
        assert e["action_type"] == "login_success"


def test_get_audit_filter_by_multiple_action_types(audit_app_client, temp_db_path: str) -> None:
    """Filter by action_types returns matching events from multiple action groups."""
    client, password, _config = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            """INSERT INTO audit_log (id, timestamp, actor_type, actor_user_id, actor_api_key_id, action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, 'user', ?, NULL, 'user_created', 'success', NULL, NULL, 'created user demo', NULL)""",
            ("aud_manual", "2026-01-02T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/v1/audit?action_types=login_success,user_created")
    assert r.status_code == 200
    data = r.json()
    assert "login_success" in data["available_action_types"]
    assert "user_created" in data["available_action_types"]
    assert len(data["events"]) >= 2
    for event in data["events"]:
        assert event["action_type"] in {"login_success", "user_created"}


def test_get_audit_filter_by_actor(audit_app_client, temp_db_path: str) -> None:
    """Filter by actor returns only events from that actor."""
    client, password, config = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    conn.close()
    r = client.get(f"/api/v1/audit?actor={admin_id}")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 1
    for e in events:
        assert e["actor_user_id"] == admin_id


def test_get_audit_filter_by_date_range(audit_app_client) -> None:
    """Filter by date range returns only events in range."""
    client, password, _ = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r_all = client.get("/api/v1/audit")
    assert r_all.status_code == 200
    all_events = r_all.json()["events"]
    assert len(all_events) >= 1
    r_future = client.get("/api/v1/audit?from=2099-01-01")
    assert r_future.status_code == 200
    assert len(r_future.json()["events"]) == 0
    r_past = client.get("/api/v1/audit?to=2000-01-01")
    assert r_past.status_code == 200
    assert len(r_past.json()["events"]) == 0


def test_get_audit_combined_filters(audit_app_client, temp_db_path: str) -> None:
    """Combined filters work together."""
    client, password, config = audit_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    conn.close()
    r = client.get(f"/api/v1/audit?action_type=login_success&actor={admin_id}&from=2020-01-01&to=2099-12-31")
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) >= 1
    for e in events:
        assert e["action_type"] == "login_success"
        assert e["actor_user_id"] == admin_id
