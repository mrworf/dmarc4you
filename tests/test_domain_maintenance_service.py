import tempfile

from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.config.schema import Config
from backend.services import domain_maintenance_service
from backend.services.domain_service import archive_domain, create_domain
from backend.storage.sqlite import get_connection, run_migrations


def _make_config(database_path: str) -> Config:
    return Config(
        database_path=database_path,
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )


def _insert_user(database_path: str, *, user_id: str, username: str, role: str, created_by_user_id: str) -> None:
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)""",
            (user_id, username, hash_password("pass"), role, "2026-01-01T00:00:00Z", created_by_user_id),
        )
        conn.commit()
    finally:
        conn.close()


def _assign_domain(database_path: str, *, user_id: str, domain_id: str, assigned_by_user_id: str) -> None:
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, domain_id, assigned_by_user_id, "2026-01-01T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_aggregate_record_with_unknown_alignment(database_path: str, *, domain_name: str) -> None:
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO aggregate_reports
               (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at, adkim, aspf, error_messages_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]')""",
            ("agg_1", "report-1", "Example Org", domain_name, 1735689600, 1735776000, "item_1", "2026-01-02T00:00:00Z", "r", "r"),
        )
        conn.execute(
            """INSERT INTO aggregate_report_records
               (id, aggregate_report_id, source_ip, count, disposition, dkim_result, spf_result, dkim_alignment, spf_alignment, dmarc_alignment, header_from, envelope_from, envelope_to)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("rec_1", "agg_1", "192.0.2.44", 1, "none", "fail", "pass", "none", "unknown", "unknown", domain_name, None, None),
        )
        conn.execute(
            """INSERT INTO aggregate_record_auth_results
               (id, aggregate_record_id, auth_method, domain, selector, scope, result, human_result)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("auth_1", "rec_1", "spf", domain_name, None, None, "pass", None),
        )
        conn.commit()
    finally:
        conn.close()


def test_enqueue_recompute_job_enforces_domain_access_and_duplicate_block() -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)

    conn = get_connection(handle.name)
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    conn.close()
    status, domain = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    assert domain is not None

    _insert_user(handle.name, user_id="usr_admin2", username="admin2", role="admin", created_by_user_id=admin_id)
    _insert_user(handle.name, user_id="usr_viewer", username="viewer", role="viewer", created_by_user_id=admin_id)
    _assign_domain(handle.name, user_id="usr_admin2", domain_id=domain["id"], assigned_by_user_id=admin_id)

    ok_status, ok_job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": "usr_admin2", "role": "admin"},
    )
    assert ok_status == "ok"
    assert ok_job is not None
    assert ok_job["state"] == "queued"

    conflict_status, conflict_job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": admin_id, "role": "super-admin"},
    )
    assert conflict_status == "conflict"
    assert conflict_job is not None
    assert conflict_job["job_id"] == ok_job["job_id"]

    forbidden_status, _ = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": "usr_viewer", "role": "viewer"},
    )
    assert forbidden_status == "forbidden"


def test_recompute_job_updates_existing_aggregate_alignment_and_is_idempotent() -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)

    conn = get_connection(handle.name)
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    conn.close()
    status, domain = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    assert domain is not None
    _insert_aggregate_record_with_unknown_alignment(handle.name, domain_name=domain["name"])

    enqueue_status, job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": admin_id, "role": "super-admin"},
    )
    assert enqueue_status == "ok"
    assert job is not None
    assert domain_maintenance_service.run_one_job(config) is True

    conn = get_connection(handle.name)
    try:
        row = conn.execute(
            """SELECT dkim_alignment, spf_alignment, dmarc_alignment
               FROM aggregate_report_records
               WHERE id = 'rec_1'"""
        ).fetchone()
        job_row = conn.execute(
            """SELECT state, reports_scanned, records_updated
               FROM domain_maintenance_jobs
               WHERE id = ?""",
            (job["job_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("none", "strict", "pass")
    assert job_row == ("completed", 1, 1)

    enqueue_status_2, second_job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": admin_id, "role": "super-admin"},
    )
    assert enqueue_status_2 == "ok"
    assert second_job is not None
    assert domain_maintenance_service.run_one_job(config) is True

    conn = get_connection(handle.name)
    try:
        second_job_row = conn.execute(
            """SELECT state, reports_scanned, records_updated
               FROM domain_maintenance_jobs
               WHERE id = ?""",
            (second_job["job_id"],),
        ).fetchone()
    finally:
        conn.close()

    assert second_job_row == ("completed", 1, 1)


def test_admin_cannot_enqueue_recompute_for_archived_domain() -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)

    conn = get_connection(handle.name)
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    conn.close()
    status, domain = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    assert domain is not None

    _insert_user(handle.name, user_id="usr_admin2", username="admin2", role="admin", created_by_user_id=admin_id)
    _assign_domain(handle.name, user_id="usr_admin2", domain_id=domain["id"], assigned_by_user_id=admin_id)
    archive_status, _archived = archive_domain(config, domain["id"], admin_id, "super-admin")
    assert archive_status == "ok"

    admin_status, _ = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": "usr_admin2", "role": "admin"},
    )
    assert admin_status == "forbidden"

    super_admin_status, job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain["id"],
        actor={"id": admin_id, "role": "super-admin"},
    )
    assert super_admin_status == "ok"
    assert job is not None
