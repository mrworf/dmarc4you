"""Search slice: GET /reports/aggregate and POST /search with domain scoping, filters, pagination."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.services.domain_service import create_domain
from backend.jobs.runner import run_one_job
from tests.conftest import wrap_client_with_csrf

MINIMAL_AGGREGATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Example Org</org_name>
    <report_id>r1.example.com-20260101</report_id>
    <date_range>
      <begin>1735689600</begin>
      <end>1735776000</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
  </policy_published>
</feedback>
"""

AGGREGATE_XML_WITH_RECORDS = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Test Org</org_name>
    <report_id>r2.example.com-records</report_id>
    <date_range>
      <begin>1735689600</begin>
      <end>1735776000</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <adkim>s</adkim>
    <aspf>r</aspf>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.1</source_ip>
      <count>10</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
      <envelope_from>bounce.example.com</envelope_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.com</domain>
        <selector>mail</selector>
        <result>pass</result>
      </dkim>
      <spf>
        <domain>bounce.example.com</domain>
        <scope>mfrom</scope>
        <result>pass</result>
      </spf>
    </auth_results>
  </record>
  <record>
    <row>
      <source_ip>198.51.100.5</source_ip>
      <count>3</count>
      <policy_evaluated>
        <disposition>reject</disposition>
        <dkim>fail</dkim>
        <spf>fail</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
      <envelope_from>mailer.other.net</envelope_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>other.net</domain>
        <selector>bad</selector>
        <result>fail</result>
      </dkim>
      <spf>
        <domain>mailer.other.net</domain>
        <scope>mfrom</scope>
        <result>fail</result>
      </spf>
    </auth_results>
  </record>
</feedback>
"""


@pytest.fixture
def search_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain example.com, one ingested report, config set."""
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
    status, _ = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    client = wrap_client_with_csrf(TestClient(app))
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    run_one_job(config)
    yield client, config
    app.state.config = None


def test_get_aggregate_returns_200_with_items_and_pagination(search_app_client) -> None:
    client, _ = search_app_client
    r = client.get("/api/v1/reports/aggregate")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert data["items"][0]["domain"] == "example.com"
    assert data["items"][0]["report_id"] == "r1.example.com-20260101"


def test_get_aggregate_domain_filter(search_app_client) -> None:
    client, _ = search_app_client
    r = client.get("/api/v1/reports/aggregate?domains=example.com")
    assert r.status_code == 200
    assert all(i["domain"] == "example.com" for i in r.json()["items"])


def test_get_aggregate_time_filter(search_app_client) -> None:
    client, _ = search_app_client
    r = client.get("/api/v1/reports/aggregate?from=1735689600&to=1735776000")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r2 = client.get("/api/v1/reports/aggregate?from=9999999999&to=9999999999")
    assert r2.json()["total"] == 0


def test_get_aggregate_pagination(search_app_client) -> None:
    client, _ = search_app_client
    r = client.get("/api/v1/reports/aggregate?page=1&page_size=1")
    assert r.status_code == 200
    assert len(r.json()["items"]) <= 1
    assert r.json()["page"] == 1
    assert r.json()["page_size"] == 1


