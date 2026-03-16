"""Ingest slice: POST ingest, job runner, GET job detail, accepted/duplicate/rejected/invalid."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.services.domain_service import create_domain
from backend.jobs.runner import run_one_job
from tests.conftest import wrap_client_with_csrf

# Minimal valid DMARC aggregate XML (one policy domain)
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

# Minimal valid DMARC forensic XML
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
def ingest_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain example.com, config set."""
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
    yield wrap_client_with_csrf(TestClient(app)), password, config
    app.state.config = None


def test_post_ingest_creates_job_queued(ingest_app_client) -> None:
    client, password, _ = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    response = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    assert response.status_code in (200, 202)
    data = response.json()
    assert "job_id" in data
    assert data["state"] == "queued"


def test_runner_accepts_valid_aggregate_and_persists(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] in ("completed", "completed_with_warnings")
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "accepted"
    assert data["items"][0]["domain_detected"] == "example.com"
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT report_id, domain FROM aggregate_reports")
        row = cur.fetchone()
        assert row is not None
        assert row[1] == "example.com"
    finally:
        conn.close()


def test_runner_stores_reverse_dns_for_aggregate_records(ingest_app_client, monkeypatch) -> None:
    client, password, config = ingest_app_client
    aggregate_with_record = MINIMAL_AGGREGATE_XML.replace(
        "</feedback>",
        """
  <record>
    <row>
      <source_ip>192.0.2.1</source_ip>
      <count>5</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers><header_from>example.com</header_from></identifiers>
  </record>
</feedback>""",
    )
    monkeypatch.setattr("backend.jobs.runner.resolve_ip", lambda ip: ("mail.example.net", "example.net"))
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": aggregate_with_record}]},
    )
    run_one_job(config)
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT source_ip, resolved_name, resolved_name_domain FROM aggregate_report_records")
        row = cur.fetchone()
        assert row == ("192.0.2.1", "mail.example.net", "example.net")
    finally:
        conn.close()


def test_runner_keeps_ingest_when_reverse_dns_fails(ingest_app_client, monkeypatch) -> None:
    client, password, config = ingest_app_client
    monkeypatch.setattr("backend.jobs.runner.resolve_ip", lambda ip: (None, None))
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
    )
    run_one_job(config)
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT source_ip, resolved_name, resolved_name_domain FROM forensic_reports")
        row = cur.fetchone()
        assert row == ("192.0.2.99", None, None)
    finally:
        conn.close()


