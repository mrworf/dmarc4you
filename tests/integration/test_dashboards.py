"""Dashboard slice: create (owner set), list (owned), get by id (domain access), 403/400."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.services.domain_service import create_domain
from tests.conftest import wrap_client_with_csrf


@pytest.fixture
def dashboard_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, two domains (example.com, other.com), config set."""
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
    conn.close()
    for name in ("example.com", "other.com"):
        status, _ = create_domain(config, name, admin_id, "super-admin")
        assert status == "ok"
    yield wrap_client_with_csrf(TestClient(app)), password, config
    app.state.config = None


def test_post_dashboard_creates_with_owner(dashboard_app_client) -> None:
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post(
        "/api/v1/dashboards",
        json={"name": "My Dashboard", "description": "Test", "domain_ids": [domain_id]},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "My Dashboard"
    assert data["owner_user_id"]
    assert data["domain_ids"] == [domain_id]
    assert "domain_names" in data
    assert "example.com" in data["domain_names"]


def test_get_dashboards_list_only_owned(dashboard_app_client) -> None:
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    r = client.get("/api/v1/dashboards")
    assert r.status_code == 200
    assert len(r.json()["dashboards"]) >= 1
    first = r.json()["dashboards"][0]
    assert set(first.keys()) >= {"id", "name", "description", "owner_user_id", "created_at", "updated_at", "domain_ids"}


def test_get_dashboard_by_id_200_with_domain_ids(dashboard_app_client) -> None:
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.get(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 200
    assert r.json()["domain_ids"] == [domain_id]
    assert r.json()["domain_names"] == ["example.com"]


def test_dashboards_openapi_contract_includes_list_and_create_models() -> None:
    schema = app.openapi()
    schemas = schema["components"]["schemas"]
    assert "DashboardSummary" in schemas
    assert "DashboardsListResponse" in schemas
    list_get = schema["paths"]["/api/v1/dashboards"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    create_post = schema["paths"]["/api/v1/dashboards"]["post"]["responses"]["201"]["content"]["application/json"]["schema"]
    assert list_get["$ref"] == "#/components/schemas/DashboardsListResponse"
    assert create_post["$ref"] == "#/components/schemas/DashboardSummary"


def test_get_dashboard_403_when_user_lacks_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_v", "viewer1", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_x"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "p"})
    r = client.get(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 403


def test_post_dashboard_403_with_disallowed_domain_ids(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer with no domain assignments cannot create dashboard (domain_ids not in allowed set)."""
    client, password, config = dashboard_app_client
    conn = get_connection(temp_db_path)
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
           VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
        ("usr_v2", "viewer2", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_x"),
    )
    conn.commit()
    conn.close()
    cur = get_connection(temp_db_path).execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer2", "password": "p"})
    r = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    assert r.status_code == 403


def test_post_dashboard_400_empty_domain_ids(dashboard_app_client) -> None:
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": []})
    assert r.status_code == 400


def test_post_dashboard_400_empty_name(dashboard_app_client) -> None:
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post("/api/v1/dashboards", json={"name": "  ", "domain_ids": [domain_id]})
    assert r.status_code == 400


def test_list_dashboards_excludes_dormant_for_non_super_admin(dashboard_app_client, temp_db_path: str) -> None:
    """When a dashboard's scope contains an archived domain, non-super-admin owner does not see it in list."""
    client, password, config = dashboard_app_client
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr", "manager1", hash_password("mgr"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager1", "password": "mgr"})
    r = client.post("/api/v1/dashboards", json={"name": "Dormant Soon", "domain_ids": [domain_id]})
    assert r.status_code == 201
    dash_id = r.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(f"/api/v1/domains/{domain_id}/archive")
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager1", "password": "mgr"})
    list_r = client.get("/api/v1/dashboards")
    assert list_r.status_code == 200
    ids = [d["id"] for d in list_r.json()["dashboards"]]
    assert dash_id not in ids


def test_list_dashboards_includes_dormant_for_super_admin(dashboard_app_client) -> None:
    """Super-admin still sees owned dashboards even when scope contains an archived domain."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post("/api/v1/dashboards", json={"name": "Dormant Ok", "domain_ids": [domain_id]})
    assert r.status_code == 201
    dash_id = r.json()["id"]
    client.post(f"/api/v1/domains/{domain_id}/archive")
    list_r = client.get("/api/v1/dashboards")
    assert list_r.status_code == 200
    ids = [d["id"] for d in list_r.json()["dashboards"]]
    assert dash_id in ids


def test_export_dashboard_200_yaml_with_domain_names(dashboard_app_client) -> None:
    """Export as owner returns 200 and YAML with name, description, domains (names)."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "Export Me", "description": "For YAML", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.get(f"/api/v1/dashboards/{dash_id}/export")
    assert r.status_code == 200
    assert "application/x-yaml" in (r.headers.get("content-type") or "")
    import yaml
    data = yaml.safe_load(r.text)
    assert data["name"] == "Export Me"
    assert data["description"] == "For YAML"
    assert data["domains"] == ["example.com"]


def test_export_dashboard_403_when_user_lacks_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    """Export as user without access to dashboard domain returns 403."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_v", "viewer1", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_x"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "p"})
    r = client.get(f"/api/v1/dashboards/{dash_id}/export")
    assert r.status_code == 403


def test_export_dashboard_404_not_found(dashboard_app_client) -> None:
    """Export non-existent dashboard returns 404."""
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.get("/api/v1/dashboards/dash_nonexistent999/export")
    assert r.status_code == 404


def test_import_dashboard_201_valid_yaml_and_remap(dashboard_app_client) -> None:
    """Import with valid YAML and complete domain_remap creates dashboard; owner is current user."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id, name FROM domains ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    domain_by_name = {r[1]: r[0] for r in rows}
    yaml_str = "name: Imported Dashboard\ndescription: From YAML\ndomains:\n  - example.com\n  - other.com\n"
    domain_remap = {name: domain_by_name[name] for name in ["example.com", "other.com"]}
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": yaml_str, "domain_remap": domain_remap},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Imported Dashboard"
    assert data["description"] == "From YAML"
    assert set(data["domain_ids"]) == set(domain_remap.values())
    assert data["owner_user_id"]


def test_import_dashboard_400_missing_remap_key(dashboard_app_client) -> None:
    """Import when a domain name in YAML is missing from domain_remap returns 400."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    cur = get_connection(config.database_path).execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    yaml_str = "name: Partial\ndomains:\n  - example.com\n  - other.com\n"
    domain_remap = {"example.com": domain_id}
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": yaml_str, "domain_remap": domain_remap},
    )
    assert r.status_code == 400


def test_import_dashboard_403_remap_domain_not_allowed(dashboard_app_client, temp_db_path: str) -> None:
    """Import when domain_remap uses a domain_id the user is not allowed returns 403."""
    client, password, config = dashboard_app_client
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id_ex = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    domain_id_other = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_m", "manager1", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_m", domain_id_ex, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    yaml_str = "name: Two Domains\ndomains:\n  - example.com\n  - other.com\n"
    domain_remap = {"example.com": domain_id_ex, "other.com": domain_id_other}
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager1", "password": "m"})
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": yaml_str, "domain_remap": domain_remap},
    )
    assert r.status_code == 403


def test_import_dashboard_400_invalid_yaml_or_empty_fields(dashboard_app_client) -> None:
    """Import with invalid YAML, empty name, or empty domains returns 400."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    cur = get_connection(config.database_path).execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": "not: valid: yaml {{{", "domain_remap": {"example.com": domain_id}},
    )
    assert r.status_code == 400
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": "name: \ndomains:\n  - example.com\n", "domain_remap": {"example.com": domain_id}},
    )
    assert r.status_code == 400
    r = client.post(
        "/api/v1/dashboards/import",
        json={"yaml": "name: No Domains\ndomains: []\n", "domain_remap": {}},
    )
    assert r.status_code == 400


