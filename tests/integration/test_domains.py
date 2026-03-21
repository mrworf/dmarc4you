"""Domain slice: create (super-admin only), list (scoped), policy."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.policies.domain_policy import can_create_domain
from backend.services import domain_maintenance_service, domain_monitoring_service, domain_service
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def domain_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, config set. Yields (client, admin_password)."""
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


def test_can_create_domain_only_super_admin() -> None:
    assert can_create_domain({"role": "super-admin"}) is True
    assert can_create_domain({"role": "admin"}) is False
    assert can_create_domain({"role": "manager"}) is False


def test_create_domain_as_super_admin_returns_201(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.post("/api/v1/domains", json={"name": "example.com"})
    assert response.status_code in (200, 201)
    data = response.json()
    assert "domain" in data
    assert data["domain"]["name"] == "example.com"
    assert data["domain"]["status"] == "active"
    assert "id" in data["domain"]


def test_list_domains_as_super_admin_returns_all(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post("/api/v1/domains", json={"name": "example.com"})
    response = client.get("/api/v1/domains")
    assert response.status_code == 200
    data = response.json()
    assert "domains" in data
    names = [d["name"] for d in data["domains"]]
    assert "example.com" in names


def test_create_domain_duplicate_name_returns_409(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post("/api/v1/domains", json={"name": "example.com"})
    response = client.post("/api/v1/domains", json={"name": "example.com"})
    assert response.status_code == 409


def test_create_domain_empty_name_returns_400(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.post("/api/v1/domains", json={"name": "   "})
    assert response.status_code == 400


def test_create_domain_as_non_super_admin_returns_403(domain_app_client, temp_db_path: str) -> None:
    client, _ = domain_app_client
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_admin2", "admin2", hash_password("pass"), "admin", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
    response = client.post("/api/v1/domains", json={"name": "example.com"})
    assert response.status_code == 403


def test_archive_domain_as_super_admin_returns_200(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "archive-test.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    arch = client.post(f"/api/v1/domains/{domain_id}/archive")
    assert arch.status_code == 200
    assert arch.json()["domain"]["status"] == "archived"
    assert "archived_at" in arch.json()["domain"]


def test_list_domains_excludes_archived_for_non_super_admin(domain_app_client, temp_db_path: str) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "hidden-when-archived.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
            ("usr_viewer", domain_id, admin_id, "2026-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_viewer", "viewer", hash_password("vp"), "viewer", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    list_before = client.get("/api/v1/domains")
    assert domain_id in [d["id"] for d in list_before.json()["domains"]]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer", "password": "vp"})
    list_after = client.get("/api/v1/domains")
    assert domain_id not in [d["id"] for d in list_after.json()["domains"]]


def test_restore_domain_as_super_admin_returns_200(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "restore-test.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    rest = client.post(f"/api/v1/domains/{domain_id}/restore")
    assert rest.status_code == 200
    assert rest.json()["domain"]["status"] == "active"


def test_archive_domain_as_non_super_admin_returns_403(domain_app_client, temp_db_path: str) -> None:
    client, password = domain_app_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin2", "admin2", hash_password("pass2"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "forbidden-archive.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass2"})
    arch = client.post(f"/api/v1/domains/{domain_id}/archive")
    assert arch.status_code == 403


def test_archive_with_retention_days_sets_retention(domain_app_client) -> None:
    """Archive with body retention_days persists retention_delete_at; list returns retention fields."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "retention-test.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    arch = client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    assert arch.status_code == 200
    data = arch.json()["domain"]
    assert data["status"] == "archived"
    assert data.get("retention_days") == 7
    assert "retention_delete_at" in data
    assert data["retention_delete_at"] is not None
    list_resp = client.get("/api/v1/domains")
    assert list_resp.status_code == 200
    domains = [d for d in list_resp.json()["domains"] if d["id"] == domain_id]
    assert len(domains) == 1
    assert domains[0]["retention_days"] == 7
    assert domains[0]["retention_delete_at"] is not None
    assert domains[0].get("retention_paused") == 0


def test_retention_purge_deletes_expired_archived_domain(domain_app_client, temp_db_path: str) -> None:
    """Run retention purge: archived domain with retention_delete_at in the past is permanently deleted."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "purge-me.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            "UPDATE domains SET retention_delete_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00Z", domain_id),
        )
        conn.commit()
    finally:
        conn.close()
    config = app.state.config
    assert config is not None
    n = domain_service.run_retention_purge(config)
    assert n == 1
    cur = get_connection(temp_db_path).execute("SELECT 1 FROM domains WHERE id = ?", (domain_id,))
    assert cur.fetchone() is None
    list_resp = client.get("/api/v1/domains")
    assert domain_id not in [d["id"] for d in list_resp.json()["domains"]]


def test_pause_retention_200_and_unpause_200(domain_app_client, temp_db_path: str) -> None:
    """Pause retention on archived domain with retention; then unpause. Scheduler must not purge paused domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "pause-unpause.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    pause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/pause", json={"reason": "Testing"})
    assert pause_resp.status_code == 200
    assert pause_resp.json()["domain"].get("retention_paused") == 1
    assert "retention_remaining_seconds" in pause_resp.json()["domain"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT retention_paused, retention_remaining_seconds FROM domains WHERE id = ?",
            (domain_id,),
        )
        row = cur.fetchone()
        assert row is not None and row[0] == 1 and row[1] is not None
    finally:
        conn.close()
    n = domain_service.run_retention_purge(app.state.config)
    assert n == 0
    unpause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/unpause")
    assert unpause_resp.status_code == 200
    assert unpause_resp.json()["domain"].get("retention_paused") == 0
    assert "retention_delete_at" in unpause_resp.json()["domain"]


def test_pause_retention_non_super_admin_403(domain_app_client, temp_db_path: str) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "pause-forbidden.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin2", "admin2", hash_password("p2"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "p2"})
    pause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/pause", json={"reason": "x"})
    assert pause_resp.status_code == 403
    unpause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/unpause")
    assert unpause_resp.status_code == 403


def test_pause_retention_no_retention_400(domain_app_client) -> None:
    """Archive without retention_days; pause returns 400."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "no-retention-pause.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    pause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/pause", json={"reason": "x"})
    assert pause_resp.status_code == 400


def test_unpause_when_not_paused_400(domain_app_client) -> None:
    """Unpause on archived domain that is not paused returns 400."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "unpause-not-paused.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    unpause_resp = client.post(f"/api/v1/domains/{domain_id}/retention/unpause")
    assert unpause_resp.status_code == 400


def test_archive_without_body_unchanged(domain_app_client) -> None:
    """Archive with no body (or empty body) does not set retention; list still returns retention fields as null/0."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "no-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    arch = client.post(f"/api/v1/domains/{domain_id}/archive")
    assert arch.status_code == 200
    assert "retention_days" not in arch.json()["domain"] or arch.json()["domain"].get("retention_days") is None
    list_resp = client.get("/api/v1/domains")
    domains = [d for d in list_resp.json()["domains"] if d["id"] == domain_id]
    assert len(domains) == 1
    assert domains[0].get("retention_days") is None
    assert domains[0].get("retention_delete_at") is None
    assert domains[0].get("retention_paused") == 0


def test_archive_already_archived_returns_400(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "double-archive.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    arch2 = client.post(f"/api/v1/domains/{domain_id}/archive")
    assert arch2.status_code == 400


def test_restore_active_domain_returns_400(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "restore-active.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    rest = client.post(f"/api/v1/domains/{domain_id}/restore")
    assert rest.status_code == 400


def test_restore_nonexistent_domain_returns_404(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    rest = client.post("/api/v1/domains/dom_nonexistent123/restore")
    assert rest.status_code == 404


def test_delete_archived_domain_returns_204_and_removes_data(domain_app_client, temp_db_path: str) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "to-delete.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    del_resp = client.delete(f"/api/v1/domains/{domain_id}")
    assert del_resp.status_code == 204
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT 1 FROM domains WHERE id = ?", (domain_id,))
        assert cur.fetchone() is None
    finally:
        conn.close()
    list_resp = client.get("/api/v1/domains")
    assert domain_id not in [d["id"] for d in list_resp.json()["domains"]]


def test_delete_active_domain_returns_400(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "active-no-delete.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    del_resp = client.delete(f"/api/v1/domains/{domain_id}")
    assert del_resp.status_code == 400


def test_delete_domain_as_non_super_admin_returns_403(domain_app_client, temp_db_path: str) -> None:
    client, password = domain_app_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin2", "admin2", hash_password("pass2"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "forbidden-delete.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass2"})
    del_resp = client.delete(f"/api/v1/domains/{domain_id}")
    assert del_resp.status_code == 403


def test_delete_nonexistent_domain_returns_404(domain_app_client) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    del_resp = client.delete("/api/v1/domains/dom_nonexistent999")
    assert del_resp.status_code == 404


def test_set_retention_on_archived_domain_without_retention(domain_app_client) -> None:
    """Set retention on an archived domain that has no retention configured."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "set-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 30})
    assert set_resp.status_code == 200
    data = set_resp.json()["domain"]
    assert data["retention_days"] == 30
    assert data["retention_delete_at"] is not None
    assert data["retention_paused"] == 0


def test_update_retention_on_archived_domain_with_retention(domain_app_client) -> None:
    """Update retention on an archived domain that already has retention configured."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "update-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 60})
    assert set_resp.status_code == 200
    data = set_resp.json()["domain"]
    assert data["retention_days"] == 60
    assert data["retention_delete_at"] is not None


def test_set_retention_on_paused_domain_updates_remaining(domain_app_client, temp_db_path: str) -> None:
    """Set retention on a paused domain updates retention_remaining_seconds."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "paused-set-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive", json={"retention_days": 7})
    client.post(f"/api/v1/domains/{domain_id}/retention/pause")
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 14})
    assert set_resp.status_code == 200
    data = set_resp.json()["domain"]
    assert data["retention_days"] == 14
    assert data["retention_paused"] == 1
    assert data.get("retention_remaining_seconds") == 14 * 86400
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT retention_remaining_seconds FROM domains WHERE id = ?",
            (domain_id,),
        )
        row = cur.fetchone()
        assert row is not None and row[0] == 14 * 86400
    finally:
        conn.close()


def test_set_retention_non_super_admin_403(domain_app_client, temp_db_path: str) -> None:
    """Non-super-admin cannot set retention."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "set-retention-forbidden.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin2", "admin2", hash_password("p2"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "p2"})
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 30})
    assert set_resp.status_code == 403


def test_set_retention_not_archived_400(domain_app_client) -> None:
    """Cannot set retention on active domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "active-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 30})
    assert set_resp.status_code == 400


def test_set_retention_not_found_404(domain_app_client) -> None:
    """Set retention on nonexistent domain returns 404."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    set_resp = client.post("/api/v1/domains/dom_nonexistent123/retention", json={"retention_days": 30})
    assert set_resp.status_code == 404


def test_set_retention_invalid_days_400(domain_app_client) -> None:
    """Set retention with 0 or negative days returns 400."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "invalid-retention.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    set_resp = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": 0})
    assert set_resp.status_code == 400
    set_resp2 = client.post(f"/api/v1/domains/{domain_id}/retention", json={"retention_days": -5})
    assert set_resp2.status_code == 400


def test_me_returns_domain_ids_for_non_super_admin(domain_app_client, temp_db_path: str) -> None:
    """Non-super-admin has domain_ids from user_domain_assignments (empty until we add assign API)."""
    client, password = domain_app_client
    # Create admin user (non-super-admin) and assign no domains; me should still work with domain_ids []
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_test123", "admin2", "hash", "admin", "2026-01-01T00:00:00Z", "usr_bootstrap"),
        )
        conn.commit()
    finally:
        conn.close()
    # We don't have a session for admin2; login as super-admin and get /me
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["all_domains"] is True
    assert "domain_ids" in data


def test_get_domain_stats_super_admin_any_domain(domain_app_client, temp_db_path: str) -> None:
    """Super-admin can get stats for any domain including archived."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "stats-test.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    stats_resp = client.get(f"/api/v1/domains/{domain_id}/stats")
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["domain_id"] == domain_id
    assert data["aggregate_reports"] == 0
    assert data["forensic_reports"] == 0
    assert data["aggregate_records"] == 0
    client.post(f"/api/v1/domains/{domain_id}/archive")
    stats_resp2 = client.get(f"/api/v1/domains/{domain_id}/stats")
    assert stats_resp2.status_code == 200


def test_get_domain_stats_admin_assigned_domain(domain_app_client, temp_db_path: str) -> None:
    """Admin can get stats for an assigned active domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "stats-assigned.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin_stats", "admin_stats", hash_password("p2"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.execute(
            "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
            ("usr_admin_stats", domain_id, admin_id, "2026-01-01T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin_stats", "password": "p2"})
    stats_resp = client.get(f"/api/v1/domains/{domain_id}/stats")
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["domain_id"] == domain_id


def test_get_domain_stats_admin_unassigned_domain_403(domain_app_client, temp_db_path: str) -> None:
    """Admin cannot get stats for an unassigned domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "stats-unassigned.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin_nostats", "admin_nostats", hash_password("p3"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin_nostats", "password": "p3"})
    stats_resp = client.get(f"/api/v1/domains/{domain_id}/stats")
    assert stats_resp.status_code == 403


def test_get_domain_stats_archived_domain_non_super_admin_403(domain_app_client, temp_db_path: str) -> None:
    """Non-super-admin cannot get stats for an archived domain even if assigned."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "stats-archived.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_admin_arch", "admin_arch", hash_password("p4"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.execute(
            "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
            ("usr_admin_arch", domain_id, admin_id, "2026-01-01T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post(f"/api/v1/domains/{domain_id}/archive")
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin_arch", "password": "p4"})
    stats_resp = client.get(f"/api/v1/domains/{domain_id}/stats")
    assert stats_resp.status_code == 403


def test_get_domain_stats_not_found_404(domain_app_client) -> None:
    """Stats for nonexistent domain returns 404."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    stats_resp = client.get("/api/v1/domains/dom_nonexistent999/stats")
    assert stats_resp.status_code == 404


def test_delete_domain_purges_forensic_reports(domain_app_client, temp_db_path: str) -> None:
    """Deleting archived domain removes forensic_reports for that domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "forensic-purge.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    domain_name = "forensic-purge.com"
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            """INSERT INTO ingest_jobs (id, actor_type, actor_user_id, actor_api_key_id,
               submitted_at, started_at, completed_at, state, last_error, retry_count)
               VALUES (?, ?, ?, NULL, ?, NULL, NULL, ?, NULL, 0)""",
            ("job_forensic_test", "user", admin_id, "2026-01-01T00:00:00Z", "queued"),
        )
        conn.execute(
            """INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content,
               report_type_detected, domain_detected, status, status_reason, started_at, completed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)""",
            ("item_forensic_test", "job_forensic_test", 1, "<test/>", "forensic", domain_name, "accepted"),
        )
        conn.execute(
            """INSERT INTO forensic_reports (id, report_id, domain, source_ip, arrival_time,
               org_name, header_from, envelope_from, envelope_to, spf_result, dkim_result,
               dmarc_result, failure_type, job_item_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("for_test1", "rpt_1", domain_name, "1.2.3.4", "2026-01-01T00:00:00Z",
             "Test Org", "from@forensic-purge.com", "env@forensic-purge.com",
             "to@example.com", "fail", "fail", "fail", "spf", "item_forensic_test",
             "2026-01-01T00:00:00Z"),
        )
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM forensic_reports WHERE domain = ?", (domain_name,))
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
    client.post(f"/api/v1/domains/{domain_id}/archive")
    del_resp = client.delete(f"/api/v1/domains/{domain_id}")
    assert del_resp.status_code == 204
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM forensic_reports WHERE domain = ?", (domain_name,))
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()


def test_delete_domain_purges_api_key_domains(domain_app_client, temp_db_path: str) -> None:
    """Deleting archived domain removes api_key_domains bindings for that domain."""
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/domains", json={"name": "apikey-purge.com"})
    assert r.status_code in (200, 201)
    domain_id = r.json()["domain"]["id"]
    key_resp = client.post("/api/v1/apikeys", json={
        "nickname": "test-key",
        "description": "for purge test",
        "domain_ids": [domain_id],
        "scopes": ["reports:ingest"],
    })
    assert key_resp.status_code == 201
    key_id = key_resp.json()["id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM api_key_domains WHERE domain_id = ?",
            (domain_id,),
        )
        assert cur.fetchone()[0] == 1
    finally:
        conn.close()
    client.post(f"/api/v1/domains/{domain_id}/archive")
    del_resp = client.delete(f"/api/v1/domains/{domain_id}")
    assert del_resp.status_code == 204
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute(
            "SELECT COUNT(*) FROM api_key_domains WHERE domain_id = ?",
            (domain_id,),
        )
        assert cur.fetchone()[0] == 0
        cur2 = conn.execute("SELECT 1 FROM api_keys WHERE id = ?", (key_id,))
        assert cur2.fetchone() is not None, "API key itself should remain"
    finally:
        conn.close()


def test_domain_monitoring_settings_and_detail_flow(domain_app_client, monkeypatch) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    create_response = client.post("/api/v1/domains", json={"name": "monitoring-example.com"})
    assert create_response.status_code in (200, 201)
    domain_id = create_response.json()["domain"]["id"]

    update_response = client.put(
        f"/api/v1/domains/{domain_id}/monitoring",
        json={"enabled": True, "dkim_selectors": ["selector1", "selector2"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["domain"]["monitoring_enabled"] == 1
    assert update_response.json()["dkim_selectors"] == ["selector1", "selector2"]

    def fake_resolve(_config: Config, host: str):
        if host == "_dmarc.monitoring-example.com":
            return (
                ["v=DMARC1; p=reject; rua=mailto:dmarc@monitoring-example.com"],
                600,
                domain_monitoring_service.DNS_RESULT_OK,
                None,
            )
        if host == "monitoring-example.com":
            return (
                ["v=spf1 include:_spf.monitoring-example.com -all"],
                300,
                domain_monitoring_service.DNS_RESULT_OK,
                None,
            )
        return (["v=DKIM1; k=rsa; p=abc123"], 180, domain_monitoring_service.DNS_RESULT_OK, None)

    monkeypatch.setattr(domain_monitoring_service, "_resolve_txt_records", fake_resolve)

    trigger_response = client.post(f"/api/v1/domains/{domain_id}/monitoring/check")
    assert trigger_response.status_code == 202
    assert trigger_response.json()["state"] == "queued"

    assert domain_maintenance_service.run_one_job(app.state.config) is True

    detail_response = client.get(f"/api/v1/domains/{domain_id}/monitoring")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["current_state"]["dmarc"]["status"] == "ok"
    assert detail["current_state"]["spf"]["status"] == "ok"
    assert len(detail["current_state"]["dkim"]) == 2
    assert detail["current_state"]["dmarc"]["details"][0]["label"] == "Policy"
    assert detail["current_state"]["dmarc"]["details"][3]["values"] == ["dmarc@monitoring-example.com"]
    assert detail["current_state"]["spf"]["details"][0]["label"] == "Default handling"
    assert detail["current_state"]["spf"]["details"][2]["label"] == "Referenced services"
    assert detail["current_state"]["spf"]["details"][2]["values"] == ["_spf.monitoring-example.com"]
    assert detail["current_state"]["dkim"][0]["details"][0]["label"] == "Selector"
    assert detail["current_state"]["dkim"][0]["details"][1]["values"] == ["Yes"]
    assert len(detail["history"]) == 1


def test_domain_monitoring_timeline_returns_only_saved_changes(domain_app_client, monkeypatch) -> None:
    client, password = domain_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    create_response = client.post("/api/v1/domains", json={"name": "timeline-example.com"})
    assert create_response.status_code in (200, 201)
    domain_id = create_response.json()["domain"]["id"]
    client.put(
        f"/api/v1/domains/{domain_id}/monitoring",
        json={"enabled": True, "dkim_selectors": ["selector1"]},
    )

    resolvers = [
        lambda _config, host: (
            ["v=DMARC1; p=none"] if host == "_dmarc.timeline-example.com"
            else ["v=spf1 ~all"] if host == "timeline-example.com"
            else ["v=DKIM1; k=rsa; p=abc123"],
            300,
            domain_monitoring_service.DNS_RESULT_OK,
            None,
        ),
        lambda _config, host: (
            ["v=DMARC1; p=none"] if host == "_dmarc.timeline-example.com"
            else ["v=spf1 ~all"] if host == "timeline-example.com"
            else ["v=DKIM1; k=rsa; p=abc123"],
            300,
            domain_monitoring_service.DNS_RESULT_OK,
            None,
        ),
        lambda _config, host: (
            ["v=DMARC1; p=reject"] if host == "_dmarc.timeline-example.com"
            else ["v=spf1 -all"] if host == "timeline-example.com"
            else ["v=DKIM1; k=rsa; p=abc123"],
            300,
            domain_monitoring_service.DNS_RESULT_OK,
            None,
        ),
    ]

    for resolver in resolvers:
        monkeypatch.setattr(domain_monitoring_service, "_resolve_txt_records", resolver)
        trigger_response = client.post(f"/api/v1/domains/{domain_id}/monitoring/check")
        assert trigger_response.status_code == 202
        conn = get_connection(app.state.config.database_path)
        try:
            conn.execute(
                "UPDATE domains SET monitoring_last_triggered_at = NULL WHERE id = ?",
                (domain_id,),
            )
            conn.commit()
        finally:
            conn.close()
        assert domain_maintenance_service.run_one_job(app.state.config) is True

    timeline_response = client.get(f"/api/v1/domains/{domain_id}/monitoring/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.json()
    assert timeline["last_checked_at"] is not None
    assert len(timeline["history"]) == 2
    assert timeline["history"][0]["overall_direction"] in {"improved", "degraded", "neutral"}
    assert timeline["history"][0]["changes"]
