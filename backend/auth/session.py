"""Session create/lookup/invalidate using SQLite storage."""

import secrets
from datetime import datetime, timezone, timedelta

from backend.storage.sqlite import get_connection

SESSION_ID_BYTES = 32


def create_session(database_path: str, user_id: str, max_age_days: int) -> str:
    """Create a session for user_id; return session id (token for cookie)."""
    session_id = secrets.token_urlsafe(SESSION_ID_BYTES)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=max_age_days)
    conn = get_connection(database_path)
    try:
        conn.execute(
            "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, now.isoformat(), expires_at.isoformat()),
        )
        conn.commit()
        return session_id
    finally:
        conn.close()


def get_session_user_id(database_path: str, session_id: str) -> str | None:
    """Return user_id if session exists and not expired; else None."""
    if not session_id:
        return None
    conn = get_connection(database_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "SELECT user_id FROM sessions WHERE id = ? AND expires_at > ?",
            (session_id, now),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def invalidate_session(database_path: str, session_id: str) -> None:
    """Remove session so it can no longer be used."""
    if not session_id:
        return
    conn = get_connection(database_path)
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


def invalidate_user_sessions(database_path: str, user_id: str) -> None:
    """Remove every active session for a user."""
    conn = get_connection(database_path)
    try:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
