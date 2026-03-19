"""API key CRUD: create (key once), list, delete; admin/super-admin only."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def apikeys_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, two domains."""
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
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    for name in ("example.com", "other.com"):
        conn.execute(
            "INSERT INTO domains (id, name, status, created_at, archived_at, archived_by_user_id, retention_days, retention_delete_at, retention_paused, retention_paused_at, retention_pause_reason, retention_remaining_seconds) VALUES (?, ?, 'active', '2026-01-01T00:00:00Z', NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL)",
            (f"dom_{name.replace('.', '_')}", name),
        )
    conn.commit()
    conn.close()
    yield wrap_client_with_csrf(TestClient(app)), password, config
    app.state.config = None


def test_create_apikey_super_admin_201(apikeys_app_client) -> None:
    """Super-admin can create API key; response includes key once."""
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post(
        "/api/v1/apikeys",
        json={
            "nickname": "test-key",
            "description": "For tests",
            "domain_ids": [domain_id],
            "scopes": ["reports:ingest"],
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data.get("id")
    assert data.get("nickname") == "test-key"
    assert data.get("key")
    assert data["key"].startswith("dmarc_")


def test_list_apikeys_super_admin_200(apikeys_app_client) -> None:
    """Super-admin can list API keys; no raw key in list."""
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    client.post(
        "/api/v1/apikeys",
        json={"nickname": "k1", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    r = client.get("/api/v1/apikeys")
    assert r.status_code == 200
    data = r.json()
    assert "keys" in data
    assert len(data["keys"]) >= 1
    for k in data["keys"]:
        assert "key" not in k
        assert "id" in k
        assert "nickname" in k


def test_delete_apikey_204(apikeys_app_client) -> None:
    """Creator can delete (revoke) API key."""
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post(
        "/api/v1/apikeys",
        json={"nickname": "to-revoke", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    assert cr.status_code == 201
    key_id = cr.json()["id"]
    r = client.delete(f"/api/v1/apikeys/{key_id}")
    assert r.status_code == 204
    list_r = client.get("/api/v1/apikeys")
    ids = [k["id"] for k in list_r.json()["keys"]]
    assert key_id not in ids


def test_create_apikey_non_admin_403(apikeys_app_client, temp_db_path: str) -> None:
    """Manager/viewer cannot create API keys."""
    client, password, config = apikeys_app_client
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_m", "manager1", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_m", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager1", "password": "m"})
    r = client.post(
        "/api/v1/apikeys",
        json={"nickname": "k", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    assert r.status_code == 403


def test_create_apikey_disallowed_domain_403(apikeys_app_client, temp_db_path: str) -> None:
    """Admin cannot create key with domain they are not allowed."""
    client, password, config = apikeys_app_client
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    dom_ex = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    dom_other = cur.fetchone()[0]
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_a", "admin1", hash_password("a"), "admin", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_a", dom_ex, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin1", "password": "a"})
    r = client.post(
        "/api/v1/apikeys",
        json={
            "nickname": "k",
            "domain_ids": [dom_ex, dom_other],
            "scopes": ["reports:ingest"],
        },
    )
    assert r.status_code == 403


def test_delete_apikey_404(apikeys_app_client) -> None:
    """Delete non-existent key returns 404."""
    client, password, _ = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.delete("/api/v1/apikeys/key_nonexistent999")
    assert r.status_code == 404


def test_update_apikey_updates_metadata_and_scopes(apikeys_app_client) -> None:
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    created = client.post(
        "/api/v1/apikeys",
        json={"nickname": "before", "description": "old", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    key_id = created.json()["id"]
    updated = client.put(
        f"/api/v1/apikeys/{key_id}",
        json={"nickname": "after", "description": "new", "scopes": ["reports:ingest"]},
    )
    assert updated.status_code == 200
    data = updated.json()["key"]
    assert data["nickname"] == "after"
    assert data["description"] == "new"
    assert data["domain_ids"] == [domain_id]
    assert data["scopes"] == ["reports:ingest"]


def test_update_apikey_non_creator_admin_forbidden(apikeys_app_client, temp_db_path: str) -> None:
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_admin2", "admin2", hash_password("pass"), "admin", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_admin2", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    created = client.post(
        "/api/v1/apikeys",
        json={"nickname": "before", "description": "", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    key_id = created.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
    updated = client.put(
        f"/api/v1/apikeys/{key_id}",
        json={"nickname": "after", "description": "new", "scopes": ["reports:ingest"]},
    )
    assert updated.status_code == 403


def test_apikey_with_monitor_scope_can_trigger_domain_monitoring(apikeys_app_client) -> None:
    client, password, config = apikeys_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    domain_id = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1").fetchone()[0]
    conn.execute(
        "UPDATE domains SET monitoring_enabled = 1, monitoring_next_check_at = ? WHERE id = ?",
        ("2026-01-01T00:00:00Z", domain_id),
    )
    conn.commit()
    conn.close()

    created = client.post(
        "/api/v1/apikeys",
        json={
            "nickname": "monitor-key",
            "description": "dns monitor trigger",
            "domain_ids": [domain_id],
            "scopes": ["domains:monitor"],
        },
    )
    assert created.status_code == 201
    raw_key = created.json()["key"]

    trigger = client.post(
        f"/api/v1/domains/{domain_id}/monitoring/check",
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert trigger.status_code == 202
    assert trigger.json()["state"] == "queued"