def test_put_dashboard_as_owner(dashboard_app_client) -> None:
    """Owner can update dashboard name, description, and domains."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    other_domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "Original", "description": "Desc", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.put(
        f"/api/v1/dashboards/{dash_id}",
        json={"name": "Updated Name", "description": "New Desc", "domain_ids": [domain_id, other_domain_id]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "New Desc"
    assert set(data["domain_ids"]) == {domain_id, other_domain_id}


def test_put_dashboard_partial_update(dashboard_app_client) -> None:
    """Partial update: only name changes, description and domains remain."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "Original", "description": "Keep Me", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.put(f"/api/v1/dashboards/{dash_id}", json={"name": "New Name Only"})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "New Name Only"
    assert data["description"] == "Keep Me"
    assert data["domain_ids"] == [domain_id]


def test_put_dashboard_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot edit dashboard even if somehow has domain access."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer", "viewer_edit", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    conn = get_connection(temp_db_path)
    conn.execute("UPDATE dashboards SET owner_user_id = 'usr_viewer' WHERE id = ?", (dash_id,))
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_edit", "password": "v"})
    r = client.put(f"/api/v1/dashboards/{dash_id}", json={"name": "Hacked"})
    assert r.status_code == 403


def test_put_dashboard_forbidden_no_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    """Manager without access to dashboard domains cannot edit."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    other_domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_other", "manager_other", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_other", other_domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager_other", "password": "m"})
    r = client.put(f"/api/v1/dashboards/{dash_id}", json={"name": "Hacked"})
    assert r.status_code == 403


def test_put_dashboard_400_empty_name(dashboard_app_client) -> None:
    """Update with empty name returns 400."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.put(f"/api/v1/dashboards/{dash_id}", json={"name": "  "})
    assert r.status_code == 400


