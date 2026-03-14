"""Integration tests for raw artifact archival during ingest."""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.services.domain_service import create_domain
from backend.jobs.runner import run_one_job
from tests.conftest import wrap_client_with_csrf


MINIMAL_AGGREGATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Archive Test Org</org_name>
    <report_id>archive-test-report-001</report_id>
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

MINIMAL_FORENSIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <feedback_type>auth-failure</feedback_type>
  <report_metadata>
    <org_name>Forensic Archive Org</org_name>
    <report_id>archive-forensic-001</report_id>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
  </policy_published>
  <auth_failure>
    <source_ip>192.0.2.1</source_ip>
    <arrival_date>2026-03-01T12:00:00Z</arrival_date>
    <header_from>test@example.com</header_from>
    <spf_result>fail</spf_result>
    <dkim_result>pass</dkim_result>
    <dmarc_result>fail</dmarc_result>
    <failure_type>spf</failure_type>
  </auth_failure>
</feedback>
"""


@pytest.fixture
def archive_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain, and archive storage configured."""
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None

    with tempfile.TemporaryDirectory() as archive_dir:
        config = Config(
            database_path=temp_db_path,
            log_level="INFO",
            session_secret="test-secret",
            session_cookie_name="dmarc_session",
            session_max_age_days=7,
            archive_storage_path=archive_dir,
        )
        app.state.config = config
        conn = get_connection(temp_db_path)
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.close()
        status, _ = create_domain(config, "example.com", admin_id, "super-admin")
        assert status == "ok"
        yield wrap_client_with_csrf(TestClient(app)), password, config, archive_dir
        app.state.config = None


