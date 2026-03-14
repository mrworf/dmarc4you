"""Unit tests for FTS free-text search functionality."""

import pytest
from backend.services.search_service import _escape_fts_query, search_records
from backend.storage.sqlite import get_connection, run_migrations
from backend.config.schema import Config
import tempfile
import os
import uuid


@pytest.fixture
def test_db():
    """Create a temporary database with migrations applied."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    run_migrations(path)
    yield path
    os.unlink(path)


@pytest.fixture
def config(test_db):
    """Create a config pointing to the test database."""
    return Config(
        database_path=test_db,
        log_level="ERROR",
        session_secret="test-secret-key-for-testing",
        session_cookie_name="test_session",
        session_max_age_days=1,
    )


@pytest.fixture
def super_admin_user():
    """Super-admin user dict for testing."""
    return {"id": "usr_super", "role": "super-admin", "username": "admin"}


@pytest.fixture
def populated_db(test_db, config):
    """Populate database with test data including aggregate reports and records."""
    conn = get_connection(test_db)
    try:
        domain_id = f"dom_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO domains (id, name, status, created_at) VALUES (?, ?, 'active', datetime('now'))",
            (domain_id, "example.com"),
        )
        
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO ingest_jobs (id, actor_type, actor_user_id, submitted_at, state)
               VALUES (?, 'user', 'usr_test', datetime('now'), 'completed')""",
            (job_id,),
        )
        
        item1_id = f"item_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content, status)
               VALUES (?, ?, 1, 'test', 'accepted')""",
            (item1_id, job_id),
        )
        
        item2_id = f"item_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content, status)
               VALUES (?, ?, 2, 'test', 'accepted')""",
            (item2_id, job_id),
        )
        
        report_id = f"agg_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_reports (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at)
               VALUES (?, ?, ?, ?, 1704067200, 1704153600, ?, datetime('now'))""",
            (report_id, "rpt_001", "Google Inc", "example.com", item1_id),
        )
        
        rec1_id = f"rec_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_report_records 
               (id, aggregate_report_id, source_ip, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rec1_id, report_id, "192.0.2.1", 100, "none", "pass", "pass", "sender@example.com", "bounce@example.com", "example.com"),
        )
        
        rec2_id = f"rec_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_report_records 
               (id, aggregate_report_id, source_ip, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rec2_id, report_id, "198.51.100.5", 50, "quarantine", "fail", "fail", "spammer@malicious.net", "fake@malicious.net", "example.com"),
        )
        
        report2_id = f"agg_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_reports (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at)
               VALUES (?, ?, ?, ?, 1704067200, 1704153600, ?, datetime('now'))""",
            (report2_id, "rpt_002", "Microsoft Corp", "example.com", item2_id),
        )
        
        rec3_id = f"rec_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_report_records 
               (id, aggregate_report_id, source_ip, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (rec3_id, report2_id, "10.0.0.1", 25, "none", "pass", "pass", "internal@corp.example.com", "noreply@corp.example.com", "example.com"),
        )
        
        conn.commit()
    finally:
        conn.close()
    return test_db


class TestEscapeFtsQuery:
    """Tests for the FTS query escaping function."""
    
    def test_empty_query(self):
        assert _escape_fts_query("") == ""
        assert _escape_fts_query(None) == ""
        assert _escape_fts_query("   ") == ""
    
    def test_single_term(self):
        result = _escape_fts_query("google")
        assert result == '"google"*'
    
    def test_multiple_terms(self):
        result = _escape_fts_query("google fail")
        assert result == '"google"* "fail"*'
    
    def test_escapes_quotes(self):
        result = _escape_fts_query('test"value')
        assert result == '"test""value"*'
    
    def test_handles_extra_whitespace(self):
        result = _escape_fts_query("  google   fail  ")
        assert result == '"google"* "fail"*'


class TestSearchRecordsFts:
    """Tests for FTS search in search_records."""
    
    def test_search_without_query_returns_all(self, populated_db, config, super_admin_user):
        """Search without query returns all records (existing behavior)."""
        result = search_records(config, super_admin_user)
        assert result["total"] == 3
        assert len(result["items"]) == 3
    
    def test_search_with_empty_query_returns_all(self, populated_db, config, super_admin_user):
        """Empty query string behaves same as no query."""
        result = search_records(config, super_admin_user, query="")
        assert result["total"] == 3
        
        result2 = search_records(config, super_admin_user, query="   ")
        assert result2["total"] == 3
    
    def test_search_by_org_name(self, populated_db, config, super_admin_user):
        """FTS search finds records by org_name."""
        result = search_records(config, super_admin_user, query="Google")
        assert result["total"] == 2
        for item in result["items"]:
            assert item["org_name"] == "Google Inc"
    
    def test_search_by_source_ip(self, populated_db, config, super_admin_user):
        """FTS search finds records by source_ip."""
        result = search_records(config, super_admin_user, query="192.0.2")
        assert result["total"] == 1
        assert result["items"][0]["source_ip"] == "192.0.2.1"
    
    def test_search_by_header_from(self, populated_db, config, super_admin_user):
        """FTS search finds records by header_from."""
        result = search_records(config, super_admin_user, query="malicious")
        assert result["total"] == 1
        assert "malicious" in result["items"][0]["header_from"]
    
    def test_search_combined_with_filters(self, populated_db, config, super_admin_user):
        """FTS search works with include/exclude filters."""
        result = search_records(
            config,
            super_admin_user,
            query="Google",
            include={"spf_result": ["pass"]},
        )
        assert result["total"] == 1
        assert result["items"][0]["spf_result"] == "pass"
        assert result["items"][0]["org_name"] == "Google Inc"
    
    def test_search_no_matches(self, populated_db, config, super_admin_user):
        """FTS search with no matching results returns empty."""
        result = search_records(config, super_admin_user, query="nonexistent")
        assert result["total"] == 0
        assert result["items"] == []
    
    def test_search_partial_match(self, populated_db, config, super_admin_user):
        """FTS search with prefix matching."""
        result = search_records(config, super_admin_user, query="Micro")
        assert result["total"] == 1
        assert result["items"][0]["org_name"] == "Microsoft Corp"


class TestSearchRecordsDomainScoping:
    """Tests that FTS search respects domain scoping."""
    
    def test_viewer_only_sees_assigned_domains(self, populated_db, config):
        """Non-super-admin user only sees records from assigned domains."""
        viewer_user = {"id": "usr_viewer", "role": "viewer", "username": "viewer"}
        result = search_records(config, viewer_user, query="Google")
        assert result["total"] == 0
        assert result["items"] == []
