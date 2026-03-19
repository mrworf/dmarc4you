"""Domain service: create_domain, list_domains (scoped), get_domain_ids_for_user (for /me)."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.config.schema import Config
from backend.policies.domain_policy import can_create_domain, can_archive_domain, can_restore_domain, can_delete_domain
from backend.services import domain_maintenance_service, domain_monitoring_service
from backend.storage.sqlite import get_connection
from backend.archive.filesystem import FilesystemArchiveStorage

DOMAIN_ID_PREFIX = "dom_"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"
ROLE_SUPER_ADMIN = "super-admin"


def create_domain(config: Config, name: str, actor_user_id: str, actor_role: str) -> tuple[str, dict[str, Any] | None]:
    """Create domain if actor is super-admin. Return ('ok', domain), ('forbidden', None), or ('duplicate', None)."""
    if not can_create_domain({"role": actor_role}):
        return "forbidden", None
    name = (name or "").strip()
    if not name:
        return "invalid", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT 1 FROM domains WHERE name = ?", (name,))
        if cur.fetchone():
            return "duplicate", None
        domain_id = f"{DOMAIN_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO domains (id, name, status, created_at, archived_at, archived_by_user_id,
               retention_days, retention_delete_at, retention_paused, retention_paused_at, retention_pause_reason, retention_remaining_seconds)
               VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL)""",
            (domain_id, name, STATUS_ACTIVE, created_at),
        )
        conn.commit()
        return "ok", {"id": domain_id, "name": name, "status": STATUS_ACTIVE, "created_at": created_at}
    finally:
        conn.close()


def list_domains(config: Config, current_user: dict[str, Any]) -> list[dict[str, Any]]:
    """List domains visible to current user: super-admin sees all (active + archived); others see only assigned active."""
    conn = get_connection(config.database_path)
    try:
        if current_user.get("role") == ROLE_SUPER_ADMIN:
            cur = conn.execute(
                """SELECT id, name, status, created_at, archived_at, retention_days, retention_delete_at, retention_paused,
                          retention_remaining_seconds, monitoring_enabled, monitoring_last_checked_at,
                          monitoring_next_check_at, monitoring_last_change_at, monitoring_failure_active,
                          monitoring_last_failure_at, monitoring_last_failure_summary
                   FROM domains
                   ORDER BY name""",
                (),
            )
        else:
            cur = conn.execute(
                """SELECT d.id, d.name, d.status, d.created_at, d.archived_at, d.retention_days, d.retention_delete_at, d.retention_paused,
                          d.retention_remaining_seconds, d.monitoring_enabled, d.monitoring_last_checked_at,
                          d.monitoring_next_check_at, d.monitoring_last_change_at, d.monitoring_failure_active,
                          d.monitoring_last_failure_at, d.monitoring_last_failure_summary
                   FROM domains d
                   INNER JOIN user_domain_assignments a ON a.domain_id = d.id
                   WHERE a.user_id = ? AND d.status = ? ORDER BY d.name""",
                (current_user["id"], STATUS_ACTIVE),
            )
        rows = cur.fetchall()
        items = []
        for r in rows:
            item = {
                "id": r[0],
                "name": r[1],
                "status": r[2],
                "created_at": r[3],
                "archived_at": r[4],
                "retention_days": r[5],
                "retention_delete_at": r[6],
                "retention_paused": r[7] if r[7] is not None else 0,
                "retention_remaining_seconds": r[8],
                "monitoring_enabled": r[9] if r[9] is not None else 0,
                "monitoring_last_checked_at": r[10],
                "monitoring_next_check_at": r[11],
                "monitoring_last_change_at": r[12],
                "monitoring_failure_active": r[13] if r[13] is not None else 0,
                "monitoring_last_failure_at": r[14],
                "monitoring_last_failure_summary": r[15],
            }
            latest_job = domain_maintenance_service.get_latest_job_for_domain(config, domain_id=r[0])
            if latest_job:
                item["latest_maintenance_job"] = latest_job
            items.append(item)
        return items
    finally:
        conn.close()


