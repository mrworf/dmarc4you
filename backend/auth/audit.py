"""Write audit events (e.g. login_success, login_failure)."""

import uuid
from datetime import datetime, timezone

from backend.storage.sqlite import get_connection

ACTOR_TYPE_USER = "user"
ACTION_LOGIN_SUCCESS = "login_success"
ACTION_LOGIN_FAILURE = "login_failure"
OUTCOME_SUCCESS = "success"
OUTCOME_FAILURE = "failure"


def write_login_event(
    database_path: str,
    *,
    action_type: str,
    outcome: str,
    actor_user_id: str | None = None,
    source_ip: str | None = None,
    user_agent: str | None = None,
    summary: str = "",
) -> None:
    """Write a login audit event. Do not leak sensitive reason to callers."""
    event_id = f"aud_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO audit_log (id, timestamp, actor_type, actor_user_id, actor_api_key_id, action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, NULL)""",
            (event_id, timestamp, ACTOR_TYPE_USER, actor_user_id, action_type, outcome, source_ip, user_agent, summary),
        )
        conn.commit()
    finally:
        conn.close()
