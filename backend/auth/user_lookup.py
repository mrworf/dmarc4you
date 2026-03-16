"""Look up user by id or username. Thin wrapper over DB."""

from backend.storage.sqlite import get_connection


def get_user_by_id(database_path: str, user_id: str) -> dict | None:
    """Return user row as dict or None."""
    conn = get_connection(database_path)
    try:
        cur = conn.execute(
            "SELECT id, username, role, full_name, email FROM users WHERE id = ? AND disabled_at IS NULL",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "username": row[1], "role": row[2], "full_name": row[3], "email": row[4]}
    finally:
        conn.close()


def get_user_by_username(database_path: str, username: str) -> dict | None:
    """Return user row as dict or None."""
    conn = get_connection(database_path)
    try:
        cur = conn.execute(
            "SELECT id, username, role, password_hash, full_name, email FROM users WHERE username = ? AND disabled_at IS NULL",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "password_hash": row[3],
            "full_name": row[4],
            "email": row[5],
        }
    finally:
        conn.close()