def archive_domain(
    config: Config,
    domain_id: str,
    actor_user_id: str,
    actor_role: str,
    retention_days: int | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """Archive domain (super-admin only). Optional retention_days sets retention_delete_at. Return ('ok', domain), ('forbidden', None), ('not_found', None), ('already_archived', None)."""
    if not can_archive_domain({"role": actor_role}):
        return "forbidden", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, name, status, created_at FROM domains WHERE id = ?", (domain_id,))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] == STATUS_ARCHIVED:
            return "already_archived", None
        archived_at = datetime.now(timezone.utc).isoformat()
        retention_delete_at = None
        if retention_days is not None and retention_days > 0:
            archived_dt = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))
            retention_delete_at = (archived_dt + timedelta(days=retention_days)).isoformat()
        if retention_delete_at is not None:
            conn.execute(
                """UPDATE domains SET status = ?, archived_at = ?, archived_by_user_id = ?, retention_days = ?, retention_delete_at = ?
                   WHERE id = ?""",
                (STATUS_ARCHIVED, archived_at, actor_user_id, retention_days, retention_delete_at, domain_id),
            )
        else:
            conn.execute(
                "UPDATE domains SET status = ?, archived_at = ?, archived_by_user_id = ? WHERE id = ?",
                (STATUS_ARCHIVED, archived_at, actor_user_id, domain_id),
            )
        conn.commit()
        out = {"id": row[0], "name": row[1], "status": STATUS_ARCHIVED, "created_at": row[3], "archived_at": archived_at}
        if retention_delete_at is not None:
            out["retention_days"] = retention_days
            out["retention_delete_at"] = retention_delete_at
        return "ok", out
    finally:
        conn.close()


def restore_domain(config: Config, domain_id: str, actor_role: str) -> tuple[str, dict[str, Any] | None]:
    """Restore archived domain (super-admin only). Return ('ok', domain), ('forbidden', None), ('not_found', None), ('not_archived', None)."""
    if not can_restore_domain({"role": actor_role}):
        return "forbidden", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, name, status, created_at FROM domains WHERE id = ?", (domain_id,))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] != STATUS_ARCHIVED:
            return "not_archived", None
        conn.execute(
            "UPDATE domains SET status = ?, archived_at = NULL, archived_by_user_id = NULL WHERE id = ?",
            (STATUS_ACTIVE, domain_id),
        )
        conn.commit()
        return "ok", {"id": row[0], "name": row[1], "status": STATUS_ACTIVE, "created_at": row[3]}
    finally:
        conn.close()


def _purge_domain_data(config: Config, domain_id: str, domain_name: str) -> None:
    """Permanently remove domain and related data. Caller must ensure domain is archived (e.g. delete_domain or retention purge)."""
    conn = get_connection(config.database_path)
    try:
        conn.execute("DELETE FROM user_domain_assignments WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM dashboard_domain_scope WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM api_key_domains WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM domain_maintenance_jobs WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM domain_monitoring_dkim_selectors WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM domain_monitoring_current_state WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM domain_monitoring_history WHERE domain_id = ?", (domain_id,))
        conn.execute("DELETE FROM aggregate_reports WHERE domain = ?", (domain_name,))
        conn.execute("DELETE FROM forensic_reports WHERE domain = ?", (domain_name,))
        conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
        conn.commit()
    finally:
        conn.close()


def delete_domain(config: Config, domain_id: str, actor_role: str) -> tuple[str, None]:
    """Delete archived domain and related data (super-admin only). Return ('ok', None) or ('forbidden'|'not_found'|'not_archived', None)."""
    if not can_delete_domain({"role": actor_role}):
        return "forbidden", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, name, status FROM domains WHERE id = ?", (domain_id,))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] != STATUS_ARCHIVED:
            return "not_archived", None
        domain_name = row[1]
    finally:
        conn.close()
    _purge_domain_data(config, domain_id, domain_name)
    return "ok", None


def pause_retention(
    config: Config, domain_id: str, actor_role: str, reason: str | None = None
) -> tuple[str, dict[str, Any] | None]:
    """Pause retention for an archived domain with retention set. Super-admin only. Returns ('ok', domain) or ('forbidden'|'not_found'|'not_archived'|'no_retention'|'already_paused', None)."""
    if actor_role != ROLE_SUPER_ADMIN:
        return "forbidden", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, status, created_at, archived_at, retention_delete_at, retention_paused FROM domains WHERE id = ?",
            (domain_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] != STATUS_ARCHIVED:
            return "not_archived", None
        if not row[5]:  # retention_delete_at
            return "no_retention", None
        if row[6]:  # already paused
            return "already_paused", None
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        delete_at = datetime.fromisoformat(str(row[5]).replace("Z", "+00:00"))
        remaining_seconds = max(0, int((delete_at - now).total_seconds()))
        conn.execute(
            """UPDATE domains SET retention_paused = 1, retention_paused_at = ?, retention_pause_reason = ?, retention_remaining_seconds = ?
               WHERE id = ?""",
            (now_iso, (reason or "").strip() or None, remaining_seconds, domain_id),
        )
        conn.commit()
        out = {
            "id": row[0],
            "name": row[1],
            "status": STATUS_ARCHIVED,
            "created_at": row[3],
            "archived_at": row[4],
            "retention_paused": 1,
            "retention_remaining_seconds": remaining_seconds,
        }
        return "ok", out
    finally:
        conn.close()


