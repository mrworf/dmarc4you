"""Audit service: list_audit_events (super-admin only)."""

from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection

ROLE_SUPER_ADMIN = "super-admin"


def normalize_action_types(
    action_type: str | None = None,
    action_types: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    """Merge legacy and multi-select action filters into a normalized unique list."""
    normalized: list[str] = []
    seen: set[str] = set()
    raw_values = []
    if action_type:
        raw_values.append(action_type)
    raw_values.extend(action_types or [])
    for raw_value in raw_values:
        for part in str(raw_value).split(","):
            value = part.strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
    return normalized


def list_audit_events(
    config: Config,
    current_user: dict[str, Any],
    limit: int = 50,
    offset: int = 0,
    action_type: str | None = None,
    action_types: list[str] | tuple[str, ...] | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    actor_user_id: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    """List audit log entries with optional filters. Returns (events, None) or ([], 'forbidden') if not super-admin."""
    if current_user.get("role") != ROLE_SUPER_ADMIN:
        return {"events": [], "available_action_types": []}, "forbidden"
    limit = max(0, min(100, limit))
    offset = max(0, offset)
    normalized_action_types = normalize_action_types(action_type, action_types)

    where_clauses: list[str] = []
    params: list[Any] = []

    if normalized_action_types:
        placeholders = ",".join("?" for _ in normalized_action_types)
        where_clauses.append(f"action_type IN ({placeholders})")
        params.extend(normalized_action_types)
    if from_date:
        where_clauses.append("timestamp >= ?")
        params.append(from_date)
    if to_date:
        where_clauses.append("timestamp <= ?")
        params.append(to_date + "T23:59:59.999999Z" if "T" not in to_date else to_date)
    if actor_user_id:
        where_clauses.append("actor_user_id = ?")
        params.append(actor_user_id)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    params.extend([limit, offset])

    conn = get_connection(config.database_path)
    try:
        available_action_types = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT action_type FROM audit_log WHERE action_type IS NOT NULL AND action_type != '' ORDER BY action_type ASC"
            ).fetchall()
        ]
        cur = conn.execute(
            f"""SELECT id, timestamp, actor_type, actor_user_id, action_type, outcome, source_ip, user_agent, summary
               FROM audit_log {where_sql} ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
            params,
        )
        rows = cur.fetchall()
        events = [
            {
                "id": r[0],
                "timestamp": r[1],
                "actor_type": r[2],
                "actor_user_id": r[3],
                "action_type": r[4],
                "outcome": r[5],
                "source_ip": r[6],
                "user_agent": r[7],
                "summary": r[8] or "",
            }
            for r in rows
        ]
        return {"events": events, "available_action_types": available_action_types}, None
    finally:
        conn.close()
