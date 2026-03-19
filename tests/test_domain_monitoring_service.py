import tempfile

from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.config.schema import Config
from backend.services import domain_monitoring_service
from backend.storage.sqlite import get_connection, run_migrations


def _make_config(database_path: str) -> Config:
    return Config(
        database_path=database_path,
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )


def _setup_domain(database_path: str, *, enabled: bool = True) -> tuple[str, str]:
    conn = get_connection(database_path)
    try:
        admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
        domain_id = "dom_monitoring"
        conn.execute(
            """INSERT INTO domains
               (id, name, status, created_at, archived_at, archived_by_user_id, retention_days, retention_delete_at,
                retention_paused, retention_paused_at, retention_pause_reason, retention_remaining_seconds,
                monitoring_enabled, monitoring_last_checked_at, monitoring_next_check_at, monitoring_last_change_at,
                monitoring_last_triggered_at, monitoring_failure_active, monitoring_last_failure_at, monitoring_last_failure_summary)
               VALUES (?, 'example.com', 'active', '2026-01-01T00:00:00Z', NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, ?, NULL, NULL, NULL, NULL, 0, NULL, NULL)""",
            (domain_id, 1 if enabled else 0),
        )
        conn.commit()
        return admin_id, domain_id
    finally:
        conn.close()