def test_duplicate_report_id_domain_yields_duplicate(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    for _ in range(2):
        client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
    run_one_job(config)
    run_one_job(config)
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, status FROM ingest_job_items ORDER BY sequence_no")
        items = cur.fetchall()
        assert len(items) == 2
        statuses = [i[1] for i in items]
        assert "accepted" in statuses
        assert "duplicate" in statuses
    finally:
        conn.close()


def test_rejected_when_domain_not_configured(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    # XML has domain example.com; do NOT create example.com - use other.com in XML
    other_xml = MINIMAL_AGGREGATE_XML.replace("example.com", "other.com").replace("r1.example.com", "r1.other.com")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": other_xml}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["status"] == "rejected"


def test_invalid_xml_yields_invalid(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": "<not valid xml"}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["status"] == "invalid"


def test_get_job_detail_401_without_session(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    job_id = r.json()["job_id"]
    client.post("/api/v1/auth/logout")
    resp = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert resp.status_code == 401


def test_list_ingest_jobs_401_without_session(ingest_app_client) -> None:
    client, _, _ = ingest_app_client
    resp = client.get("/api/v1/ingest-jobs")
    assert resp.status_code == 401


def test_list_ingest_jobs_returns_only_current_user_jobs(ingest_app_client) -> None:
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    list_resp = client.get("/api/v1/ingest-jobs")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert "jobs" in data
    job_ids = [j["job_id"] for j in data["jobs"]]
    assert job_id in job_ids


def test_ingest_with_api_key_201_and_runner_accepts(ingest_app_client) -> None:
    """POST ingest with Bearer API key (scope reports:ingest) creates job with actor_api_key_id; runner accepts report for key's domain."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post(
        "/api/v1/apikeys",
        json={"nickname": "ingest-key", "domain_ids": [domain_id], "scopes": ["reports:ingest"]},
    )
    assert r.status_code == 201
    raw_key = r.json()["key"]
    client.post("/api/v1/auth/logout")
    job_r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "cli", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert job_r.status_code in (200, 201)
    job_id = job_r.json()["job_id"]
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT actor_type, actor_api_key_id, actor_user_id FROM ingest_jobs WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "api_key"
    assert row[1] is not None
    assert row[2] is None
    run_one_job(config)
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT status, domain_detected FROM ingest_job_items WHERE job_id = ?", (job_id,))
    item = cur.fetchone()
    conn.close()
    assert item is not None
    assert item[0] == "accepted"
    assert item[1] == "example.com"


def test_ingest_without_auth_401(ingest_app_client) -> None:
    """POST ingest with no session and no Bearer returns 401."""
    client, _, _ = ingest_app_client
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "cli", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    assert r.status_code == 401


def test_ingest_with_invalid_api_key_403(ingest_app_client) -> None:
    """POST ingest with invalid Bearer key returns 403."""
    client, _, _ = ingest_app_client
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "cli", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        headers={"Authorization": "Bearer dmarc_invalidkey123"},
    )
    assert r.status_code == 403


def test_ingest_with_api_key_without_scope_403(ingest_app_client) -> None:
    """POST ingest with valid API key that lacks reports:ingest scope returns 403."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    conn = get_connection(config.database_path)
    cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com' LIMIT 1")
    domain_id = cur.fetchone()[0]
    conn.close()
    r = client.post(
        "/api/v1/apikeys",
        json={"nickname": "read-only-key", "domain_ids": [domain_id], "scopes": ["reports:read"]},
    )
    assert r.status_code == 201
    raw_key = r.json()["key"]
    client.post("/api/v1/auth/logout")
    job_r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "cli", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        headers={"Authorization": f"Bearer {raw_key}"},
    )
    assert job_r.status_code == 403


def test_list_ingest_jobs_excludes_other_users_job_and_detail_404(ingest_app_client, temp_db_path: str) -> None:
    from backend.auth.password import hash_password

    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
    )
    assert r.status_code in (200, 202)
    admin_job_id = r.json()["job_id"]
    conn = get_connection(temp_db_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
            ("usr_other", "other", hash_password("otherpass"), "admin", "2026-01-01T00:00:00Z", admin_id),
        )
        conn.commit()
    finally:
        conn.close()
    client.post("/api/v1/auth/logout")
    client.post("/api/v1/auth/login", json={"username": "other", "password": "otherpass"})
    list_resp = client.get("/api/v1/ingest-jobs")
    assert list_resp.status_code == 200
    job_ids = [j["job_id"] for j in list_resp.json()["jobs"]]
    assert admin_job_id not in job_ids
    detail_resp = client.get(f"/api/v1/ingest-jobs/{admin_job_id}")
    assert detail_resp.status_code == 404


def test_runner_accepts_valid_forensic_and_persists(ingest_app_client) -> None:
    """Forensic XML is parsed, persisted to forensic_reports, and job item shows report_type_detected=forensic."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] in ("completed", "completed_with_warnings")
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "accepted"
    assert data["items"][0]["domain_detected"] == "example.com"
    assert data["items"][0]["report_type_detected"] == "forensic"
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT report_id, domain, source_ip, spf_result FROM forensic_reports")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "ruf-example-20260301"
        assert row[1] == "example.com"
        assert row[2] == "192.0.2.99"
        assert row[3] == "fail"
    finally:
        conn.close()


def test_duplicate_forensic_report_id_domain_yields_duplicate(ingest_app_client) -> None:
    """Ingesting the same forensic report twice yields duplicate on second."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    for _ in range(2):
        client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
        )
    run_one_job(config)
    run_one_job(config)
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT status, report_type_detected FROM ingest_job_items ORDER BY id")
        items = cur.fetchall()
        assert len(items) == 2
        statuses = [i[0] for i in items]
        assert "accepted" in statuses
        assert "duplicate" in statuses
        for item in items:
            assert item[1] == "forensic"
    finally:
        conn.close()


def test_mixed_envelope_aggregate_and_forensic(ingest_app_client) -> None:
    """Envelope with both aggregate and forensic reports processes both correctly."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={
            "source": "test",
            "reports": [
                {"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML},
                {"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML},
            ],
        },
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] == "completed"
    assert len(data["items"]) == 2
    report_types = {i["report_type_detected"] for i in data["items"]}
    assert report_types == {"aggregate", "forensic"}
    for item in data["items"]:
        assert item["status"] == "accepted"


def test_get_reports_forensic_list(ingest_app_client) -> None:
    """GET /api/v1/reports/forensic lists ingested forensic reports with domain scoping."""
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
    )
    run_one_job(config)
    resp = client.get("/api/v1/reports/forensic")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["report_id"] == "ruf-example-20260301"
    assert item["domain"] == "example.com"
    assert item["source_ip"] == "192.0.2.99"
    assert item["spf_result"] == "fail"


def test_forensic_rejected_when_domain_not_configured(ingest_app_client) -> None:
    """Forensic report for unconfigured domain is rejected."""
    client, password, config = ingest_app_client
    other_xml = MINIMAL_FORENSIC_XML.replace("example.com", "other.com").replace("ruf-example", "ruf-other")
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    r = client.post(
        "/api/v1/reports/ingest",
        json={"source": "test", "reports": [{"content_type": "application/xml", "content": other_xml}]},
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["status"] == "rejected"
    assert detail.json()["items"][0]["report_type_detected"] == "forensic"


def _make_mime_email(attachments: list[tuple[str, str, bytes]]) -> str:
    """Build a simple multipart/mixed MIME message with given attachments.
    
    attachments: list of (filename, content_type, content_bytes)
    Returns the MIME message as a string.
    """
    import base64
    boundary = "----=_Part_12345"
    parts = []
    for filename, content_type, content in attachments:
        encoded = base64.b64encode(content).decode("ascii")
        part = (
            f'--{boundary}\r\n'
            f'Content-Type: {content_type}; name="{filename}"\r\n'
            f'Content-Disposition: attachment; filename="{filename}"\r\n'
            f'Content-Transfer-Encoding: base64\r\n'
            f'\r\n'
            f'{encoded}\r\n'
        )
        parts.append(part)
    body = "".join(parts) + f'--{boundary}--\r\n'
    headers = (
        f'From: reporter@example.org\r\n'
        f'To: dmarc@example.com\r\n'
        f'Subject: DMARC Report\r\n'
        f'MIME-Version: 1.0\r\n'
        f'Content-Type: multipart/mixed; boundary="{boundary}"\r\n'
        f'\r\n'
    )
    return headers + body


def test_ingest_mime_email_with_aggregate_attachment(ingest_app_client) -> None:
    """MIME email with XML attachment is parsed and aggregate report is accepted."""
    import base64
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    
    email_content = _make_mime_email([
        ("report.xml", "application/xml", MINIMAL_AGGREGATE_XML.encode("utf-8"))
    ])
    encoded_email = base64.b64encode(email_content.encode("utf-8")).decode("ascii")
    
    r = client.post(
        "/api/v1/reports/ingest",
        json={
            "source": "email",
            "reports": [{
                "content_type": "message/rfc822",
                "content_transfer_encoding": "base64",
                "content": encoded_email
            }]
        },
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] in ("completed", "completed_with_warnings")
    assert len(data["items"]) == 1
    assert data["items"][0]["status"] == "accepted"
    assert data["items"][0]["domain_detected"] == "example.com"
    
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT report_id, domain FROM aggregate_reports")
        row = cur.fetchone()
        assert row is not None
        assert row[1] == "example.com"
    finally:
        conn.close()


def test_ingest_mime_email_with_gzip_attachment(ingest_app_client) -> None:
    """MIME email with gzip-compressed XML attachment is decompressed and accepted."""
    import base64
    import gzip
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    
    compressed_xml = gzip.compress(MINIMAL_AGGREGATE_XML.encode("utf-8"))
    email_content = _make_mime_email([
        ("report.xml.gz", "application/gzip", compressed_xml)
    ])
    encoded_email = base64.b64encode(email_content.encode("utf-8")).decode("ascii")
    
    r = client.post(
        "/api/v1/reports/ingest",
        json={
            "source": "email",
            "reports": [{
                "content_type": "message/rfc822",
                "content_transfer_encoding": "base64",
                "content": encoded_email
            }]
        },
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] in ("completed", "completed_with_warnings")
    assert data["items"][0]["status"] == "accepted"


def test_ingest_mime_email_with_multiple_attachments(ingest_app_client) -> None:
    """MIME email with multiple attachments processes each and accepts valid ones."""
    import base64
    client, password, config = ingest_app_client
    client.post("/api/v1/auth/login", json={"username": "admin", "password": password})
    
    xml2 = MINIMAL_AGGREGATE_XML.replace("r1.example.com-20260101", "r2.example.com-20260102")
    email_content = _make_mime_email([
        ("report1.xml", "application/xml", MINIMAL_AGGREGATE_XML.encode("utf-8")),
        ("report2.xml", "application/xml", xml2.encode("utf-8")),
    ])
    encoded_email = base64.b64encode(email_content.encode("utf-8")).decode("ascii")
    
    r = client.post(
        "/api/v1/reports/ingest",
        json={
            "source": "email",
            "reports": [{
                "content_type": "message/rfc822",
                "content_transfer_encoding": "base64",
                "content": encoded_email
            }]
        },
    )
    assert r.status_code in (200, 202)
    job_id = r.json()["job_id"]
    run_one_job(config)
    
    detail = client.get(f"/api/v1/ingest-jobs/{job_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["state"] in ("completed", "completed_with_warnings")
    assert data["items"][0]["status"] == "accepted"
    
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM aggregate_reports")
        count = cur.fetchone()[0]
        assert count == 2
    finally:
        conn.close()
