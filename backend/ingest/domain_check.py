"""Check if actor can ingest for domain: configured, active, and authorized."""

from backend.config.schema import Config
from backend.storage.sqlite import get_connection

ROLE_SUPER_ADMIN = "super-admin"
STATUS_ACTIVE = "active"


def can_ingest_for_domain(
    config: Config,
    domain_name: str,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    key_domain_ids: set[str] | None = None,
) -> tuple[bool, str]:
    """Return (allowed, reason). When key_domain_ids is set, allow only if domain is active and in that set. Else use user/role."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, status FROM domains WHERE name = ?",
            (domain_name.strip(),),
        )
        row = cur.fetchone()
        if not row:
            return False, "unconfigured"
        domain_id, name, status = row
        if status != STATUS_ACTIVE:
            return False, "archived"
        if key_domain_ids is not None:
            return (domain_id in key_domain_ids, "" if domain_id in key_domain_ids else "unauthorized")
        if actor_role == ROLE_SUPER_ADMIN:
            return True, ""
        cur = conn.execute(
            "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
            (actor_user_id, domain_id),
        )
        if cur.fetchone():
            return True, ""
        return False, "unauthorized"
    finally:
        conn.close()
