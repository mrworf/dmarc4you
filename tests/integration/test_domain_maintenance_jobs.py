from fastapi.testclient import TestClient

from backend.app import app
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.config.schema import Config
from backend.storage.sqlite import get_connection, run_migrations
from tests.conftest import wrap_client_with_csrf


def _setup_client(temp_db_path: str):
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
    return wrap_client_with_csrf(TestClient(app)), password


def test_domain_recompute_endpoints_enforce_access_and_expose_job_detail(temp_db_path: str) -> None:
    client, password = _setup_client(temp_db_path)
    try:
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
        create_response = client.post("/api/v1/domains", json={"name": "example.com"})
        assert create_response.status_code in (200, 201)
        domain_id = create_response.json()["domain"]["id"]

        conn = get_connection(temp_db_path)
        try:
            admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
            conn.execute(
                """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
                ("usr_admin2", "admin2", hash_password("pass"), "admin", "2026-01-01T00:00:00Z", admin_id),
            )
            conn.execute(
                """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
                ("usr_viewer", "viewer", hash_password("pass"), "viewer", "2026-01-01T00:00:00Z", admin_id),
            )
            conn.execute(
                """INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at)
                   VALUES (?, ?, ?, ?)""",
                ("usr_admin2", domain_id, admin_id, "2026-01-01T00:00:00Z"),
            )
            conn.commit()
        finally:
            conn.close()

        enqueue_response = client.post(f"/api/v1/domains/{domain_id}/recompute")
        assert enqueue_response.status_code == 200
        job = enqueue_response.json()["job"]
        assert job["domain_id"] == domain_id
        assert job["state"] == "queued"

        conflict_response = client.post(f"/api/v1/domains/{domain_id}/recompute")
        assert conflict_response.status_code == 409

        list_response = client.get(f"/api/v1/domains/{domain_id}/maintenance-jobs")
        assert list_response.status_code == 200
        assert list_response.json()["jobs"][0]["job_id"] == job["job_id"]

        detail_response = client.get(f"/api/v1/domain-maintenance-jobs/{job['job_id']}")
        assert detail_response.status_code == 200
        assert detail_response.json()["job"]["job_id"] == job["job_id"]

        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login", json={"username": "viewer", "password": "pass"})
        forbidden_response = client.post(f"/api/v1/domains/{domain_id}/recompute")
        assert forbidden_response.status_code == 403
        forbidden_detail = client.get(f"/api/v1/domain-maintenance-jobs/{job['job_id']}")
        assert forbidden_detail.status_code == 403

        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login", json={"username": "admin2", "password": "pass"})
        admin_list = client.get(f"/api/v1/domains/{domain_id}/maintenance-jobs")
        assert admin_list.status_code == 200
        assert admin_list.json()["jobs"][0]["job_id"] == job["job_id"]
    finally:
        app.state.config = None
