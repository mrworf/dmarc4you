"""User management API tests: CRUD, RBAC, domain assignment."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.policies.user_policy import (
    can_manage_users,
    can_create_user_with_role,
    can_update_user,
    can_reset_password,
    can_assign_domain,
    can_delete_user,
)
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def user_app_client(temp_db_path: str):
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


def _create_test_user(temp_db_path: str, user_id: str, username: str, role: str, password: str = "pass"):
    """Helper to insert a test user directly."""
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, '2026-01-01T00:00:00Z', 'usr_bootstrap', NULL, NULL)""",
            (user_id, username, hash_password(password), role),
        )
        conn.commit()
    finally:
        conn.close()


def _create_test_domain(temp_db_path: str, domain_id: str, name: str):
    """Helper to insert a test domain directly."""
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO domains (id, name, status, created_at)
               VALUES (?, ?, 'active', '2026-01-01T00:00:00Z')""",
            (domain_id, name),
        )
        conn.commit()
    finally:
        conn.close()


def _assign_domain(temp_db_path: str, user_id: str, domain_id: str):
    """Helper to assign domain to user directly."""
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at)
               VALUES (?, ?, 'usr_bootstrap', '2026-01-01T00:00:00Z')""",
            (user_id, domain_id),
        )
        conn.commit()
    finally:
        conn.close()


def _create_dashboard(temp_db_path: str, dash_id: str, name: str, owner_user_id: str, domain_ids: list[str]):
    """Helper to create a dashboard with domain scope."""
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO dashboards (id, name, description, owner_user_id, created_by_user_id, created_at, updated_at, is_dormant, dormant_reason)
               VALUES (?, ?, '', ?, ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 0, NULL)""",
            (dash_id, name, owner_user_id, owner_user_id),
        )
        for domain_id in domain_ids:
            conn.execute(
                "INSERT INTO dashboard_domain_scope (dashboard_id, domain_id) VALUES (?, ?)",
                (dash_id, domain_id),
            )
        conn.commit()
    finally:
        conn.close()


def _assign_dashboard_access(temp_db_path: str, dash_id: str, user_id: str, access_level: str):
    """Helper to assign dashboard access to user."""
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO dashboard_user_access (dashboard_id, user_id, access_level, granted_by_user_id, granted_at)
               VALUES (?, ?, ?, 'usr_bootstrap', '2026-01-01T00:00:00Z')""",
            (dash_id, user_id, access_level),
        )
        conn.commit()
    finally:
        conn.close()