def test_put_dashboard_400_empty_domains(dashboard_app_client) -> None:
    """Update with empty domain_ids returns 400."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.put(f"/api/v1/dashboards/{dash_id}", json={"domain_ids": []})
    assert r.status_code == 400


def test_put_dashboard_404_not_found(dashboard_app_client) -> None:
    """Update non-existent dashboard returns 404."""
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.put("/api/v1/dashboards/dash_nonexistent999", json={"name": "New"})
    assert r.status_code == 404


def test_delete_dashboard_as_owner(dashboard_app_client) -> None:
    """Owner can delete their dashboard."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "ToDelete", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.delete(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 204
    r = client.get(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 404


def test_delete_dashboard_as_admin(dashboard_app_client, temp_db_path: str) -> None:
    """Admin can delete another user's dashboard within shared domain scope."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_del", "manager_del", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_del", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager_del", "password": "m"})
    cr = client.post("/api/v1/dashboards", json={"name": "ManagerDash", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.delete(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 204


def test_delete_dashboard_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot delete dashboard."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_del", "viewer_del", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_del", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    conn = get_connection(temp_db_path)
    conn.execute("UPDATE dashboards SET owner_user_id = 'usr_viewer_del' WHERE id = ?", (dash_id,))
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_del", "password": "v"})
    r = client.delete(f"/api/v1/dashboards/{dash_id}")
    assert r.status_code == 403


def test_delete_dashboard_404_not_found(dashboard_app_client) -> None:
    """Delete non-existent dashboard returns 404."""
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.delete("/api/v1/dashboards/dash_nonexistent999")
    assert r.status_code == 404


def test_transfer_ownership_as_super_admin(dashboard_app_client, temp_db_path: str) -> None:
    """Super-admin can transfer dashboard ownership to a manager with domain access."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_transfer", "manager_transfer", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_transfer", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "ToTransfer", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": "usr_mgr_transfer"})
    assert r.status_code == 200
    data = r.json()
    assert data["owner_user_id"] == "usr_mgr_transfer"


def test_transfer_ownership_as_admin(dashboard_app_client, temp_db_path: str) -> None:
    """Admin can transfer dashboard ownership within their domain scope."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_admin2", "admin2", hash_password("a"), "admin", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_target", "manager_target", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_admin2", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_target", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "AdminTransfer", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "admin2", "password": "a"})
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": "usr_mgr_target"})
    assert r.status_code == 200
    assert r.json()["owner_user_id"] == "usr_mgr_target"


def test_transfer_ownership_forbidden_manager(dashboard_app_client, temp_db_path: str) -> None:
    """Manager cannot transfer ownership (not admin/super-admin)."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_no_transfer", "manager_no_transfer", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_no_transfer", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager_no_transfer", "password": "m"})
    cr = client.post("/api/v1/dashboards", json={"name": "ManagerDash", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": admin_id})
    assert r.status_code == 403


def test_transfer_ownership_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot transfer ownership."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_no_transfer", "viewer_no_transfer", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_no_transfer", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    conn = get_connection(temp_db_path)
    conn.execute("UPDATE dashboards SET owner_user_id = 'usr_viewer_no_transfer' WHERE id = ?", (dash_id,))
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_no_transfer", "password": "v"})
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": admin_id})
    assert r.status_code == 403


def test_transfer_ownership_invalid_viewer_target(dashboard_app_client, temp_db_path: str) -> None:
    """Cannot transfer ownership to a viewer."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_target", "viewer_target", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_target", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": "usr_viewer_target"})
    assert r.status_code == 400
    assert "viewer" in r.json()["detail"].lower() or "invalid" in r.json()["detail"].lower()


def test_transfer_ownership_invalid_no_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    """Cannot transfer ownership to user who lacks access to dashboard domains."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    other_domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_wrong_domain", "manager_wrong_domain", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_wrong_domain", other_domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": "usr_mgr_wrong_domain"})
    assert r.status_code == 400


