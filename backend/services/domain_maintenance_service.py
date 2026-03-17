"""Domain maintenance jobs: enqueue, list, detail, and background recompute work."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.services.dmarc_alignment import compute_aggregate_alignment, load_record_auth_results
from backend.storage.sqlite import get_connection

JOB_ID_PREFIX = "dmjob_"
ACTION_RECOMPUTE_AGGREGATE_REPORTS = "recompute_aggregate_reports"
STATE_QUEUED = "queued"
STATE_PROCESSING = "processing"
STATE_COMPLETED = "completed"
STATE_COMPLETED_WITH_WARNINGS = "completed_with_warnings"
STATE_FAILED = "failed"
ROLE_SUPER_ADMIN = "super-admin"
ROLE_ADMIN = "admin"


def _write_audit_event(
    database_path: str,
    *,
    action_type: str,
    outcome: str,
    actor_user_id: str,
    summary: str,
) -> None:
    event_id = f"aud_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO audit_log
               (id, timestamp, actor_type, actor_user_id, actor_api_key_id, action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, 'user', ?, NULL, ?, ?, NULL, NULL, ?, NULL)""",
            (event_id, timestamp, actor_user_id, action_type, outcome, summary),
        )
        conn.commit()
    finally:
        conn.close()


def _serialize_job(row: Any) -> dict[str, Any]:
    return {
        "job_id": row[0],
        "domain_id": row[1],
        "domain_name": row[2],
        "action": row[3],
        "actor_user_id": row[4],
        "submitted_at": row[5],
        "started_at": row[6],
        "completed_at": row[7],
        "state": row[8],
        "reports_scanned": row[9],
        "reports_skipped": row[10],
        "records_updated": row[11],
        "last_error": row[12],
        "summary": row[13],
    }


def _get_domain_for_actor(
    config: Config,
    *,
    actor: dict[str, Any],
    domain_id: str,
) -> tuple[str, dict[str, Any] | None]:
    role = actor.get("role") or ""
    actor_user_id = actor.get("id") or ""
    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            "SELECT id, name, status, created_at, archived_at FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()
        if not row:
            return "not_found", None

        domain = {
            "id": row[0],
            "name": row[1],
            "status": row[2],
            "created_at": row[3],
            "archived_at": row[4],
        }
        if role == ROLE_SUPER_ADMIN:
            return "ok", domain
        if role != ROLE_ADMIN:
            return "forbidden", None
        if domain["status"] != "active":
            return "forbidden", None

        assignment = conn.execute(
            "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
            (actor_user_id, domain_id),
        ).fetchone()
        if not assignment:
            return "forbidden", None
        return "ok", domain
    finally:
        conn.close()


def _get_job_for_actor(
    config: Config,
    *,
    actor: dict[str, Any],
    job_id: str,
) -> tuple[str, dict[str, Any] | None]:
    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE id = ?""",
            (job_id,),
        ).fetchone()
        if not row:
            return "not_found", None
        job = _serialize_job(row)
    finally:
        conn.close()

    access_status, _domain = _get_domain_for_actor(config, actor=actor, domain_id=job["domain_id"])
    if access_status != "ok":
        return access_status, None
    return "ok", job


def enqueue_recompute_job(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    access_status, domain = _get_domain_for_actor(config, actor=actor, domain_id=domain_id)
    if access_status != "ok" or domain is None:
        return access_status, None

    conn = get_connection(config.database_path)
    try:
        existing = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE domain_id = ? AND action = ? AND state IN (?, ?)
               ORDER BY submitted_at DESC
               LIMIT 1""",
            (
                domain_id,
                ACTION_RECOMPUTE_AGGREGATE_REPORTS,
                STATE_QUEUED,
                STATE_PROCESSING,
            ),
        ).fetchone()
        if existing:
            return "conflict", _serialize_job(existing)

        job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:14]}"
        submitted_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO domain_maintenance_jobs
               (id, domain_id, domain_name, action, actor_user_id, submitted_at, state, reports_scanned, reports_skipped, records_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
            (
                job_id,
                domain["id"],
                domain["name"],
                ACTION_RECOMPUTE_AGGREGATE_REPORTS,
                actor["id"],
                submitted_at,
                STATE_QUEUED,
            ),
        )
        conn.commit()
        job = {
            "job_id": job_id,
            "domain_id": domain["id"],
            "domain_name": domain["name"],
            "action": ACTION_RECOMPUTE_AGGREGATE_REPORTS,
            "actor_user_id": actor["id"],
            "submitted_at": submitted_at,
            "started_at": None,
            "completed_at": None,
            "state": STATE_QUEUED,
            "reports_scanned": 0,
            "reports_skipped": 0,
            "records_updated": 0,
            "last_error": None,
            "summary": None,
        }
    finally:
        conn.close()

    _write_audit_event(
        config.database_path,
        action_type="domain_maintenance_job_enqueued",
        outcome="success",
        actor_user_id=actor["id"],
        summary=f"Enqueued {ACTION_RECOMPUTE_AGGREGATE_REPORTS} for {domain['name']}",
    )
    return "ok", job