def unpause_retention(config: Config, domain_id: str, actor_role: str) -> tuple[str, dict[str, Any] | None]:
    """Unpause retention for an archived domain. Super-admin only. Returns ('ok', domain) or ('forbidden'|'not_found'|'not_archived'|'not_paused', None)."""
    if actor_role != ROLE_SUPER_ADMIN:
        return "forbidden", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, status, created_at, archived_at, retention_remaining_seconds FROM domains WHERE id = ?",
            (domain_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] != STATUS_ARCHIVED:
            return "not_archived", None
        cur2 = conn.execute("SELECT retention_paused FROM domains WHERE id = ?", (domain_id,))
        r2 = cur2.fetchone()
        if not r2 or not r2[0]:
            return "not_paused", None
        now = datetime.now(timezone.utc)
        remaining = row[5] if row[5] is not None else 0
        new_delete_at = (now + timedelta(seconds=max(0, remaining))).isoformat()
        conn.execute(
            """UPDATE domains SET retention_paused = 0, retention_paused_at = NULL, retention_pause_reason = NULL,
               retention_delete_at = ? WHERE id = ?""",
            (new_delete_at, domain_id),
        )
        conn.commit()
        out = {
            "id": row[0],
            "name": row[1],
            "status": STATUS_ARCHIVED,
            "created_at": row[3],
            "archived_at": row[4],
            "retention_paused": 0,
            "retention_delete_at": new_delete_at,
        }
        return "ok", out
    finally:
        conn.close()


def run_retention_purge(config: Config) -> int:
    """Find archived domains past retention_delete_at (and not paused), purge them. Returns count purged."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, name FROM domains
               WHERE status = ? AND retention_delete_at IS NOT NULL AND retention_delete_at <= ?
               AND (retention_paused IS NULL OR retention_paused = 0)""",
            (STATUS_ARCHIVED, now_iso),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    for domain_id, domain_name in rows:
        _purge_domain_data(config, domain_id, domain_name)
    return len(rows)