def test_get_aggregate_non_super_admin_with_assignment_sees_only_their_domain(search_app_client, temp_db_path: str) -> None:
    client, config = search_app_client
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_viewer", "viewer1", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        dom_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at) VALUES (?, ?, ?, ?)",
            ("usr_viewer", dom_id, "usr_xxx", "2026-01-01T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "viewer1", "password": "p"})
    r = client.get("/api/v1/reports/aggregate")
    assert r.status_code == 200
    assert all(i["domain"] == "example.com" for i in r.json()["items"])


def test_get_aggregate_non_super_admin_no_assignments_empty(search_app_client, temp_db_path: str) -> None:
    client, config = search_app_client
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_nodom", "nodom", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "nodom", "password": "p"})
    r = client.get("/api/v1/reports/aggregate")
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_get_aggregate_401_without_session(search_app_client) -> None:
    client, _ = search_app_client
    client.post("/api/v1/auth/logout")
    r = client.get("/api/v1/reports/aggregate")
    assert r.status_code == 401


@pytest.fixture
def search_records_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain, and report with records ingested."""
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
    status, _ = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    client = wrap_client_with_csrf(TestClient(app))
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": AGGREGATE_XML_WITH_RECORDS}]},
    )
    run_one_job(config)
    yield client, config
    app.state.config = None


def test_post_search_returns_records(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={})
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["items"][0]["record_date"] == "2025-01-01"
    assert {"dmarc_alignment", "dkim_alignment", "spf_alignment"} <= set(data["items"][0].keys())


def test_post_search_include_spf_fail(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={"include": {"spf_result": ["fail"]}})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["spf_result"] == "fail"
    assert data["items"][0]["source_ip"] == "198.51.100.5"


def test_post_search_include_alignment_filter(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={"include": {"dmarc_alignment": ["pass"]}})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["source_ip"] == "192.0.2.1"
    assert data["items"][0]["dmarc_alignment"] == "pass"


def test_post_search_exclude_disposition_none(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={"exclude": {"disposition": ["none"]}})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["disposition"] == "reject"


def test_post_search_returns_resolved_name_fields(search_records_client, temp_db_path: str) -> None:
    client, _ = search_records_client
    conn = get_connection(temp_db_path)
    conn.execute(
        """UPDATE aggregate_report_records
           SET resolved_name = ?, resolved_name_domain = ?
           WHERE source_ip = ?""",
        ("mail.example.net", "example.net", "192.0.2.1"),
    )
    conn.commit()
    conn.close()
    r = client.post("/api/v1/search", json={})
    assert r.status_code == 200
    item = [row for row in r.json()["items"] if row["source_ip"] == "192.0.2.1"][0]
    assert item["resolved_name"] == "mail.example.net"
    assert item["resolved_name_domain"] == "example.net"


def test_post_search_query_matches_resolved_host(search_records_client, temp_db_path: str) -> None:
    client, _ = search_records_client
    conn = get_connection(temp_db_path)
    conn.execute(
        """UPDATE aggregate_report_records
           SET resolved_name = ?, resolved_name_domain = ?
           WHERE source_ip = ?""",
        ("mail.example.net", "example.net", "192.0.2.1"),
    )
    conn.commit()
    conn.close()

    r = client.post("/api/v1/search", json={"query": "mail.example.net"})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["source_ip"] == "192.0.2.1"
    assert data["items"][0]["resolved_name"] == "mail.example.net"


def test_post_search_groups_by_source_ip(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={"group_by": "source_ip"})
    assert r.status_code == 200
    data = r.json()
    assert data["group_by"] == "source_ip"
    assert data["total"] == 2
    values = {item["group_value"] for item in data["items"]}
    assert values == {"192.0.2.1", "198.51.100.5"}


def test_post_search_groups_by_record_date(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search", json={"group_by": "record_date"})
    assert r.status_code == 200
    data = r.json()
    assert data["group_by"] == "record_date"
    assert data["total"] == 1
    assert data["items"][0]["group_value"] == "2025-01-01"


def test_post_grouped_search_returns_group_nodes(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post("/api/v1/search/grouped", json={"grouping": ["domain", "disposition"]})
    assert r.status_code == 200
    data = r.json()
    assert data["level_kind"] == "group"
    assert data["grouping"] == ["domain", "disposition"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    node = data["items"][0]
    assert node["type"] == "group"
    assert node["field"] == "domain"
    assert node["value"] == "example.com"
    assert node["message_count"] == 13
    assert node["dmarc_alignment_summary"]["pass"] == 10
    assert node["dmarc_alignment_summary"]["fail"] == 3


def test_post_grouped_search_returns_leaf_rows_for_branch(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post(
        "/api/v1/search/grouped",
        json={
            "grouping": ["domain", "disposition"],
            "path": [
                {"field": "domain", "value": "example.com"},
                {"field": "disposition", "value": "reject"},
            ],
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["level_kind"] == "row"
    assert data["total"] == 1
    assert data["items"][0]["type"] == "row"
    assert data["items"][0]["disposition"] == "reject"


def test_post_grouped_search_rejects_invalid_path_order(search_records_client) -> None:
    client, _ = search_records_client
    r = client.post(
        "/api/v1/search/grouped",
        json={
            "grouping": ["domain", "disposition"],
            "path": [{"field": "disposition", "value": "reject"}],
        },
    )
    assert r.status_code == 400


def test_post_search_domain_scoping(search_records_client, temp_db_path: str) -> None:
    """Viewer without domain assignment sees no records."""
    client, config = search_records_client
    conn = get_connection(temp_db_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_nodom", "nodom", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "nodom", "password": "p"})
    r = client.post("/api/v1/search", json={})
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0


def test_post_search_401_without_session(search_records_client) -> None:
    client, _ = search_records_client
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/search", json={})
    assert r.status_code == 401


def test_get_aggregate_detail_returns_report_with_records(search_records_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/aggregate/{id} returns report with records array."""
    client, _ = search_records_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM aggregate_reports LIMIT 1")
        report_id = cur.fetchone()[0]
    finally:
        conn.close()
    r = client.get(f"/api/v1/reports/aggregate/{report_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == report_id
    assert data["domain"] == "example.com"
    assert data["org_name"] == "Test Org"
    assert "records" in data
    assert len(data["records"]) == 2
    ips = {rec["source_ip"] for rec in data["records"]}
    assert ips == {"192.0.2.1", "198.51.100.5"}
    first_record = next(rec for rec in data["records"] if rec["source_ip"] == "192.0.2.1")
    assert first_record["dkim_alignment"] == "strict"
    assert first_record["spf_alignment"] == "relaxed"
    assert first_record["dmarc_alignment"] == "pass"


def test_get_aggregate_detail_404_not_found(search_records_client) -> None:
    """GET /api/v1/reports/aggregate/{id} returns 404 for non-existent id."""
    client, _ = search_records_client
    r = client.get("/api/v1/reports/aggregate/nonexistent_id")
    assert r.status_code == 404


def test_get_aggregate_detail_403_no_domain_access(search_records_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/aggregate/{id} returns 403 when user lacks domain access."""
    client, _ = search_records_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM aggregate_reports LIMIT 1")
        report_id = cur.fetchone()[0]
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_nodom2", "nodom2", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "nodom2", "password": "p"})
    r = client.get(f"/api/v1/reports/aggregate/{report_id}")
    assert r.status_code == 403


def test_get_aggregate_detail_401_without_session(search_records_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/aggregate/{id} returns 401 without session."""
    client, _ = search_records_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM aggregate_reports LIMIT 1")
        report_id = cur.fetchone()[0]
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    r = client.get(f"/api/v1/reports/aggregate/{report_id}")
    assert r.status_code == 401


MINIMAL_FORENSIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <feedback_type>auth-failure</feedback_type>
  <report_metadata>
    <org_name>Forensic Org</org_name>
    <report_id>ruf-example-20260301</report_id>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
  </policy_published>
  <auth_failure>
    <source_ip>192.0.2.99</source_ip>
    <arrival_date>2026-03-01T12:00:00Z</arrival_date>
    <header_from>bad@example.com</header_from>
    <spf_result>fail</spf_result>
    <dkim_result>fail</dkim_result>
    <dmarc_result>fail</dmarc_result>
    <failure_type>spf</failure_type>
  </auth_failure>
</feedback>
"""


@pytest.fixture
def forensic_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain, and forensic report ingested."""
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
    status, _ = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    client = wrap_client_with_csrf(TestClient(app))
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
    )
    run_one_job(config)
    yield client, config
    app.state.config = None


def test_get_forensic_detail_returns_report(forensic_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/forensic/{id} returns forensic report with all fields."""
    client, _ = forensic_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM forensic_reports LIMIT 1")
        report_id = cur.fetchone()[0]
    finally:
        conn.close()
    r = client.get(f"/api/v1/reports/forensic/{report_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == report_id
    assert data["domain"] == "example.com"
    assert data["report_id"] == "ruf-example-20260301"
    assert data["org_name"] == "Forensic Org"
    assert data["source_ip"] == "192.0.2.99"
    assert "resolved_name" in data
    assert "resolved_name_domain" in data
    assert data["spf_result"] == "fail"
    assert data["dkim_result"] == "fail"
    assert data["dmarc_result"] == "fail"
    assert data["failure_type"] == "spf"


def test_forensic_list_and_detail_return_resolved_name_fields(forensic_client, temp_db_path: str) -> None:
    client, _ = forensic_client
    conn = get_connection(temp_db_path)
    conn.execute(
        "UPDATE forensic_reports SET resolved_name = ?, resolved_name_domain = ?",
        ("mail.example.net", "example.net"),
    )
    conn.commit()
    cur = conn.execute("SELECT id FROM forensic_reports LIMIT 1")
    report_id = cur.fetchone()[0]
    conn.close()
    list_resp = client.get("/api/v1/reports/forensic")
    assert list_resp.status_code == 200
    assert list_resp.json()["items"][0]["resolved_name"] == "mail.example.net"
    assert list_resp.json()["items"][0]["resolved_name_domain"] == "example.net"
    detail_resp = client.get(f"/api/v1/reports/forensic/{report_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["resolved_name"] == "mail.example.net"
    assert detail["resolved_name_domain"] == "example.net"
    assert data["header_from"] == "bad@example.com"


def test_get_forensic_detail_404_not_found(forensic_client) -> None:
    """GET /api/v1/reports/forensic/{id} returns 404 for non-existent id."""
    client, _ = forensic_client
    r = client.get("/api/v1/reports/forensic/nonexistent_id")
    assert r.status_code == 404


def test_get_forensic_detail_403_no_domain_access(forensic_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/forensic/{id} returns 403 when user lacks domain access."""
    client, _ = forensic_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM forensic_reports LIMIT 1")
        report_id = cur.fetchone()[0]
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            ("usr_nofordom", "nofordom", hash_password("p"), "viewer", "2026-01-01T00:00:00Z", "usr_xxx"),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "nofordom", "password": "p"})
    r = client.get(f"/api/v1/reports/forensic/{report_id}")
    assert r.status_code == 403


def test_get_forensic_detail_401_without_session(forensic_client, temp_db_path: str) -> None:
    """GET /api/v1/reports/forensic/{id} returns 401 without session."""
    client, _ = forensic_client
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM forensic_reports LIMIT 1")
        report_id = cur.fetchone()[0]
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    r = client.get(f"/api/v1/reports/forensic/{report_id}")
    assert r.status_code == 401
