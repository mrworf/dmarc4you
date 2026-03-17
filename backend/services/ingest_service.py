"""Ingest service: create_ingest_job, get_job_detail."""

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection

JOB_ID_PREFIX = "job_"
ITEM_ID_PREFIX = "item_"


def create_ingest_job(
    config: Config,
    envelope: dict,
    actor_type: str,
    actor_user_id: str | None = None,
    actor_api_key_id: str | None = None,
) -> str:
    """Create job (queued) and one item per report. Return job_id. actor_type is 'user' or 'api_key'."""
    reports = envelope.get("reports") or []
    if not reports:
        reports = []
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:14]}"
    submitted_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """INSERT INTO ingest_jobs (id, actor_type, actor_user_id, actor_api_key_id, submitted_at, started_at, completed_at, state, last_error, retry_count)
               VALUES (?, ?, ?, ?, ?, NULL, NULL, 'queued', NULL, 0)""",
            (job_id, actor_type, actor_user_id, actor_api_key_id, submitted_at),
        )
        for i, rep in enumerate(reports):
            item_id = f"{ITEM_ID_PREFIX}{uuid.uuid4().hex[:12]}"
            content = rep.get("content") or ""
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="replace")
            conn.execute(
                """INSERT INTO ingest_job_items (id, job_id, sequence_no, raw_content_type, raw_content_encoding, raw_content_transfer_encoding, raw_content, report_type_detected, domain_detected, status, status_reason, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL)""",
                (
                    item_id,
                    job_id,
                    i,
                    rep.get("content_type") or None,
                    rep.get("content_encoding") or None,
                    rep.get("content_transfer_encoding") or None,
                    content,
                ),
            )
        conn.commit()
        return job_id
    finally:
        conn.close()


def list_jobs(
    config: Config,
    actor_user_id: str | None = None,
    actor_api_key_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return jobs: by actor_user_id or by actor_api_key_id. Ordered by submitted_at desc, up to limit."""
    limit = min(max(1, limit), 100)
    conn = get_connection(config.database_path)
    try:
        if actor_api_key_id is not None:
            cur = conn.execute(
                """SELECT id, state, submitted_at FROM ingest_jobs
                   WHERE actor_api_key_id = ? ORDER BY submitted_at DESC LIMIT ?""",
                (actor_api_key_id, limit),
            )
        else:
            cur = conn.execute(
                """SELECT id, state, submitted_at FROM ingest_jobs
                   WHERE actor_user_id = ? ORDER BY submitted_at DESC LIMIT ?""",
                (actor_user_id, limit),
            )
        return [
            {"job_id": row[0], "state": row[1], "submitted_at": row[2]}
            for row in cur.fetchall()
        ]
    finally:
        conn.close()


def get_job_detail(
    config: Config,
    job_id: str,
    actor_user_id: str | None = None,
    actor_api_key_id: str | None = None,
) -> dict[str, Any] | None:
    """Return job with items if job exists and caller is owner (by user_id or api_key_id); else None."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, actor_type, actor_user_id, actor_api_key_id, submitted_at, started_at, completed_at, state, last_error, retry_count FROM ingest_jobs WHERE id = ?",
            (job_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        job_actor_user_id = row[2]
        job_actor_api_key_id = row[3]
        if actor_api_key_id is not None:
            if job_actor_api_key_id != actor_api_key_id:
                return None
        else:
            if job_actor_user_id != actor_user_id:
                return None
        job = {
            "job_id": row[0],
            "actor_type": row[1],
            "actor_user_id": job_actor_user_id,
            "submitted_at": row[4],
            "started_at": row[5],
            "completed_at": row[6],
            "state": row[7],
            "last_error": row[8],
            "retry_count": row[9],
        }
        cur = conn.execute(
            """SELECT id, job_id, sequence_no, report_type_detected, domain_detected, status, status_reason FROM ingest_job_items WHERE job_id = ? ORDER BY sequence_no""",
            (job_id,),
        )
        items = []
        for r in cur.fetchall():
            normalized_report_id = None
            normalized_report_kind = None
            aggregate_row = conn.execute(
                "SELECT id FROM aggregate_reports WHERE job_item_id = ? LIMIT 1",
                (r[0],),
            ).fetchone()
            if aggregate_row:
                normalized_report_id = aggregate_row[0]
                normalized_report_kind = "aggregate"
            else:
                forensic_row = conn.execute(
                    "SELECT id FROM forensic_reports WHERE job_item_id = ? LIMIT 1",
                    (r[0],),
                ).fetchone()
                if forensic_row:
                    normalized_report_id = forensic_row[0]
                    normalized_report_kind = "forensic"
            items.append({
                "item_id": r[0],
                "job_id": r[1],
                "sequence_no": r[2],
                "report_type_detected": r[3],
                "domain_detected": r[4],
                "status": r[5],
                "status_reason": r[6],
                "normalized_report_id": normalized_report_id,
                "normalized_report_kind": normalized_report_kind,
            })
        job["items"] = items
        job["accepted_count"] = sum(1 for i in items if i.get("status") == "accepted")
        job["duplicate_count"] = sum(1 for i in items if i.get("status") == "duplicate")
        job["invalid_count"] = sum(1 for i in items if i.get("status") == "invalid")
        job["rejected_count"] = sum(1 for i in items if i.get("status") == "rejected")
        return job
    finally:
        conn.close()
