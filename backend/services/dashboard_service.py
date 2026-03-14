"""Dashboard service: create, list, get, update, delete, transfer_ownership, export_yaml, import_yaml, share, unshare."""

import uuid
import yaml
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection
from backend.services.domain_service import list_domains
from backend.services.user_service import get_user_by_id, get_user_domain_ids
from backend.policies.dashboard_policy import (
    can_view_dashboard,
    can_create_dashboard_with_domains,
    can_edit_dashboard,
    can_delete_dashboard,
    can_transfer_ownership,
    can_share_dashboard,
    can_unshare_dashboard,
    can_be_shared_with,
)

DASHBOARD_ID_PREFIX = "dash_"


def create_dashboard(
    config: Config,
    name: str,
    description: str,
    domain_ids: list[str],
    owner_user_id: str,
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Create dashboard if domain_ids ⊆ user's allowed domains. Return ('ok', dashboard_dict) or ('forbidden', None) or ('invalid', None)."""
    name = (name or "").strip()
    if not name:
        return "invalid", None
    if not domain_ids:
        return "invalid", None
    allowed = [d["id"] for d in list_domains(config, current_user)]
    if not can_create_dashboard_with_domains(domain_ids, allowed):
        return "forbidden", None
    dashboard_id = f"{DASHBOARD_ID_PREFIX}{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """INSERT INTO dashboards (id, name, description, owner_user_id, created_by_user_id, created_at, updated_at, is_dormant, dormant_reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL)""",
            (dashboard_id, name, description or "", owner_user_id, owner_user_id, now, now),
        )
        for domain_id in domain_ids:
            conn.execute(
                "INSERT INTO dashboard_domain_scope (dashboard_id, domain_id) VALUES (?, ?)",
                (dashboard_id, domain_id),
            )
        conn.commit()
        return "ok", _build_dashboard_dict(conn, dashboard_id)
    finally:
        conn.close()


def _build_dashboard_dict(conn, dashboard_id: str) -> dict[str, Any] | None:
    cur = conn.execute(
        "SELECT id, name, description, owner_user_id, created_by_user_id, created_at, updated_at FROM dashboards WHERE id = ?",
        (dashboard_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cur = conn.execute(
        "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ? ORDER BY domain_id",
        (dashboard_id,),
    )
    domain_ids = [r[0] for r in cur.fetchall()]
    domain_names = []
    for did in domain_ids:
        c = conn.execute("SELECT name FROM domains WHERE id = ?", (did,))
        r = c.fetchone()
        domain_names.append(r[0] if r else did)
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2] or "",
        "owner_user_id": row[3],
        "created_by_user_id": row[4],
        "created_at": row[5],
        "updated_at": row[6],
        "domain_ids": domain_ids,
        "domain_names": domain_names,
    }


ROLE_SUPER_ADMIN = "super-admin"


def list_dashboards(config: Config, current_user: dict[str, Any]) -> list[dict[str, Any]]:
    """List dashboards owned by current user. For non-super-admin, exclude dashboards whose scope contains any archived domain (dormant)."""
    conn = get_connection(config.database_path)
    try:
        user_id = current_user.get("id") or ""
        if current_user.get("role") == ROLE_SUPER_ADMIN:
            cur = conn.execute(
                "SELECT id, name, description, owner_user_id, created_at, updated_at FROM dashboards WHERE owner_user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            )
        else:
            cur = conn.execute(
                """SELECT id, name, description, owner_user_id, created_at, updated_at FROM dashboards
                   WHERE owner_user_id = ? AND id NOT IN (
                     SELECT s.dashboard_id FROM dashboard_domain_scope s
                     INNER JOIN domains d ON d.id = s.domain_id
                     WHERE d.status = 'archived'
                   )
                   ORDER BY updated_at DESC""",
                (user_id,),
            )
        out = []
        for row in cur.fetchall():
            cur2 = conn.execute(
                "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ? ORDER BY domain_id",
                (row[0],),
            )
            domain_ids = [r[0] for r in cur2.fetchall()]
            out.append({
                "id": row[0],
                "name": row[1],
                "description": row[2] or "",
                "owner_user_id": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "domain_ids": domain_ids,
            })
        return out
    finally:
        conn.close()


def get_dashboard(config: Config, dashboard_id: str, current_user: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Return ('ok', dashboard), ('not_found', None), or ('forbidden', None)."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id FROM dashboards WHERE id = ?",
            (dashboard_id,),
        )
        if not cur.fetchone():
            return "not_found", None
        cur = conn.execute(
            "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ? ORDER BY domain_id",
            (dashboard_id,),
        )
        dashboard_domain_ids = [r[0] for r in cur.fetchall()]
        allowed_ids = [d["id"] for d in list_domains(config, current_user)]
        if not can_view_dashboard(dashboard_domain_ids, allowed_ids):
            return "forbidden", None
        return "ok", _build_dashboard_dict(conn, dashboard_id)
    finally:
        conn.close()


def export_dashboard_yaml(
    config: Config, dashboard_id: str, current_user: dict[str, Any]
) -> tuple[str | None, str | None]:
    """Return (yaml_str, None) on success or (None, 'not_found'|'forbidden'). Same access as get_dashboard; portable shape: name, description, domains (names)."""
    code, dashboard = get_dashboard(config, dashboard_id, current_user)
    if code == "not_found":
        return None, "not_found"
    if code == "forbidden":
        return None, "forbidden"
    if not dashboard:
        return None, "not_found"
    payload = {
        "name": dashboard["name"],
        "description": dashboard.get("description") or "",
        "domains": dashboard.get("domain_names") or [],
    }
    return yaml.safe_dump(payload, default_flow_style=False, sort_keys=False), None


def import_dashboard_yaml(
    config: Config,
    yaml_str: str,
    domain_remap: dict[str, str],
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Import dashboard from portable YAML + domain_remap. Return ('ok', dashboard_dict) or ('invalid', None) or ('forbidden', None)."""
    try:
        data = yaml.safe_load(yaml_str)
    except yaml.YAMLError:
        return "invalid", None
    if not isinstance(data, dict):
        return "invalid", None
    name = data.get("name")
    if not name or not isinstance(name, str):
        return "invalid", None
    name = name.strip()
    if not name:
        return "invalid", None
    domains = data.get("domains")
    if not isinstance(domains, list) or not domains:
        return "invalid", None
    if not all(isinstance(d, str) for d in domains):
        return "invalid", None
    description = data.get("description")
    if description is None:
        description = ""
    if not isinstance(description, str):
        description = ""
    if not isinstance(domain_remap, dict):
        return "invalid", None
    for d in domains:
        if d not in domain_remap:
            return "invalid", None
    domain_ids = [domain_remap[d] for d in domains]
    allowed = [d["id"] for d in list_domains(config, current_user)]
    if not can_create_dashboard_with_domains(domain_ids, allowed):
        return "forbidden", None
    code, dashboard = create_dashboard(
        config, name, description, domain_ids, current_user["id"], current_user
    )
    if code != "ok" or not dashboard:
        return "forbidden", None
    return "ok", dashboard


def update_dashboard(
    config: Config,
    dashboard_id: str,
    name: str | None,
    description: str | None,
    domain_ids: list[str] | None,
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """
    Update dashboard name, description, and/or domain_ids.
    Returns ('ok', dashboard_dict), ('not_found', None), ('forbidden', None), or ('invalid', None).
    """
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, description, owner_user_id FROM dashboards WHERE id = ?",
            (dashboard_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        cur = conn.execute(
            "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ?",
            (dashboard_id,),
        )
        existing_domain_ids = [r[0] for r in cur.fetchall()]
        dashboard = {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "owner_user_id": row[3],
            "domain_ids": existing_domain_ids,
        }
        allowed = [d["id"] for d in list_domains(config, current_user)]
        if not can_edit_dashboard(current_user, dashboard, allowed):
            return "forbidden", None
        new_name = name.strip() if name is not None else dashboard["name"]
        new_description = description if description is not None else dashboard["description"]
        new_domain_ids = domain_ids if domain_ids is not None else existing_domain_ids
        if not new_name:
            return "invalid", None
        if not new_domain_ids:
            return "invalid", None
        if not can_create_dashboard_with_domains(new_domain_ids, allowed):
            return "forbidden", None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE dashboards SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (new_name, new_description, now, dashboard_id),
        )
        if set(new_domain_ids) != set(existing_domain_ids):
            conn.execute(
                "DELETE FROM dashboard_domain_scope WHERE dashboard_id = ?",
                (dashboard_id,),
            )
            for did in new_domain_ids:
                conn.execute(
                    "INSERT INTO dashboard_domain_scope (dashboard_id, domain_id) VALUES (?, ?)",
                    (dashboard_id, did),
                )
        conn.commit()
        return "ok", _build_dashboard_dict(conn, dashboard_id)
    finally:
        conn.close()


def delete_dashboard(
    config: Config,
    dashboard_id: str,
    current_user: dict[str, Any],
) -> tuple[str, None]:
    """
    Delete dashboard and its domain scope entries.
    Returns ('ok', None), ('not_found', None), or ('forbidden', None).
    """
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, description, owner_user_id FROM dashboards WHERE id = ?",
            (dashboard_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        cur = conn.execute(
            "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ?",
            (dashboard_id,),
        )
        domain_ids = [r[0] for r in cur.fetchall()]
        dashboard = {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "owner_user_id": row[3],
            "domain_ids": domain_ids,
        }
        allowed = [d["id"] for d in list_domains(config, current_user)]
        if not can_delete_dashboard(current_user, dashboard, allowed):
            return "forbidden", None
        conn.execute(
            "DELETE FROM dashboard_domain_scope WHERE dashboard_id = ?",
            (dashboard_id,),
        )
        conn.execute("DELETE FROM dashboards WHERE id = ?", (dashboard_id,))
        conn.commit()
        return "ok", None
    finally:
        conn.close()


def transfer_dashboard_ownership(
    config: Config,
    dashboard_id: str,
    new_owner_user_id: str,
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """
    Transfer dashboard ownership to another user.
    Returns:
    - ('ok', dashboard_dict)
    - ('not_found', None) - dashboard not found
    - ('forbidden', None) - current user not admin/super-admin or lacks domain access
    - ('invalid_owner', None) - new owner is viewer or lacks domain access
    - ('user_not_found', None) - new owner user not found
    """
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, name, description, owner_user_id FROM dashboards WHERE id = ?",
            (dashboard_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found", None
        cur = conn.execute(
            "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ?",
            (dashboard_id,),
        )
        domain_ids = [r[0] for r in cur.fetchall()]
        dashboard = {
            "id": row[0],
            "name": row[1],
            "description": row[2] or "",
            "owner_user_id": row[3],
            "domain_ids": domain_ids,
        }
        new_owner = get_user_by_id(config, new_owner_user_id)
        if not new_owner:
            return "user_not_found", None
        current_user_domains = [d["id"] for d in list_domains(config, current_user)]
        new_owner_domains = list(get_user_domain_ids(config, new_owner_user_id))
        if new_owner.get("role") == ROLE_SUPER_ADMIN:
            cur = conn.execute("SELECT id FROM domains")
            new_owner_domains = [r[0] for r in cur.fetchall()]
        allowed, reason = can_transfer_ownership(
            current_user, dashboard, new_owner, current_user_domains, new_owner_domains
        )
        if not allowed:
            return reason or "forbidden", None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE dashboards SET owner_user_id = ?, updated_at = ? WHERE id = ?",
            (new_owner_user_id, now, dashboard_id),
        )
        conn.commit()
        return "ok", _build_dashboard_dict(conn, dashboard_id)
    finally:
        conn.close()


def _get_dashboard_with_domains(conn, dashboard_id: str) -> dict[str, Any] | None:
    """Helper: fetch dashboard row and domain_ids without building full dict."""
    cur = conn.execute(
        "SELECT id, name, description, owner_user_id FROM dashboards WHERE id = ?",
        (dashboard_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cur = conn.execute(
        "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ?",
        (dashboard_id,),
    )
    domain_ids = [r[0] for r in cur.fetchall()]
    return {
        "id": row[0],
        "name": row[1],
        "description": row[2] or "",
        "owner_user_id": row[3],
        "domain_ids": domain_ids,
    }


def _get_user_effective_domain_ids(config: Config, conn, user: dict[str, Any]) -> list[str]:
    """Get domain IDs a user can access (super-admin gets all)."""
    if user.get("role") == ROLE_SUPER_ADMIN:
        cur = conn.execute("SELECT id FROM domains")
        return [r[0] for r in cur.fetchall()]
    return list(get_user_domain_ids(config, user["id"]))


def share_dashboard(
    config: Config,
    dashboard_id: str,
    target_user_id: str,
    access_level: str,
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """
    Share dashboard with a user at the given access level.
    Returns:
    - ('ok', {'dashboard_id', 'user_id', 'access_level', ...})
    - ('not_found', None) - dashboard not found
    - ('user_not_found', None) - target user not found
    - ('forbidden', None) - current user cannot share
    - ('invalid_target', None) - target lacks domain access
    - ('invalid_access_level', None) - viewer cannot be manager
    """
    if access_level not in ("viewer", "manager"):
        return "invalid_access_level", None
    conn = get_connection(config.database_path)
    try:
        dashboard = _get_dashboard_with_domains(conn, dashboard_id)
        if not dashboard:
            return "not_found", None
        target_user = get_user_by_id(config, target_user_id)
        if not target_user:
            return "user_not_found", None
        current_user_domains = [d["id"] for d in list_domains(config, current_user)]
        if not can_share_dashboard(current_user, dashboard, current_user_domains):
            return "forbidden", None
        target_user_domains = _get_user_effective_domain_ids(config, conn, target_user)
        allowed, reason = can_be_shared_with(
            target_user, access_level, target_user_domains, dashboard["domain_ids"]
        )
        if not allowed:
            return reason or "invalid_target", None
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO dashboard_user_access (dashboard_id, user_id, access_level, granted_by_user_id, granted_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (dashboard_id, user_id) DO UPDATE SET access_level = ?, granted_by_user_id = ?, granted_at = ?""",
            (dashboard_id, target_user_id, access_level, current_user["id"], now, access_level, current_user["id"], now),
        )
        conn.commit()
        return "ok", {
            "dashboard_id": dashboard_id,
            "user_id": target_user_id,
            "access_level": access_level,
            "granted_by_user_id": current_user["id"],
            "granted_at": now,
        }
    finally:
        conn.close()


def unshare_dashboard(
    config: Config,
    dashboard_id: str,
    target_user_id: str,
    current_user: dict[str, Any],
) -> str:
    """
    Remove a user's access to a dashboard.
    Returns: 'ok', 'not_found', 'assignment_not_found', 'forbidden'.
    """
    conn = get_connection(config.database_path)
    try:
        dashboard = _get_dashboard_with_domains(conn, dashboard_id)
        if not dashboard:
            return "not_found"
        current_user_domains = [d["id"] for d in list_domains(config, current_user)]
        if not can_unshare_dashboard(current_user, dashboard, current_user_domains):
            return "forbidden"
        cur = conn.execute(
            "SELECT 1 FROM dashboard_user_access WHERE dashboard_id = ? AND user_id = ?",
            (dashboard_id, target_user_id),
        )
        if not cur.fetchone():
            return "assignment_not_found"
        conn.execute(
            "DELETE FROM dashboard_user_access WHERE dashboard_id = ? AND user_id = ?",
            (dashboard_id, target_user_id),
        )
        conn.commit()
        return "ok"
    finally:
        conn.close()


def list_dashboard_shares(
    config: Config,
    dashboard_id: str,
    current_user: dict[str, Any],
) -> tuple[str, list[dict[str, Any]] | None]:
    """
    List users who have been granted access to a dashboard.
    Returns:
    - ('ok', [{'user_id', 'username', 'access_level', 'granted_by_user_id', 'granted_at'}, ...])
    - ('not_found', None) - dashboard not found
    - ('forbidden', None) - current user lacks access
    """
    conn = get_connection(config.database_path)
    try:
        dashboard = _get_dashboard_with_domains(conn, dashboard_id)
        if not dashboard:
            return "not_found", None
        allowed_ids = [d["id"] for d in list_domains(config, current_user)]
        if not can_view_dashboard(dashboard["domain_ids"], allowed_ids):
            return "forbidden", None
        cur = conn.execute(
            """SELECT ua.user_id, u.username, ua.access_level, ua.granted_by_user_id, ua.granted_at
               FROM dashboard_user_access ua
               JOIN users u ON u.id = ua.user_id
               WHERE ua.dashboard_id = ?
               ORDER BY ua.granted_at DESC""",
            (dashboard_id,),
        )
        shares = []
        for row in cur.fetchall():
            shares.append({
                "user_id": row[0],
                "username": row[1],
                "access_level": row[2],
                "granted_by_user_id": row[3],
                "granted_at": row[4],
            })
        return "ok", shares
    finally:
        conn.close()


def validate_dashboard_update(
    config: Config,
    dashboard_id: str,
    proposed_domain_ids: list[str],
    current_user: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """
    Dry-run validation: check which users would lose access if domain scope changed.
    Returns:
    - ('ok', {'valid': bool, 'impacted_users': [...]})
    - ('not_found', None)
    - ('forbidden', None)
    """
    conn = get_connection(config.database_path)
    try:
        dashboard = _get_dashboard_with_domains(conn, dashboard_id)
        if not dashboard:
            return "not_found", None
        current_user_domains = [d["id"] for d in list_domains(config, current_user)]
        if not can_edit_dashboard(current_user, dashboard, current_user_domains):
            return "forbidden", None
        proposed_set = set(proposed_domain_ids)
        cur = conn.execute(
            """SELECT ua.user_id, u.username, ua.access_level
               FROM dashboard_user_access ua
               JOIN users u ON u.id = ua.user_id
               WHERE ua.dashboard_id = ?""",
            (dashboard_id,),
        )
        impacted = []
        for row in cur.fetchall():
            user_id, username, access_level = row
            user = get_user_by_id(config, user_id)
            if not user:
                continue
            user_domains = _get_user_effective_domain_ids(config, conn, user)
            if not can_view_dashboard(list(proposed_set), user_domains):
                impacted.append({
                    "user_id": user_id,
                    "username": username,
                    "access_level": access_level,
                })
        return "ok", {"valid": len(impacted) == 0, "impacted_users": impacted}
    finally:
        conn.close()
