"""SQLite-backed login throttling keyed by username and source IP."""

from datetime import datetime, timedelta, timezone

from backend.storage.sqlite import get_connection

THROTTLE_WINDOW_MINUTES = 15
THROTTLE_THRESHOLD = 5
THROTTLE_BLOCK_MINUTES = 15
UNKNOWN_SOURCE_IP = "unknown"


def normalize_source_ip(source_ip: str | None) -> str:
    """Return a stable source IP key."""
    value = (source_ip or "").strip()
    return value or UNKNOWN_SOURCE_IP


def get_login_retry_after_seconds(database_path: str, username: str, source_ip: str | None) -> int | None:
    """Return retry-after seconds when throttled, otherwise None."""
    conn = get_connection(database_path)
    try:
        row = conn.execute(
            """SELECT blocked_until
               FROM auth_login_throttle
               WHERE username = ? AND source_ip = ?""",
            (username, normalize_source_ip(source_ip)),
        ).fetchone()
    finally:
        conn.close()

    if not row or not row[0]:
        return None

    blocked_until = datetime.fromisoformat(row[0])
    now = datetime.now(timezone.utc)
    remaining = int((blocked_until - now).total_seconds())
    return remaining if remaining > 0 else None


def clear_login_failures(database_path: str, username: str, source_ip: str | None) -> None:
    """Clear failure state after a successful login."""
    conn = get_connection(database_path)
    try:
        conn.execute(
            "DELETE FROM auth_login_throttle WHERE username = ? AND source_ip = ?",
            (username, normalize_source_ip(source_ip)),
        )
        conn.commit()
    finally:
        conn.close()


def record_failed_login(database_path: str, username: str, source_ip: str | None) -> None:
    """Record a failed login attempt and update throttle state."""
    key_source_ip = normalize_source_ip(source_ip)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=THROTTLE_WINDOW_MINUTES)

    conn = get_connection(database_path)
    try:
        row = conn.execute(
            """SELECT failed_count, first_failed_at
               FROM auth_login_throttle
               WHERE username = ? AND source_ip = ?""",
            (username, key_source_ip),
        ).fetchone()

        if not row:
            conn.execute(
                """INSERT INTO auth_login_throttle
                   (username, source_ip, failed_count, first_failed_at, blocked_until)
                   VALUES (?, ?, 1, ?, NULL)""",
                (username, key_source_ip, now.isoformat()),
            )
            conn.commit()
            return

        failed_count = int(row[0])
        first_failed_at = datetime.fromisoformat(row[1])
        if first_failed_at < window_start:
            failed_count = 0
            first_failed_at = now

        failed_count += 1
        blocked_until = now + timedelta(minutes=THROTTLE_BLOCK_MINUTES) if failed_count >= THROTTLE_THRESHOLD else None

        conn.execute(
            """UPDATE auth_login_throttle
               SET failed_count = ?, first_failed_at = ?, blocked_until = ?
               WHERE username = ? AND source_ip = ?""",
            (
                failed_count,
                first_failed_at.isoformat(),
                blocked_until.isoformat() if blocked_until else None,
                username,
                key_source_ip,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def extend_login_block(database_path: str, username: str, source_ip: str | None) -> int:
    """Extend an active throttle block and return the new retry-after seconds."""
    key_source_ip = normalize_source_ip(source_ip)
    blocked_until = datetime.now(timezone.utc) + timedelta(minutes=THROTTLE_BLOCK_MINUTES)

    conn = get_connection(database_path)
    try:
        conn.execute(
            """UPDATE auth_login_throttle
               SET blocked_until = ?
               WHERE username = ? AND source_ip = ?""",
            (blocked_until.isoformat(), username, key_source_ip),
        )
        conn.commit()
    finally:
        conn.close()

    return int((blocked_until - datetime.now(timezone.utc)).total_seconds())
