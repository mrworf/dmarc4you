import os
import tempfile
import uuid

from backend.config.schema import Config
from backend.services.dmarc_alignment import (
    backfill_missing_aggregate_alignment,
    compute_aggregate_alignment,
    compute_dkim_alignment,
    compute_spf_alignment,
)
from backend.services.search_service import search_records
from backend.storage.sqlite import get_connection, run_migrations


def test_compute_dkim_alignment_strict_match() -> None:
    alignment = compute_dkim_alignment(
        "example.com",
        [{"auth_method": "dkim", "domain": "example.com", "result": "pass"}],
        "pass",
        "s",
    )
    assert alignment == "strict"


def test_compute_dkim_alignment_relaxed_subdomain_match() -> None:
    alignment = compute_dkim_alignment(
        "example.com",
        [{"auth_method": "dkim", "domain": "mail.example.com", "result": "pass"}],
        "pass",
        "r",
    )
    assert alignment == "relaxed"


def test_compute_spf_alignment_strict_requires_exact_domain() -> None:
    alignment = compute_spf_alignment(
        "example.com",
        "bounce.example.com",
        [{"auth_method": "spf", "domain": "bounce.example.com", "scope": "mfrom", "result": "pass"}],
        "pass",
        "s",
    )
    assert alignment == "none"


def test_compute_spf_alignment_relaxed_allows_same_org_domain() -> None:
    alignment = compute_spf_alignment(
        "example.com",
        "bounce.example.com",
        [{"auth_method": "spf", "domain": "bounce.example.com", "scope": "mfrom", "result": "pass"}],
        "pass",
        "r",
    )
    assert alignment == "relaxed"


def test_compute_spf_alignment_falls_back_to_envelope_from_when_scope_is_not_mfrom() -> None:
    alignment = compute_spf_alignment(
        "example.com",
        "bounce.example.com",
        [{"auth_method": "spf", "domain": "bounce.example.com", "scope": "helo", "result": "pass"}],
        "pass",
        "r",
    )
    assert alignment == "relaxed"


def test_compute_spf_alignment_uses_auth_domain_when_scope_is_missing() -> None:
    alignment = compute_spf_alignment(
        "thedudes.nu",
        None,
        [{"auth_method": "spf", "domain": "thedudes.nu", "scope": None, "result": "pass"}],
        "pass",
        "r",
    )
    assert alignment == "strict"


def test_compute_aggregate_alignment_uses_any_passing_dkim_signature() -> None:
    alignment = compute_aggregate_alignment(
        header_from="example.com",
        envelope_from="bounce.other.net",
        dkim_result="pass",
        spf_result="fail",
        auth_results=[
            {"auth_method": "dkim", "domain": "invalid_domain", "result": "pass"},
            {"auth_method": "dkim", "domain": "mail.example.com", "result": "pass"},
        ],
        adkim="r",
        aspf="r",
    )
    assert alignment["dkim_alignment"] == "relaxed"
    assert alignment["dmarc_alignment"] == "pass"


def test_compute_aggregate_alignment_returns_unknown_for_missing_domains() -> None:
    alignment = compute_aggregate_alignment(
        header_from=None,
        envelope_from=None,
        dkim_result="pass",
        spf_result="pass",
        auth_results=[],
        adkim=None,
        aspf=None,
    )
    assert alignment["dkim_alignment"] == "unknown"
    assert alignment["spf_alignment"] == "unknown"
    assert alignment["dmarc_alignment"] == "unknown"


def test_backfill_missing_alignment_persists_legacy_rows() -> None:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
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
            job_id = f"job_{uuid.uuid4().hex[:8]}"
            item_id = f"item_{uuid.uuid4().hex[:8]}"
            report_id = f"agg_{uuid.uuid4().hex[:8]}"
            record_id = f"rec_{uuid.uuid4().hex[:8]}"

            conn.execute(
                "INSERT INTO domains (id, name, status, created_at) VALUES (?, ?, 'active', datetime('now'))",
                (domain_id, "example.com"),
            )
            conn.execute(
                """INSERT INTO ingest_jobs (id, actor_type, actor_user_id, submitted_at, state)
                   VALUES (?, 'user', 'usr_test', datetime('now'), 'completed')""",
                (job_id,),
            )
            conn.execute(
                """INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content, status)
                   VALUES (?, ?, 1, 'test', 'accepted')""",
                (item_id, job_id),
            )
            conn.execute(
                """INSERT INTO aggregate_reports
                   (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at, adkim, aspf)
                   VALUES (?, ?, ?, ?, 1704067200, 1704153600, ?, datetime('now'), 's', 'r')""",
                (report_id, "legacy-report", "Legacy Org", "example.com", item_id),
            )
            conn.execute(
                """INSERT INTO aggregate_report_records
                   (id, aggregate_report_id, source_ip, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to,
                    dkim_alignment, spf_alignment, dmarc_alignment)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)""",
                (
                    record_id,
                    report_id,
                    "192.0.2.10",
                    5,
                    "none",
                    "pass",
                    "pass",
                    "example.com",
                    "bounce.example.com",
                    "example.com",
                ),
            )
            conn.execute(
                """INSERT INTO aggregate_record_auth_results
                   (id, aggregate_record_id, auth_method, domain, selector, scope, result, human_result)
                   VALUES (?, ?, 'dkim', ?, 'mail', NULL, 'pass', NULL)""",
                (f"auth_{uuid.uuid4().hex[:8]}", record_id, "example.com"),
            )
            conn.execute(
                """INSERT INTO aggregate_record_auth_results
                   (id, aggregate_record_id, auth_method, domain, selector, scope, result, human_result)
                   VALUES (?, ?, 'spf', ?, NULL, 'mfrom', 'pass', NULL)""",
                (f"auth_{uuid.uuid4().hex[:8]}", record_id, "bounce.example.com"),
            )
            conn.commit()
        finally:
            conn.close()

        backfill_missing_aggregate_alignment(path)
        result = search_records(config, {"id": "usr_super", "role": "super-admin", "username": "admin"})
        assert result["total"] == 1
        item = result["items"][0]
        assert item["dkim_alignment"] == "strict"
        assert item["spf_alignment"] == "relaxed"
        assert item["dmarc_alignment"] == "pass"
    finally:
        os.unlink(path)