@pytest.fixture
def no_archive_app_client(temp_db_path: str):
    """App with temp DB, bootstrap admin, domain, but NO archive storage."""
    run_migrations(temp_db_path)
    password = ensure_bootstrap_admin(temp_db_path)
    assert password is not None

    config = Config(
        database_path=temp_db_path,
        log_level="INFO",
        session_secret="test-secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
        archive_storage_path=None,
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


class TestArchiveIngest:
    """Tests for ingest with archive storage enabled."""

    def test_accepted_aggregate_creates_archive_file(self, archive_app_client) -> None:
        """When archive is enabled, accepted aggregate report creates a .raw file."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        domain_dir = Path(archive_dir) / "example.com"
        assert domain_dir.is_dir()
        raw_files = list(domain_dir.glob("*.raw"))
        assert len(raw_files) == 1
        assert b"archive-test-report-001" in raw_files[0].read_bytes()

    def test_accepted_forensic_creates_archive_file(self, archive_app_client) -> None:
        """When archive is enabled, accepted forensic report creates a .raw file."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_FORENSIC_XML}]},
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        domain_dir = Path(archive_dir) / "example.com"
        assert domain_dir.is_dir()
        raw_files = list(domain_dir.glob("*.raw"))
        assert len(raw_files) == 1
        assert b"archive-forensic-001" in raw_files[0].read_bytes()

    def test_duplicate_does_not_create_archive_file(self, archive_app_client) -> None:
        """Duplicate reports are not archived (only first acceptance is archived)."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        for _ in range(2):
            client.post(
                "/api/v1/reports/ingest",
                json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
            )
        run_one_job(config)
        run_one_job(config)

        domain_dir = Path(archive_dir) / "example.com"
        raw_files = list(domain_dir.glob("*.raw"))
        assert len(raw_files) == 1

    def test_rejected_does_not_create_archive_file(self, archive_app_client) -> None:
        """Rejected reports (unauthorized domain) are not archived."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        other_xml = MINIMAL_AGGREGATE_XML.replace("example.com", "unauthorized.com")
        r = client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": other_xml}]},
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        unauthorized_dir = Path(archive_dir) / "unauthorized.com"
        assert not unauthorized_dir.exists()

    def test_invalid_does_not_create_archive_file(self, archive_app_client) -> None:
        """Invalid (unparseable) reports are not archived."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": "<invalid"}]},
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        archive_path = Path(archive_dir)
        raw_files = list(archive_path.rglob("*.raw"))
        assert len(raw_files) == 0

    def test_multiple_reports_creates_multiple_files(self, archive_app_client) -> None:
        """Multiple accepted reports create multiple archive files."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        xml2 = MINIMAL_AGGREGATE_XML.replace("archive-test-report-001", "archive-test-report-002")
        r = client.post(
            "/api/v1/reports/ingest",
            json={
                "source": "test",
                "reports": [
                    {"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML},
                    {"content_type": "application/xml", "content": xml2},
                ],
            },
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        domain_dir = Path(archive_dir) / "example.com"
        raw_files = list(domain_dir.glob("*.raw"))
        assert len(raw_files) == 2


class TestNoArchiveIngest:
    """Tests for ingest without archive storage (disabled)."""

    def test_accepted_report_no_archive_file(self, no_archive_app_client) -> None:
        """When archive is disabled, no .raw files are created anywhere."""
        client, password, config = no_archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
        assert r.status_code in (200, 202)
        run_one_job(config)

        detail = client.get(f"/api/v1/ingest-jobs/{r.json()['job_id']}")
        assert detail.json()["items"][0]["status"] == "accepted"


class TestDomainStatsWithArchive:
    """Tests for domain stats artifact_count."""

    def test_stats_includes_artifact_count_when_archive_enabled(self, archive_app_client) -> None:
        """GET /domains/{id}/stats includes artifact_count when archive is configured."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        xml2 = MINIMAL_AGGREGATE_XML.replace("archive-test-report-001", "archive-test-report-002")
        for xml in [MINIMAL_AGGREGATE_XML, xml2]:
            client.post(
                "/api/v1/reports/ingest",
                json={"source": "test", "reports": [{"content_type": "application/xml", "content": xml}]},
            )
        run_one_job(config)
        run_one_job(config)

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/stats")
        assert r.status_code == 200
        data = r.json()
        assert "artifact_count" in data
        assert data["artifact_count"] == 2
        assert data["aggregate_reports"] == 2

    def test_stats_excludes_artifact_count_when_archive_disabled(self, no_archive_app_client) -> None:
        """GET /domains/{id}/stats omits artifact_count when archive is not configured."""
        client, password, config = no_archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
        run_one_job(config)

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/stats")
        assert r.status_code == 200
        data = r.json()
        assert "artifact_count" not in data
        assert data["aggregate_reports"] == 1


class TestArtifactListEndpoint:
    """Tests for GET /domains/{id}/artifacts endpoint."""

    def test_list_artifacts_returns_artifact_ids(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts returns list of artifact IDs."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        xml2 = MINIMAL_AGGREGATE_XML.replace("archive-test-report-001", "archive-test-report-002")
        for xml in [MINIMAL_AGGREGATE_XML, xml2]:
            client.post(
                "/api/v1/reports/ingest",
                json={"source": "test", "reports": [{"content_type": "application/xml", "content": xml}]},
            )
        run_one_job(config)
        run_one_job(config)

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["domain_id"] == domain_id
        assert len(data["artifacts"]) == 2
        assert all(isinstance(a, str) for a in data["artifacts"])

    def test_list_artifacts_empty_when_no_archive_configured(self, no_archive_app_client) -> None:
        """GET /domains/{id}/artifacts returns empty list when archival is disabled."""
        client, password, config = no_archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["domain_id"] == domain_id
        assert data["artifacts"] == []

    def test_list_artifacts_empty_domain(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts returns empty list for domain with no artifacts."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts")
        assert r.status_code == 200
        assert r.json()["artifacts"] == []

    def test_list_artifacts_forbidden_for_unassigned_domain(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts returns 403 for domain user is not assigned to."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        from backend.services.user_service import create_user
        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.close()
        _, result = create_user(config, {"id": admin_id, "role": "super-admin"}, "viewer1", "viewer")
        viewer_password = result["password"]

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login", json={"username": "viewer1", "password": viewer_password})

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts")
        assert r.status_code == 403

    def test_list_artifacts_not_found_for_invalid_domain(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts returns 404 for non-existent domain."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.get("/api/v1/domains/dom_nonexistent/artifacts")
        assert r.status_code == 404


class TestArtifactDownloadEndpoint:
    """Tests for GET /domains/{id}/artifacts/{artifact_id} endpoint."""

    def test_download_artifact_returns_bytes(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts/{artifact_id} returns raw bytes."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
        run_one_job(config)

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        list_r = client.get(f"/api/v1/domains/{domain_id}/artifacts")
        artifact_id = list_r.json()["artifacts"][0]

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts/{artifact_id}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/octet-stream"
        assert "attachment" in r.headers.get("content-disposition", "")
        assert b"archive-test-report-001" in r.content

    def test_download_artifact_not_found_when_archive_disabled(self, no_archive_app_client) -> None:
        """GET /domains/{id}/artifacts/{artifact_id} returns 404 when archival is disabled."""
        client, password, config = no_archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts/some-artifact")
        assert r.status_code == 404

    def test_download_artifact_not_found_for_nonexistent_artifact(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts/{artifact_id} returns 404 for non-existent artifact."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts/nonexistent-artifact")
        assert r.status_code == 404

    def test_download_artifact_forbidden_for_unassigned_domain(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts/{artifact_id} returns 403 for unassigned domain."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        client.post(
            "/api/v1/reports/ingest",
            json={"source": "test", "reports": [{"content_type": "application/xml", "content": MINIMAL_AGGREGATE_XML}]},
        )
        run_one_job(config)

        from backend.services.user_service import create_user
        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1")
        admin_id = cur.fetchone()[0]
        conn.close()
        _, result = create_user(config, {"id": admin_id, "role": "super-admin"}, "viewer2", "viewer")
        viewer_password = result["password"]

        conn = get_connection(config.database_path)
        cur = conn.execute("SELECT id FROM domains WHERE name = 'example.com'")
        domain_id = cur.fetchone()[0]
        conn.close()

        client.post("/api/v1/auth/logout")
        client.post("/api/v1/auth/login", json={"username": "viewer2", "password": viewer_password})

        r = client.get(f"/api/v1/domains/{domain_id}/artifacts/some-artifact")
        assert r.status_code == 403

    def test_download_artifact_not_found_for_invalid_domain(self, archive_app_client) -> None:
        """GET /domains/{id}/artifacts/{artifact_id} returns 404 for non-existent domain."""
        client, password, config, archive_dir = archive_app_client
        client.post("/api/v1/auth/login", json={"username": "admin", "password": password})

        r = client.get("/api/v1/domains/dom_nonexistent/artifacts/some-artifact")
        assert r.status_code == 404