def _insert_job(database_path: str, *, job_id: str, domain_id: str, actor_user_id: str | None) -> None:
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO domain_maintenance_jobs
               (id, domain_id, domain_name, action, actor_user_id, actor_api_key_id, submitted_at, state, reports_scanned, reports_skipped, records_updated)
               VALUES (?, ?, 'example.com', ?, ?, NULL, '2026-01-01T00:00:00Z', 'queued', 0, 0, 0)""",
            (job_id, domain_id, domain_monitoring_service.ACTION_CHECK_DNS_MONITORING, actor_user_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_run_monitoring_job_records_initial_snapshot_and_history(monkeypatch) -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)
    admin_id, domain_id = _setup_domain(handle.name)
    _insert_job(handle.name, job_id="dmjob_1", domain_id=domain_id, actor_user_id=admin_id)

    def fake_resolve(_config: Config, host: str):
        if host == "_dmarc.example.com":
            return (["v=DMARC1; p=reject; rua=mailto:dmarc@example.com"], 600, domain_monitoring_service.DNS_RESULT_OK, None)
        if host == "example.com":
            return (["v=spf1 include:_spf.example.net -all"], 300, domain_monitoring_service.DNS_RESULT_OK, None)
        return (["v=DKIM1; k=rsa; p=abc123"], 120, domain_monitoring_service.DNS_RESULT_OK, None)

    monkeypatch.setattr(domain_monitoring_service, "_resolve_txt_records", fake_resolve)

    counts = domain_monitoring_service.run_monitoring_job(config, job_id="dmjob_1")

    assert counts == {"reports_scanned": 1, "reports_skipped": 0, "records_updated": 1}

    conn = get_connection(handle.name)
    try:
        current = conn.execute(
            "SELECT ttl_seconds, error_summary FROM domain_monitoring_current_state WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()
        history = conn.execute(
            "SELECT COUNT(*) FROM domain_monitoring_history WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()[0]
        domain = conn.execute(
            """SELECT monitoring_last_checked_at, monitoring_next_check_at, monitoring_failure_active
               FROM domains WHERE id = ?""",
            (domain_id,),
        ).fetchone()
    finally:
        conn.close()

    assert current == (120, None)
    assert history == 1
    assert domain is not None and domain[0] is not None and domain[1] is not None and domain[2] == 0


def test_failure_streak_logs_only_once_until_success(monkeypatch) -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)
    admin_id, domain_id = _setup_domain(handle.name)

    states = [
        lambda _config, host: ([], None, domain_monitoring_service.DNS_RESULT_ERROR, f"{host}: timeout"),
        lambda _config, host: ([], None, domain_monitoring_service.DNS_RESULT_ERROR, f"{host}: timeout"),
        lambda _config, host: (
            ["v=DMARC1; p=quarantine"] if host == "_dmarc.example.com" else ["v=spf1 -all"],
            300,
            domain_monitoring_service.DNS_RESULT_OK,
            None,
        ),
        lambda _config, host: ([], None, domain_monitoring_service.DNS_RESULT_ERROR, f"{host}: timeout"),
    ]

    for index, resolver in enumerate(states, start=1):
        monkeypatch.setattr(domain_monitoring_service, "_resolve_txt_records", resolver)
        job_id = f"dmjob_{index}"
        _insert_job(handle.name, job_id=job_id, domain_id=domain_id, actor_user_id=admin_id)
        domain_monitoring_service.run_monitoring_job(config, job_id=job_id)

    conn = get_connection(handle.name)
    try:
        failure_events = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action_type = 'domain_monitoring_check_failed'",
        ).fetchone()[0]
        domain = conn.execute(
            "SELECT monitoring_failure_active FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()
    finally:
        conn.close()

    assert failure_events == 2
    assert domain == (1,)


def test_unchanged_poll_updates_last_checked_without_adding_history(monkeypatch) -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)
    admin_id, domain_id = _setup_domain(handle.name)

    def fake_resolve(_config: Config, host: str):
        if host == "_dmarc.example.com":
            return (["v=DMARC1; p=reject"], 600, domain_monitoring_service.DNS_RESULT_OK, None)
        if host == "example.com":
            return (["v=spf1 -all"], 300, domain_monitoring_service.DNS_RESULT_OK, None)
        return (["v=DKIM1; k=rsa; p=abc123"], 120, domain_monitoring_service.DNS_RESULT_OK, None)

    monkeypatch.setattr(domain_monitoring_service, "_resolve_txt_records", fake_resolve)

    _insert_job(handle.name, job_id="dmjob_1", domain_id=domain_id, actor_user_id=admin_id)
    domain_monitoring_service.run_monitoring_job(config, job_id="dmjob_1")

    conn = get_connection(handle.name)
    try:
        first_checked = conn.execute(
            "SELECT monitoring_last_checked_at FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE domains SET monitoring_last_checked_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (domain_id,),
        )
        conn.execute(
            "UPDATE domain_monitoring_current_state SET checked_at = '2020-01-01T00:00:00Z' WHERE domain_id = ?",
            (domain_id,),
        )
        conn.commit()
    finally:
        conn.close()

    _insert_job(handle.name, job_id="dmjob_2", domain_id=domain_id, actor_user_id=admin_id)
    counts = domain_monitoring_service.run_monitoring_job(config, job_id="dmjob_2")
    assert counts["records_updated"] == 0

    conn = get_connection(handle.name)
    try:
        history_count = conn.execute(
            "SELECT COUNT(*) FROM domain_monitoring_history WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()[0]
        last_checked = conn.execute(
            "SELECT monitoring_last_checked_at FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert history_count == 1
    assert last_checked is not None
    assert last_checked != "2020-01-01T00:00:00Z"
    assert last_checked != first_checked


def test_classify_timeline_change_marks_degraded_and_improved_cases() -> None:
    degraded_direction, degraded_changes = domain_monitoring_service.classify_timeline_change(
        {
            "dmarc": {"raw_value": "v=DMARC1; p=reject", "parsed": {"p": "reject"}},
            "spf": {"raw_value": "v=spf1 -all", "parsed": {"qualifier": "fail", "includes": []}},
            "dkim": [{"raw_value": "v=DKIM1; p=abc", "parsed": {"selector": "s1", "has_key": True}}],
        },
        {
            "dmarc": {"raw_value": "v=DMARC1; p=none", "parsed": {"p": "none"}},
            "spf": {"raw_value": "v=spf1 +all", "parsed": {"qualifier": "allow_all", "includes": []}},
            "dkim": [{"raw_value": None, "parsed": {"selector": "s1", "has_key": False}}],
        },
    )

    improved_direction, improved_changes = domain_monitoring_service.classify_timeline_change(
        {
            "dmarc": {"raw_value": "v=DMARC1; p=none", "parsed": {"p": "none"}},
            "spf": {"raw_value": "v=spf1 ~all", "parsed": {"qualifier": "softfail", "includes": ["include:a"]}},
            "dkim": [{"raw_value": None, "parsed": {"selector": "s1", "has_key": False}}],
        },
        {
            "dmarc": {"raw_value": "v=DMARC1; p=reject", "parsed": {"p": "reject"}},
            "spf": {"raw_value": "v=spf1 -all", "parsed": {"qualifier": "fail", "includes": []}},
            "dkim": [{"raw_value": "v=DKIM1; p=abc", "parsed": {"selector": "s1", "has_key": True}}],
        },
    )

    assert degraded_direction == "degraded"
    assert any(change["direction"] == "degraded" for change in degraded_changes)
    assert improved_direction == "improved"
    assert any(change["direction"] == "improved" for change in improved_changes)


def test_timeout_does_not_update_last_checked_or_create_history(monkeypatch) -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = _make_config(handle.name)
    admin_id, domain_id = _setup_domain(handle.name)

    conn = get_connection(handle.name)
    try:
        conn.execute(
            """INSERT INTO domain_monitoring_current_state
               (domain_id, checked_at, observed_state_json, dmarc_record_raw, spf_record_raw, dkim_records_json, ttl_seconds, error_summary)
               VALUES (?, '2026-01-02T00:00:00Z', ?, 'v=DMARC1; p=reject', 'v=spf1 -all', '[]', 300, NULL)""",
            (domain_id, '{"dmarc":{"status":"ok","raw_value":"v=DMARC1; p=reject"},"spf":{"status":"ok","raw_value":"v=spf1 -all"},"dkim":[]}'),
        )
        conn.execute(
            """UPDATE domains
               SET monitoring_last_checked_at = '2026-01-02T00:00:00Z'
               WHERE id = ?""",
            (domain_id,),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setattr(
        domain_monitoring_service,
        "_resolve_txt_records",
        lambda _config, host: ([], None, domain_monitoring_service.DNS_RESULT_ERROR, f"{host}: timeout"),
    )

    _insert_job(handle.name, job_id="dmjob_timeout", domain_id=domain_id, actor_user_id=admin_id)
    counts = domain_monitoring_service.run_monitoring_job(config, job_id="dmjob_timeout")
    assert counts["records_updated"] == 0

    conn = get_connection(handle.name)
    try:
        row = conn.execute(
            "SELECT monitoring_last_checked_at, monitoring_last_failure_summary FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()
        history_count = conn.execute(
            "SELECT COUNT(*) FROM domain_monitoring_history WHERE domain_id = ?",
            (domain_id,),
        ).fetchone()[0]
    finally:
        conn.close()

    assert row == ("2026-01-02T00:00:00Z", "_dmarc.example.com: timeout; example.com: timeout")
    assert history_count == 0


def test_restored_missing_record_creates_restore_event() -> None:
    direction, changes = domain_monitoring_service.classify_timeline_change(
        {
            "dmarc": {"status": domain_monitoring_service.DNS_RESULT_MISSING, "raw_value": None, "parsed": {}},
            "spf": {"status": domain_monitoring_service.DNS_RESULT_OK, "raw_value": "v=spf1 -all", "parsed": {"qualifier": "fail", "includes": []}},
            "dkim": [],
        },
        {
            "dmarc": {"status": domain_monitoring_service.DNS_RESULT_OK, "raw_value": "v=DMARC1; p=reject", "parsed": {"p": "reject"}},
            "spf": {"status": domain_monitoring_service.DNS_RESULT_OK, "raw_value": "v=spf1 -all", "parsed": {"qualifier": "fail", "includes": []}},
            "dkim": [],
        },
    )

    assert direction == "improved"
    assert changes[0]["label"] == "DMARC record restored"