class TestUserPolicy:
    def test_can_manage_users_super_admin(self):
        assert can_manage_users({"role": "super-admin"}) is True

    def test_can_manage_users_admin(self):
        assert can_manage_users({"role": "admin"}) is True

    def test_can_manage_users_manager(self):
        assert can_manage_users({"role": "manager"}) is False

    def test_can_manage_users_viewer(self):
        assert can_manage_users({"role": "viewer"}) is False

    def test_super_admin_can_create_any_role(self):
        actor = {"role": "super-admin"}
        assert can_create_user_with_role(actor, "super-admin") is True
        assert can_create_user_with_role(actor, "admin") is True
        assert can_create_user_with_role(actor, "manager") is True
        assert can_create_user_with_role(actor, "viewer") is True

    def test_admin_cannot_create_super_admin(self):
        actor = {"role": "admin"}
        assert can_create_user_with_role(actor, "super-admin") is False
        assert can_create_user_with_role(actor, "admin") is True
        assert can_create_user_with_role(actor, "manager") is True
        assert can_create_user_with_role(actor, "viewer") is True

    def test_cannot_self_edit(self):
        actor = {"id": "usr_1", "role": "super-admin"}
        target = {"id": "usr_1", "role": "super-admin"}
        allowed, reason = can_update_user(actor, target)
        assert allowed is False
        assert reason == "cannot_self_edit"

    def test_admin_cannot_modify_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_update_user(actor, target)
        assert allowed is False
        assert reason == "cannot_modify_admin"

    def test_admin_cannot_modify_super_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "super-admin"}
        allowed, reason = can_update_user(actor, target)
        assert allowed is False
        assert reason == "cannot_modify_admin"

    def test_admin_cannot_promote_to_super_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "viewer"}
        allowed, reason = can_update_user(actor, target, new_role="super-admin")
        assert allowed is False
        assert reason == "cannot_promote_to_super_admin"

    def test_super_admin_can_update_anyone(self):
        actor = {"id": "usr_1", "role": "super-admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_update_user(actor, target, new_role="viewer")
        assert allowed is True

    def test_cannot_self_reset_password(self):
        actor = {"id": "usr_1", "role": "super-admin"}
        target = {"id": "usr_1", "role": "super-admin"}
        allowed, reason = can_reset_password(actor, target)
        assert allowed is False
        assert reason == "cannot_self_reset"

    def test_admin_cannot_reset_admin_password(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_reset_password(actor, target)
        assert allowed is False
        assert reason == "cannot_reset_admin"

    def test_admin_cannot_assign_to_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_assign_domain(actor, target, {"dom_1"}, "dom_1")
        assert allowed is False
        assert reason == "cannot_assign_to_admin"

    def test_admin_cannot_assign_domain_outside_scope(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "viewer"}
        allowed, reason = can_assign_domain(actor, target, {"dom_1"}, "dom_2")
        assert allowed is False
        assert reason == "domain_not_in_scope"

    def test_cannot_self_delete(self):
        actor = {"id": "usr_1", "role": "super-admin"}
        target = {"id": "usr_1", "role": "super-admin"}
        allowed, reason = can_delete_user(actor, target)
        assert allowed is False
        assert reason == "cannot_self_delete"

    def test_super_admin_can_delete_anyone(self):
        actor = {"id": "usr_1", "role": "super-admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_delete_user(actor, target)
        assert allowed is True

    def test_admin_cannot_delete_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "admin"}
        allowed, reason = can_delete_user(actor, target)
        assert allowed is False
        assert reason == "cannot_delete_admin"

    def test_admin_cannot_delete_super_admin(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "super-admin"}
        allowed, reason = can_delete_user(actor, target)
        assert allowed is False
        assert reason == "cannot_delete_admin"

    def test_admin_can_delete_viewer(self):
        actor = {"id": "usr_1", "role": "admin"}
        target = {"id": "usr_2", "role": "viewer"}
        allowed, reason = can_delete_user(actor, target)
        assert allowed is True


class TestListUsers:
    def test_list_users_as_super_admin_returns_all(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_viewer1", "viewer1", "viewer")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.get("/api/v1/users")
        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()["users"]]
        assert "admin" in usernames
        assert "viewer1" in usernames
        assert "admin2" in usernames
        admin_entry = next(user for user in response.json()["users"] if user["username"] == "admin")
        assert admin_entry["must_change_password"] is True

    def test_list_users_as_admin_returns_domain_scoped(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_domain(temp_db_path, "dom_b", "domain-b.com")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_viewer_a", "viewer_a", "viewer")
        _create_test_user(temp_db_path, "usr_viewer_b", "viewer_b", "viewer")
        _assign_domain(temp_db_path, "usr_admin2", "dom_a")
        _assign_domain(temp_db_path, "usr_viewer_a", "dom_a")
        _assign_domain(temp_db_path, "usr_viewer_b", "dom_b")

        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.get("/api/v1/users")
        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()["users"]]
        assert "admin2" in usernames
        assert "viewer_a" in usernames
        assert "viewer_b" not in usernames

    def test_list_users_as_viewer_returns_403(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "pass"})
        response = client.get("/api/v1/users")
        assert response.status_code == 403


class TestCreateUser:
    def test_super_admin_creates_admin(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users", json={"username": "new_admin", "role": "admin"})
        assert response.status_code == 201
        data = response.json()
        assert data["user"]["username"] == "new_admin"
        assert data["user"]["role"] == "admin"
        assert data["user"]["must_change_password"] is True
        assert "password" in data
        assert len(data["password"]) > 10

        login_response = client.post("/api/v1/auth/login", json={"username": "new_admin", "password": data["password"]})
        assert login_response.status_code == 200
        assert login_response.json()["password_change_required"] is True

    def test_super_admin_creates_super_admin(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users", json={"username": "super2", "role": "super-admin"})
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "super-admin"

    def test_admin_cannot_create_super_admin(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users", json={"username": "super3", "role": "super-admin"})
        assert response.status_code == 403

    def test_admin_creates_viewer(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users", json={"username": "viewer_new", "role": "viewer"})
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "viewer"

    def test_create_duplicate_username_returns_409(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.post("/api/v1/users", json={"username": "dup_user", "role": "viewer"})
        response = client.post("/api/v1/users", json={"username": "dup_user", "role": "viewer"})
        assert response.status_code == 409

    def test_create_empty_username_returns_400(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users", json={"username": "", "role": "viewer"})
        assert response.status_code == 400

    def test_create_invalid_role_returns_400(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users", json={"username": "test", "role": "invalid"})
        assert response.status_code == 400

    def test_create_user_with_optional_profile_fields(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post(
            "/api/v1/users",
            json={"username": "profiled", "role": "viewer", "full_name": "Profile User", "email": "profile@example.com"},
        )
        assert response.status_code == 201
        data = response.json()["user"]
        assert data["full_name"] == "Profile User"
        assert data["email"] == "profile@example.com"


class TestUpdateUser:
    def test_super_admin_updates_username(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put("/api/v1/users/usr_target", json={"username": "new_name"})
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "new_name"

    def test_super_admin_updates_role(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put("/api/v1/users/usr_target", json={"role": "manager"})
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "manager"

    def test_admin_cannot_update_own_username(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.put("/api/v1/users/usr_admin2", json={"username": "new_admin2"})
        assert response.status_code == 403

    def test_admin_can_update_viewer_username(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.put("/api/v1/users/usr_viewer", json={"username": "viewer_renamed"})
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "viewer_renamed"

    def test_admin_cannot_change_admin_role(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_admin3", "admin3", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.put("/api/v1/users/usr_admin3", json={"role": "viewer"})
        assert response.status_code == 403

    def test_update_nonexistent_user_returns_404(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put("/api/v1/users/usr_nonexistent", json={"username": "new"})
        assert response.status_code == 404

    def test_update_duplicate_username_returns_409(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_a", "user_a", "viewer")
        _create_test_user(temp_db_path, "usr_b", "user_b", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put("/api/v1/users/usr_a", json={"username": "user_b"})
        assert response.status_code == 409

    def test_super_admin_updates_optional_profile_fields(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put(
            "/api/v1/users/usr_target",
            json={"full_name": "Target User", "email": "target@example.com"},
        )
        assert response.status_code == 200
        data = response.json()["user"]
        assert data["full_name"] == "Target User"
        assert data["email"] == "target@example.com"

    def test_super_admin_can_clear_optional_profile_fields(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        conn = get_connection(temp_db_path)
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, full_name, email, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, '2026-01-01T00:00:00Z', 'usr_bootstrap', NULL, NULL)""",
            ("usr_profiled", "profiled", hash_password("pass"), "viewer", "Profiled User", "profiled@example.com"),
        )
        conn.commit()
        conn.close()
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.put("/api/v1/users/usr_profiled", json={"full_name": "", "email": ""})
        assert response.status_code == 200
        data = response.json()["user"]
        assert data["full_name"] is None
        assert data["email"] is None


class TestResetPassword:
    def test_reset_password_returns_new_password(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users/usr_target/reset-password")
        assert response.status_code == 200
        new_password = response.json()["password"]
        assert len(new_password) > 10
        conn = get_connection(temp_db_path)
        try:
            row = conn.execute(
                "SELECT must_change_password FROM users WHERE id = ?",
                ("usr_target",),
            ).fetchone()
            assert row is not None
            assert row[0] == 1
        finally:
            conn.close()

    def test_reset_password_old_password_fails(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer", password="oldpass")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        reset_resp = client.post("/api/v1/users/usr_target/reset-password")
        new_password = reset_resp.json()["password"]
        client.post("/api/v1/auth/logout")
        old_login = client.post("/api/v1/auth/login", json={"username": "target_user", "password": "oldpass"})
        assert old_login.status_code == 401
        new_login = client.post("/api/v1/auth/login", json={"username": "target_user", "password": new_password})
        assert new_login.status_code == 200
        assert new_login.json()["password_change_required"] is True

    def test_reset_password_invalidates_existing_target_sessions(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer", password="oldpass")

        target_client = wrap_client_with_csrf(TestClient(app))
        target_login = target_client.post("/api/v1/auth/login", json={"username": "target_user", "password": "oldpass"})
        assert target_login.status_code == 200

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        reset_resp = client.post("/api/v1/users/usr_target/reset-password")
        assert reset_resp.status_code == 200

        me_response = target_client.get("/api/v1/auth/me")
        assert me_response.status_code == 401

    def test_admin_cannot_reset_admin_password(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_admin3", "admin3", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users/usr_admin3/reset-password")
        assert response.status_code == 403

    def test_reset_nonexistent_user_returns_404(self, user_app_client):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users/usr_nonexistent/reset-password")
        assert response.status_code == 404


class TestDomainAssignment:
    def test_super_admin_assigns_domain(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_test", "test.com")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users/usr_viewer/domains", json={"domain_ids": ["dom_test"]})
        assert response.status_code == 200
        assert "dom_test" in response.json()["user"]["domain_ids"]

    def test_admin_assigns_domain_in_scope(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        _assign_domain(temp_db_path, "usr_admin2", "dom_a")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users/usr_viewer/domains", json={"domain_ids": ["dom_a"]})
        assert response.status_code == 200
        assert "dom_a" in response.json()["user"]["domain_ids"]

    def test_admin_cannot_assign_domain_outside_scope(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_domain(temp_db_path, "dom_b", "domain-b.com")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        _assign_domain(temp_db_path, "usr_admin2", "dom_a")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users/usr_viewer/domains", json={"domain_ids": ["dom_b"]})
        assert response.status_code == 403

    def test_admin_cannot_assign_domain_to_admin(self, user_app_client, temp_db_path: str):
        client, _ = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_admin3", "admin3", "admin")
        _assign_domain(temp_db_path, "usr_admin2", "dom_a")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.post("/api/v1/users/usr_admin3/domains", json={"domain_ids": ["dom_a"]})
        assert response.status_code == 403

    def test_assign_invalid_domain_returns_400(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.post("/api/v1/users/usr_viewer/domains", json={"domain_ids": ["dom_nonexistent"]})
        assert response.status_code == 400

    def test_remove_domain_assignment(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_test", "test.com")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        _assign_domain(temp_db_path, "usr_viewer", "dom_test")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_viewer/domains/dom_test")
        assert response.status_code == 200
        assert "dom_test" not in response.json()["user"]["domain_ids"]


class TestAuditEvents:
    def test_user_created_audit(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.post("/api/v1/users", json={"username": "audited_user", "role": "viewer"})
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT action_type, summary FROM audit_log WHERE action_type = 'user_created'")
            row = cur.fetchone()
            assert row is not None
            assert "audited_user" in row[1]
        finally:
            conn.close()

    def test_user_updated_audit(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.put("/api/v1/users/usr_target", json={"username": "renamed_user"})
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT action_type, summary FROM audit_log WHERE action_type = 'user_updated'")
            row = cur.fetchone()
            assert row is not None
            assert "target_user" in row[1] and "renamed_user" in row[1]
        finally:
            conn.close()

    def test_password_reset_audit(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.post("/api/v1/users/usr_target/reset-password")
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT action_type, summary FROM audit_log WHERE action_type = 'password_reset'")
            row = cur.fetchone()
            assert row is not None
            assert "usr_target" in row[1]
        finally:
            conn.close()

    def test_domain_assigned_audit(self, user_app_client, temp_db_path: str):
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_test", "test.com")
        _create_test_user(temp_db_path, "usr_viewer", "viewer1", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.post("/api/v1/users/usr_viewer/domains", json={"domain_ids": ["dom_test"]})
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT action_type, summary FROM audit_log WHERE action_type = 'domain_assigned'")
            row = cur.fetchone()
            assert row is not None
            assert "dom_test" in row[1]
        finally:
            conn.close()


class TestDeleteUser:
    def test_delete_user_without_dashboards(self, user_app_client, temp_db_path: str):
        """Delete user without dashboards returns 204."""
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_target")
        assert response.status_code == 204
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT disabled_at FROM users WHERE id = 'usr_target'")
            row = cur.fetchone()
            assert row is not None
            assert row[0] is not None
        finally:
            conn.close()

    def test_deleted_user_cannot_login(self, user_app_client, temp_db_path: str):
        """Deleted user cannot log in."""
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer", password="mypass")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.delete("/api/v1/users/usr_target")
        client.post("/api/v1/auth/logout")
        login_response = client.post("/api/v1/auth/login", json={"username": "target_user", "password": "mypass"})
        assert login_response.status_code == 401

    def test_cannot_delete_self(self, user_app_client):
        """Cannot delete yourself returns 400."""
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        conn = get_connection(user_app_client[0].app.state.config.database_path)
        try:
            cur = conn.execute("SELECT id FROM users WHERE username = 'admin'")
            admin_id = cur.fetchone()[0]
        finally:
            conn.close()
        response = client.delete(f"/api/v1/users/{admin_id}")
        assert response.status_code == 400
        assert "Cannot delete yourself" in response.json()["detail"]

    def test_admin_cannot_delete_admin(self, user_app_client, temp_db_path: str):
        """Admin cannot delete another admin returns 403."""
        client, _ = user_app_client
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _create_test_user(temp_db_path, "usr_admin3", "admin3", "admin")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        response = client.delete("/api/v1/users/usr_admin3")
        assert response.status_code == 403

    def test_delete_nonexistent_user_returns_404(self, user_app_client):
        """Delete nonexistent user returns 404."""
        client, password = user_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_nonexistent")
        assert response.status_code == 404

    def test_delete_owner_transfers_to_manager(self, user_app_client, temp_db_path: str):
        """Deleting dashboard owner transfers ownership to assigned manager."""
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_owner", "owner_user", "manager")
        _create_test_user(temp_db_path, "usr_manager", "manager_user", "manager")
        _assign_domain(temp_db_path, "usr_owner", "dom_a")
        _assign_domain(temp_db_path, "usr_manager", "dom_a")
        _create_dashboard(temp_db_path, "dash_1", "Test Dashboard", "usr_owner", ["dom_a"])
        _assign_dashboard_access(temp_db_path, "dash_1", "usr_manager", "manager")

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_owner")
        assert response.status_code == 204

        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT owner_user_id FROM dashboards WHERE id = 'dash_1'")
            new_owner = cur.fetchone()[0]
            assert new_owner == "usr_manager"
        finally:
            conn.close()

    def test_delete_owner_transfers_to_admin_when_no_manager(self, user_app_client, temp_db_path: str):
        """Deleting dashboard owner transfers to admin when no manager available."""
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_owner", "owner_user", "manager")
        _create_test_user(temp_db_path, "usr_admin2", "admin2", "admin")
        _assign_domain(temp_db_path, "usr_owner", "dom_a")
        _assign_domain(temp_db_path, "usr_admin2", "dom_a")
        _create_dashboard(temp_db_path, "dash_1", "Test Dashboard", "usr_owner", ["dom_a"])

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_owner")
        assert response.status_code == 204

        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT owner_user_id FROM dashboards WHERE id = 'dash_1'")
            new_owner = cur.fetchone()[0]
            assert new_owner == "usr_admin2"
        finally:
            conn.close()

    def test_delete_owner_transfers_to_super_admin_as_fallback(self, user_app_client, temp_db_path: str):
        """Deleting dashboard owner transfers to super-admin when no manager or admin available."""
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_owner", "owner_user", "manager")
        _assign_domain(temp_db_path, "usr_owner", "dom_a")
        _create_dashboard(temp_db_path, "dash_1", "Test Dashboard", "usr_owner", ["dom_a"])

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_owner")
        assert response.status_code == 204

        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT owner_user_id FROM dashboards WHERE id = 'dash_1'")
            new_owner = cur.fetchone()[0]
            cur2 = conn.execute("SELECT id FROM users WHERE username = 'admin'")
            bootstrap_admin_id = cur2.fetchone()[0]
            assert new_owner == bootstrap_admin_id
        finally:
            conn.close()

    def test_delete_user_removes_dashboard_access(self, user_app_client, temp_db_path: str):
        """Deleting user removes their dashboard_user_access entries."""
        client, password = user_app_client
        _create_test_domain(temp_db_path, "dom_a", "domain-a.com")
        _create_test_user(temp_db_path, "usr_viewer", "viewer_user", "viewer")
        _assign_domain(temp_db_path, "usr_viewer", "dom_a")
        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT id FROM users WHERE username = 'admin'")
            admin_id = cur.fetchone()[0]
        finally:
            conn.close()
        _create_dashboard(temp_db_path, "dash_1", "Test Dashboard", admin_id, ["dom_a"])
        _assign_dashboard_access(temp_db_path, "dash_1", "usr_viewer", "viewer")

        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        response = client.delete("/api/v1/users/usr_viewer")
        assert response.status_code == 204

        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT 1 FROM dashboard_user_access WHERE user_id = 'usr_viewer'")
            assert cur.fetchone() is None
        finally:
            conn.close()

    def test_delete_user_audit_event(self, user_app_client, temp_db_path: str):
        """Deleting user creates audit event."""
        client, password = user_app_client
        _create_test_user(temp_db_path, "usr_target", "target_user", "viewer")
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        client.delete("/api/v1/users/usr_target")

        conn = get_connection(temp_db_path)
        try:
            cur = conn.execute("SELECT action_type, summary FROM audit_log WHERE action_type = 'user_deleted'")
            row = cur.fetchone()
            assert row is not None
            assert "target_user" in row[1]
        finally:
            conn.close()