def set_retention(
    config: Config, domain_id: str, actor_role: str, retention_days: int
) -> tuple[str, dict[str, Any] | None]:
    """Set or update retention for an archived domain. Super-admin only. Returns ('ok', domain) or error tuple."""
    if actor_role != ROLE_SUPER_ADMIN:
        return "forbidden", None
    if retention_days is None or retention_days <= 0:
        return "invalid", None
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, name, status, created_at, archived_at, retention_paused
               FROM domains WHERE id = ?""",
            (domain_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        if row[2] != STATUS_ARCHIVED:
            return "not_archived", None
        now = datetime.now(timezone.utc)
        is_paused = row[5] == 1
        if is_paused:
            remaining_seconds = retention_days * 86400
            conn.execute(
                """UPDATE domains SET retention_days = ?, retention_remaining_seconds = ?
                   WHERE id = ?""",
                (retention_days, remaining_seconds, domain_id),
            )
        else:
            new_delete_at = (now + timedelta(days=retention_days)).isoformat()
            conn.execute(
                """UPDATE domains SET retention_days = ?, retention_delete_at = ?
                   WHERE id = ?""",
                (retention_days, new_delete_at, domain_id),
            )
        conn.commit()
        cur2 = conn.execute(
            """SELECT retention_days, retention_delete_at, retention_paused, retention_remaining_seconds
               FROM domains WHERE id = ?""",
            (domain_id,),
        )
        r2 = cur2.fetchone()
        out = {
            "id": row[0],
            "name": row[1],
            "status": STATUS_ARCHIVED,
            "created_at": row[3],
            "archived_at": row[4],
            "retention_days": r2[0],
            "retention_delete_at": r2[1],
            "retention_paused": r2[2] if r2[2] is not None else 0,
        }
        if is_paused and r2[3] is not None:
            out["retention_remaining_seconds"] = r2[3]
        return "ok", out
    finally:
        conn.close()


def get_domain_ids_for_user(config: Config, user_id: str, role: str) -> list[str]:
    """Return domain ids visible to user: super-admin gets empty (all_domains=true); others get assigned ids."""
    if role == ROLE_SUPER_ADMIN:
        return []  # /me uses all_domains true; domain_ids can be empty
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT domain_id FROM user_domain_assignments WHERE user_id = ? ORDER BY domain_id",
            (user_id,),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def get_domain_stats(
    config: Config, domain_id: str, current_user: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    """Get report/record counts for a domain. Super-admin sees any; others only assigned active domains."""
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, name, status FROM domains WHERE id = ?", (domain_id,))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        domain_name = row[1]
        domain_status = row[2]

        if role != ROLE_SUPER_ADMIN:
            if domain_status != STATUS_ACTIVE:
                return "forbidden", None
            cur2 = conn.execute(
                "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
                (user_id, domain_id),
            )
            if not cur2.fetchone():
                return "forbidden", None

        agg_count = conn.execute(
            "SELECT COUNT(*) FROM aggregate_reports WHERE domain = ?", (domain_name,)
        ).fetchone()[0]
        forensic_count = conn.execute(
            "SELECT COUNT(*) FROM forensic_reports WHERE domain = ?", (domain_name,)
        ).fetchone()[0]
        record_count = conn.execute(
            """SELECT COUNT(*) FROM aggregate_report_records r
               JOIN aggregate_reports a ON r.aggregate_report_id = a.id
               WHERE a.domain = ?""",
            (domain_name,),
        ).fetchone()[0]

        result: dict[str, Any] = {
            "domain_id": domain_id,
            "aggregate_reports": agg_count,
            "forensic_reports": forensic_count,
            "aggregate_records": record_count,
        }

        if config.archive_storage_path:
            archive = FilesystemArchiveStorage(config.archive_storage_path)
            result["artifact_count"] = archive.count(domain_name)

        return "ok", result
    finally:
        conn.close()


def get_domain_detail(
    config: Config, domain_id: str, current_user: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    status, _domain_name = _check_domain_access(config, domain_id, current_user)
    if status != "ok":
        return status, None
    return "ok", domain_monitoring_service.fetch_domain_summary(config, domain_id=domain_id)


def _check_domain_access(
    config: Config, domain_id: str, current_user: dict[str, Any]
) -> tuple[str, str | None]:
    """Check if user can access domain. Returns (status_code, domain_name) or (error_code, None)."""
    role = current_user.get("role", "")
    user_id = current_user.get("id", "")
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, name, status FROM domains WHERE id = ?", (domain_id,))
        row = cur.fetchone()
        if not row:
            return "not_found", None
        domain_name = row[1]
        domain_status = row[2]

        if role != ROLE_SUPER_ADMIN:
            if domain_status != STATUS_ACTIVE:
                return "forbidden", None
            cur2 = conn.execute(
                "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
                (user_id, domain_id),
            )
            if not cur2.fetchone():
                return "forbidden", None

        return "ok", domain_name
    finally:
        conn.close()


def list_artifacts(
    config: Config, domain_id: str, current_user: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    """List artifact IDs for a domain. Same authorization as domain stats."""
    status, domain_name = _check_domain_access(config, domain_id, current_user)
    if status != "ok" or domain_name is None:
        return status, None

    if not config.archive_storage_path:
        return "ok", {"domain_id": domain_id, "artifacts": []}

    archive = FilesystemArchiveStorage(config.archive_storage_path)
    artifact_ids = archive.list(domain_name)
    return "ok", {"domain_id": domain_id, "artifacts": artifact_ids}


def get_artifact(
    config: Config, domain_id: str, artifact_id: str, current_user: dict[str, Any]
) -> tuple[str, bytes | None]:
    """Retrieve raw artifact bytes. Returns ('ok', bytes), ('not_found', None), or ('forbidden', None)."""
    status, domain_name = _check_domain_access(config, domain_id, current_user)
    if status != "ok" or domain_name is None:
        return status, None

    if not config.archive_storage_path:
        return "not_found", None

    archive = FilesystemArchiveStorage(config.archive_storage_path)
    data = archive.retrieve(domain_name, artifact_id)
    if data is None:
        return "not_found", None
    return "ok", data
