import os
import tempfile
import uuid

from backend.config.schema import Config
from backend.services.search_service import search_timeseries_records
from backend.storage.sqlite import get_connection, run_migrations


def _config_with_data() -> tuple[Config, dict[str, str], str]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    run_migrations(path)
    config = Config(
        database_path=path,
        log_level="ERROR",
        session_secret="test-secret",
        session_cookie_name="test_session",
        session_max_age_days=1,
    )
    conn = get_connection(path)
    try:
        domain_id = f"dom_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO domains (id, name, status, created_at) VALUES (?, ?, 'active', datetime('now'))",
            (domain_id, "example.com"),
        )
        item_one = f"item_{uuid.uuid4().hex[:8]}"
        item_two = f"item_{uuid.uuid4().hex[:8]}"
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        conn.execute(
            "INSERT INTO ingest_jobs (id, actor_type, actor_user_id, submitted_at, state) VALUES (?, 'user', 'usr_test', datetime('now'), 'completed')",
            (job_id,),
        )
        conn.execute(
            "INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content, status) VALUES (?, ?, 1, 'test', 'accepted')",
            (item_one, job_id),
        )
        conn.execute(
            "INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content, status) VALUES (?, ?, 2, 'test', 'accepted')",
            (item_two, job_id),
        )
        report_one = f"agg_{uuid.uuid4().hex[:8]}"
        report_two = f"agg_{uuid.uuid4().hex[:8]}"
        conn.execute(
            """INSERT INTO aggregate_reports (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at)
               VALUES (?, ?, ?, ?, 1735689600, 1735776000, ?, datetime('now'))""",
            (report_one, "ts_001", "Example Org", "example.com", item_one),
        )
        conn.execute(
            """INSERT INTO aggregate_reports (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at)
               VALUES (?, ?, ?, ?, 1735862400, 1735948800, ?, datetime('now'))""",
            (report_two, "ts_002", "Example Org", "example.com", item_two),
        )
        conn.execute(
            """INSERT INTO aggregate_report_records
               (id, aggregate_report_id, source_ip, resolved_name, resolved_name_domain, country_code, country_name, count, disposition, dkim_result, spf_result, dkim_alignment, spf_alignment, dmarc_alignment, header_from, envelope_from, envelope_to)
               VALUES (?, ?, '192.0.2.1', 'mail.example.com', 'example.com', 'US', 'United States', 10, 'none', 'pass', 'pass', 'strict', 'relaxed', 'pass', 'example.com', 'bounce.example.com', 'example.com')""",
            (f"rec_{uuid.uuid4().hex[:8]}", report_one),
        )
        conn.execute(
            """INSERT INTO aggregate_report_records
               (id, aggregate_report_id, source_ip, resolved_name, resolved_name_domain, country_code, country_name, count, disposition, dkim_result, spf_result, dkim_alignment, spf_alignment, dmarc_alignment, header_from, envelope_from, envelope_to)
               VALUES (?, ?, '198.51.100.5', 'bad.example.net', 'example.net', 'SE', 'Sweden', 3, 'reject', 'fail', 'fail', 'none', 'none', 'fail', 'example.com', 'evil.example.net', 'example.com')""",
            (f"rec_{uuid.uuid4().hex[:8]}", report_two),
        )
        conn.commit()
    finally:
        conn.close()
    return config, {"id": "usr_super", "role": "super-admin", "username": "admin"}, path


def test_search_timeseries_returns_daily_buckets_and_gaps() -> None:
    config, current_user, path = _config_with_data()
    try:
        result = search_timeseries_records(
            config,
            current_user,
            from_ts="2025-01-01",
            to_ts="2025-01-04",
            y_axis="message_count",
        )
        assert result["y_axis"] == "message_count"
        assert [bucket["date"] for bucket in result["buckets"]] == ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]
        assert result["buckets"][0]["spf"]["pass"] == 10
        assert result["buckets"][0]["dkim"]["pass"] == 10
        assert result["buckets"][0]["dmarc"]["pass"] == 10
        assert result["buckets"][1]["spf"]["pass"] == 0
        assert result["buckets"][2]["spf"]["fail"] == 3
        assert result["buckets"][2]["dmarc"]["fail"] == 3
    finally:
        os.unlink(path)


def test_search_timeseries_supports_row_and_report_count_metrics() -> None:
    config, current_user, path = _config_with_data()
    try:
        row_result = search_timeseries_records(config, current_user, y_axis="row_count")
        report_result = search_timeseries_records(config, current_user, y_axis="report_count")

        assert row_result["buckets"][0]["spf"]["pass"] == 1
        assert row_result["buckets"][2]["spf"]["fail"] == 1
        assert report_result["buckets"][0]["spf"]["pass"] == 1
        assert report_result["buckets"][2]["spf"]["fail"] == 1
    finally:
        os.unlink(path)