def test_transfer_ownership_user_not_found(dashboard_app_client) -> None:
    """Transfer to non-existent user returns 404."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/owner", json={"user_id": "usr_nonexistent999"})
    assert r.status_code == 404
    assert "user" in r.json()["detail"].lower()


def test_transfer_ownership_dashboard_not_found(dashboard_app_client) -> None:
    """Transfer on non-existent dashboard returns 404."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    conn.close()
    r = client.post("/api/v1/dashboards/dash_nonexistent999/owner", json={"user_id": admin_id})
    assert r.status_code == 404
    assert "dashboard" in r.json()["detail"].lower()


# --- Dashboard Sharing Tests ---


def test_share_dashboard_as_owner(dashboard_app_client, temp_db_path: str) -> None:
    """Owner can share dashboard with a manager who has domain access."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_share", "manager_share", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_share", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "ToShare", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_mgr_share", "access_level": "viewer"})
    assert r.status_code == 201
    data = r.json()
    assert data["dashboard_id"] == dash_id
    assert data["user_id"] == "usr_mgr_share"
    assert data["access_level"] == "viewer"


def test_share_dashboard_as_manager(dashboard_app_client, temp_db_path: str) -> None:
    """Manager with domain access can share dashboard they own."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_owner", "manager_owner", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_target2", "viewer_target2", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_owner", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_target2", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "manager_owner", "password": "m"})
    cr = client.post("/api/v1/dashboards", json={"name": "ManagerDash", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_viewer_target2", "access_level": "viewer"})
    assert r.status_code == 201


def test_share_dashboard_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot share a dashboard."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_share", "viewer_share", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_share", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_share", "password": "v"})
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": admin_id, "access_level": "viewer"})
    assert r.status_code == 403


def test_share_dashboard_invalid_target_no_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    """Cannot share with user who lacks access to dashboard domains."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    other_domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_wrong", "manager_wrong", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_wrong", other_domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_mgr_wrong", "access_level": "viewer"})
    assert r.status_code == 400
    assert "domain" in r.json()["detail"].lower()


def test_share_dashboard_invalid_manager_access_for_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Cannot grant manager access to a viewer-role user."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_mgr", "viewer_mgr", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_mgr", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_viewer_mgr", "access_level": "manager"})
    assert r.status_code == 400
    assert "viewer" in r.json()["detail"].lower() or "access" in r.json()["detail"].lower()


def test_share_dashboard_user_not_found(dashboard_app_client) -> None:
    """Share with non-existent user returns 404."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_nonexistent999", "access_level": "viewer"})
    assert r.status_code == 404
    assert "user" in r.json()["detail"].lower()


def test_share_dashboard_dashboard_not_found(dashboard_app_client) -> None:
    """Share on non-existent dashboard returns 404."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    conn.close()
    r = client.post("/api/v1/dashboards/dash_nonexistent999/share", json={"user_id": admin_id, "access_level": "viewer"})
    assert r.status_code == 404


def test_unshare_dashboard(dashboard_app_client, temp_db_path: str) -> None:
    """Can remove a user's dashboard assignment."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_to_unshare", "to_unshare", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_to_unshare", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_to_unshare", "access_level": "viewer"})
    r = client.delete(f"/api/v1/dashboards/{dash_id}/share/usr_to_unshare")
    assert r.status_code == 204