def list_domain_jobs(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
    limit: int = 20,
) -> tuple[str, list[dict[str, Any]] | None]:
    access_status, _domain = _get_domain_for_actor(config, actor=actor, domain_id=domain_id)
    if access_status != "ok":
        return access_status, None

    limit = min(max(1, limit), 100)
    conn = get_connection(config.database_path)
    try:
        rows = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE domain_id = ?
               ORDER BY submitted_at DESC
               LIMIT ?""",
            (domain_id, limit),
        ).fetchall()
        return "ok", [_serialize_job(row) for row in rows]
    finally:
        conn.close()


def get_job_detail(
    config: Config,
    *,
    job_id: str,
    actor: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    return _get_job_for_actor(config, actor=actor, job_id=job_id)


def get_latest_job_for_domain(config: Config, *, domain_id: str) -> dict[str, Any] | None:
    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE domain_id = ?
               ORDER BY submitted_at DESC
               LIMIT 1""",
            (domain_id,),
        ).fetchone()
        return _serialize_job(row) if row else None
    finally:
        conn.close()


def claim_next_job(config: Config) -> dict[str, Any] | None:
    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE state IN (?, ?)
               ORDER BY submitted_at
               LIMIT 1""",
            (STATE_QUEUED, STATE_PROCESSING),
        ).fetchone()
        if not row:
            return None
        started_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """UPDATE domain_maintenance_jobs
               SET state = ?, started_at = ?, completed_at = NULL, last_error = NULL, summary = NULL,
                   reports_scanned = 0, reports_skipped = 0, records_updated = 0
               WHERE id = ?""",
            (STATE_PROCESSING, started_at, row[0]),
        )
        conn.commit()
        refreshed = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE id = ?""",
            (row[0],),
        ).fetchone()
        return _serialize_job(refreshed) if refreshed else None
    finally:
        conn.close()


