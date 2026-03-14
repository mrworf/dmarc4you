"""Bootstrap super-admin on first run: create admin with random password if no users exist."""

import logging
import uuid
from datetime import datetime, timezone

from backend.storage.sqlite import get_connection, run_migrations
from backend.auth.password import hash_password, generate_random_password

BOOTSTRAP_USERNAME = "admin"
ROLE_SUPER_ADMIN = "super-admin"
USER_ID_PREFIX = "usr_"

logger = logging.getLogger(__name__)


def ensure_bootstrap_admin(database_path: str) -> str | None:
    """
    If no users exist, run migrations, create super-admin 'admin' with random password,
    and return the plaintext password (caller should print once). Otherwise return None.
    """
    run_migrations(database_path)
    conn = get_connection(database_path)
    try:
        cur = conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            return None
        password = generate_random_password()
        password_hash = hash_password(password)
        user_id = f"{USER_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        # SQLite datetime: ISO 8601
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at)
               VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL)""",
            (user_id, BOOTSTRAP_USERNAME, password_hash, ROLE_SUPER_ADMIN, created_at),
        )
        conn.commit()
        logger.info("Bootstrap: created super-admin user %s", BOOTSTRAP_USERNAME)
        return password
    finally:
        conn.close()