def test_unshare_dashboard_assignment_not_found(dashboard_app_client) -> None:
    """Unshare non-existent assignment returns 404."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.delete(f"/api/v1/dashboards/{dash_id}/share/usr_nonexistent999")
    assert r.status_code == 404


def test_unshare_dashboard_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot unshare from dashboard."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_unshare", "viewer_unshare", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_mgr_unshare", "manager_unshare", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_unshare", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_mgr_unshare", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_mgr_unshare", "access_level": "viewer"})
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_unshare", "password": "v"})
    r = client.delete(f"/api/v1/dashboards/{dash_id}/share/usr_mgr_unshare")
    assert r.status_code == 403


def test_validate_update_no_impacted_users(dashboard_app_client) -> None:
    """Validate-update with no shared users returns valid=true, empty impacted."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    other_domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.post(f"/api/v1/dashboards/{dash_id}/validate-update", json={"domain_ids": [other_domain_id]})
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is True
    assert data["impacted_users"] == []


def test_validate_update_with_impacted_user(dashboard_app_client, temp_db_path: str) -> None:
    """Validate-update returns impacted user when scope change would remove their access."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id_ex = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'other.com' LIMIT 1")
    domain_id_other = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_impacted", "impacted_user", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_impacted", domain_id_ex, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id_ex]})
    dash_id = cr.json()["id"]
    client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_impacted", "access_level": "viewer"})
    r = client.post(f"/api/v1/dashboards/{dash_id}/validate-update", json={"domain_ids": [domain_id_other]})
    assert r.status_code == 200
    data = r.json()
    assert data["valid"] is False
    assert len(data["impacted_users"]) == 1
    assert data["impacted_users"][0]["user_id"] == "usr_impacted"
    assert data["impacted_users"][0]["username"] == "impacted_user"


def test_validate_update_forbidden_viewer(dashboard_app_client, temp_db_path: str) -> None:
    """Viewer cannot call validate-update."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_viewer_val", "viewer_val", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_viewer_val", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer_val", "password": "v"})
    r = client.post(f"/api/v1/dashboards/{dash_id}/validate-update", json={"domain_ids": [domain_id]})
    assert r.status_code == 403


def test_validate_update_dashboard_not_found(dashboard_app_client) -> None:
    """Validate-update on non-existent dashboard returns 404."""
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post("/api/v1/dashboards/dash_nonexistent999/validate-update", json={"domain_ids": []})
    assert r.status_code == 404


# --- Dashboard List Shares Tests ---


def test_list_dashboard_shares_empty(dashboard_app_client) -> None:
    """List shares on dashboard with no shares returns empty list."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "NoShares", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    r = client.get(f"/api/v1/dashboards/{dash_id}/shares")
    assert r.status_code == 200
    data = r.json()
    assert data["shares"] == []


def test_list_dashboard_shares_with_shares(dashboard_app_client, temp_db_path: str) -> None:
    """List shares returns shared users with access_level and username."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_shared1", "shared_user1", hash_password("m"), "manager", "2026-01-01T00:00:00Z", admin_id),
    )
    conn.execute(
        "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
        ("usr_shared1", domain_id, admin_id, "2026-01-01T00:00:00Z"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "WithShares", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post(f"/api/v1/dashboards/{dash_id}/share", json={"user_id": "usr_shared1", "access_level": "manager"})
    r = client.get(f"/api/v1/dashboards/{dash_id}/shares")
    assert r.status_code == 200
    data = r.json()
    assert len(data["shares"]) == 1
    share = data["shares"][0]
    assert share["user_id"] == "usr_shared1"
    assert share["username"] == "shared_user1"
    assert share["access_level"] == "manager"
    assert "granted_at" in share
    assert "granted_by_user_id" in share


def test_list_dashboard_shares_forbidden_no_domain_access(dashboard_app_client, temp_db_path: str) -> None:
    """List shares returns 403 for user without dashboard domain access."""
    client, password, config = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(temp_db_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
        ("usr_no_access", "no_access_user", hash_password("v"), "viewer", "2026-01-01T00:00:00Z", "usr_x"),
    )
    conn.commit()
    conn.close()
    cr = client.post("/api/v1/dashboards", json={"name": "D1", "domain_ids": [domain_id]})
    dash_id = cr.json()["id"]
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "no_access_user", "password": "v"})
    r = client.get(f"/api/v1/dashboards/{dash_id}/shares")
    assert r.status_code == 403


def test_list_dashboard_shares_not_found(dashboard_app_client) -> None:
    """List shares on non-existent dashboard returns 404."""
    client, password, _ = dashboard_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.get("/api/v1/dashboards/dash_nonexistent999/shares")
    assert r.status_code == 404