def process_job(config: Config, *, job_id: str) -> None:
    conn = get_connection(config.database_path)
    try:
        job_row = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id
               FROM domain_maintenance_jobs
               WHERE id = ?""",
            (job_id,),
        ).fetchone()
        if not job_row:
            return
        domain_row = conn.execute(
            "SELECT id, name FROM domains WHERE id = ?",
            (job_row[1],),
        ).fetchone()
        if not domain_row:
            conn.execute(
                """UPDATE domain_maintenance_jobs
                   SET state = ?, completed_at = ?, last_error = ?, summary = ?
                   WHERE id = ?""",
                (
                    STATE_FAILED,
                    datetime.now(timezone.utc).isoformat(),
                    "domain_not_found",
                    "The target domain no longer exists.",
                    job_id,
                ),
            )
            conn.commit()
            actor_user_id = job_row[4]
        else:
            actor_user_id = job_row[4]
    finally:
        conn.close()

    if not domain_row:
        _write_audit_event(
            config.database_path,
            action_type="domain_maintenance_job_failed",
            outcome="failure",
            actor_user_id=actor_user_id,
            summary=f"Maintenance job {job_id} failed because the target domain no longer exists",
        )
        return

    try:
        counts = _recompute_domain_aggregate_alignment(config, domain_id=domain_row[0], domain_name=domain_row[1], job_id=job_id)
        completed_at = datetime.now(timezone.utc).isoformat()
        state = STATE_COMPLETED if counts["reports_scanned"] else STATE_COMPLETED_WITH_WARNINGS
        summary = (
            f"Recomputed aggregate alignment for {counts['records_updated']} records across {counts['reports_scanned']} reports."
            if counts["reports_scanned"]
            else "No aggregate reports were available to recompute for this domain."
        )
        conn = get_connection(config.database_path)
        try:
            conn.execute(
                """UPDATE domain_maintenance_jobs
                   SET state = ?, completed_at = ?, reports_scanned = ?, reports_skipped = ?, records_updated = ?, summary = ?, last_error = NULL
                   WHERE id = ?""",
                (
                    state,
                    completed_at,
                    counts["reports_scanned"],
                    counts["reports_skipped"],
                    counts["records_updated"],
                    summary,
                    job_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        _write_audit_event(
            config.database_path,
            action_type="domain_maintenance_job_completed",
            outcome="success",
            actor_user_id=actor_user_id,
            summary=f"Maintenance job {job_id} completed for {domain_row[1]}",
        )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        conn = get_connection(config.database_path)
        try:
            conn.execute(
                """UPDATE domain_maintenance_jobs
                   SET state = ?, completed_at = ?, last_error = ?, summary = ?
                   WHERE id = ?""",
                (
                    STATE_FAILED,
                    completed_at,
                    str(exc),
                    "Failed while recomputing aggregate report alignment.",
                    job_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        _write_audit_event(
            config.database_path,
            action_type="domain_maintenance_job_failed",
            outcome="failure",
            actor_user_id=actor_user_id,
            summary=f"Maintenance job {job_id} failed for {domain_row[1]}",
        )
        raise


def run_one_job(config: Config) -> bool:
    job = claim_next_job(config)
    if not job:
        return False
    process_job(config, job_id=job["job_id"])
    return True


def _recompute_domain_aggregate_alignment(
    config: Config,
    *,
    domain_id: str,
    domain_name: str,
    job_id: str,
) -> dict[str, int]:
    del domain_id  # persisted for future action types; current recompute is keyed by stored domain name.

    conn = get_connection(config.database_path)
    try:
        reports = conn.execute(
            """SELECT id, adkim, aspf
               FROM aggregate_reports
               WHERE domain = ?
               ORDER BY created_at, id""",
            (domain_name,),
        ).fetchall()
        reports_scanned = 0
        records_updated = 0
        reports_skipped = 0

        for report_id, adkim, aspf in reports:
            reports_scanned += 1
            record_rows = conn.execute(
                """SELECT id, header_from, envelope_from, dkim_result, spf_result
                   FROM aggregate_report_records
                   WHERE aggregate_report_id = ?
                   ORDER BY id""",
                (report_id,),
            ).fetchall()
            if not record_rows:
                reports_skipped += 1
            for record_id, header_from, envelope_from, dkim_result, spf_result in record_rows:
                auth_results = load_record_auth_results(conn, record_id)
                alignment = compute_aggregate_alignment(
                    header_from=header_from,
                    envelope_from=envelope_from,
                    dkim_result=dkim_result,
                    spf_result=spf_result,
                    auth_results=auth_results,
                    adkim=adkim,
                    aspf=aspf,
                )
                conn.execute(
                    """UPDATE aggregate_report_records
                       SET dkim_alignment = ?, spf_alignment = ?, dmarc_alignment = ?
                       WHERE id = ?""",
                    (
                        alignment["dkim_alignment"],
                        alignment["spf_alignment"],
                        alignment["dmarc_alignment"],
                        record_id,
                    ),
                )
                records_updated += 1
            conn.execute(
                """UPDATE domain_maintenance_jobs
                   SET reports_scanned = ?, reports_skipped = ?, records_updated = ?
                   WHERE id = ?""",
                (reports_scanned, reports_skipped, records_updated, job_id),
            )
        conn.commit()
        return {
            "reports_scanned": reports_scanned,
            "reports_skipped": reports_skipped,
            "records_updated": records_updated,
        }
    finally:
        conn.close()
