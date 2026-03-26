"""User service: CRUD operations for user management."""

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection
from backend.auth.password import hash_password, generate_random_password
from backend.auth.session import invalidate_user_sessions
from backend.policies.user_policy import (
    can_manage_users,
    can_create_user_with_role,
    can_update_user,
    can_reset_password,
    can_assign_domain,
    can_remove_domain,
    can_delete_user,
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_HIERARCHY,
)

USER_ID_PREFIX = "usr_"
_UNSET = object()


def _write_audit_event(
    database_path: str,
    action_type: str,
    outcome: str,
    actor_user_id: str,
    summary: str,
) -> None:
    """Write audit event for user management actions."""
    event_id = f"aud_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO audit_log (id, timestamp, actor_type, actor_user_id, actor_api_key_id,
               action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, 'user', ?, NULL, ?, ?, NULL, NULL, ?, NULL)""",
            (event_id, timestamp, actor_user_id, action_type, outcome, summary),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_domain_ids(config: Config, user_id: str) -> set[str]:
    """Get domain IDs assigned to a user."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT domain_id FROM user_domain_assignments WHERE user_id = ?",
            (user_id,),
        )
        return {r[0] for r in cur.fetchall()}
    finally:
        conn.close()


def list_users(config: Config, actor: dict) -> tuple[str, list[dict[str, Any]]]:
    """
    List users visible to actor.
    Super-admin sees all users.
    Admin sees users who share at least one domain assignment.
    Returns ('ok', users) or ('forbidden', []).
    """
    if not can_manage_users(actor):
        return "forbidden", []

    conn = get_connection(config.database_path)
    try:
        if actor.get("role") == ROLE_SUPER_ADMIN:
            cur = conn.execute(
                """SELECT id, username, role, full_name, email, created_at, created_by_user_id, must_change_password
                   FROM users WHERE disabled_at IS NULL ORDER BY username"""
            )
            rows = cur.fetchall()
        else:
            actor_domains = get_user_domain_ids(config, actor["id"])
            if not actor_domains:
                return "ok", []
            placeholders = ",".join("?" for _ in actor_domains)
            cur = conn.execute(
                f"""SELECT DISTINCT u.id, u.username, u.role, u.full_name, u.email, u.created_at, u.created_by_user_id,
                           u.must_change_password
                    FROM users u
                    INNER JOIN user_domain_assignments uda ON uda.user_id = u.id
                    WHERE u.disabled_at IS NULL AND uda.domain_id IN ({placeholders})
                    ORDER BY u.username""",
                tuple(actor_domains),
            )
            rows = cur.fetchall()

        users = []
        for r in rows:
            user_id = r[0]
            domain_cur = conn.execute(
                "SELECT domain_id FROM user_domain_assignments WHERE user_id = ?",
                (user_id,),
            )
            domain_ids = [d[0] for d in domain_cur.fetchall()]
            users.append({
                "id": user_id,
                "username": r[1],
                "role": r[2],
                "full_name": r[3],
                "email": r[4],
                "created_at": r[5],
                "created_by_user_id": r[6],
                "must_change_password": bool(r[7]),
                "domain_ids": domain_ids,
            })
        return "ok", users
    finally:
        conn.close()


def get_user_by_id(config: Config, user_id: str) -> dict[str, Any] | None:
    """Get user by ID (internal use). Returns None if not found or disabled."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, username, role, full_name, email, created_at, created_by_user_id, must_change_password
               FROM users WHERE id = ? AND disabled_at IS NULL""",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "full_name": row[3],
            "email": row[4],
            "created_at": row[5],
            "created_by_user_id": row[6],
            "must_change_password": bool(row[7]),
        }
    finally:
        conn.close()


def create_user(
    config: Config,
    actor: dict,
    username: str,
    role: str,
    full_name: str | None = None,
    email: str | None = None,
) -> tuple[str, dict[str, Any] | None]:
    """
    Create a new user with random password.
    Returns ('ok', {user, password}) or ('forbidden'|'invalid'|'duplicate', None).
    """
    if not can_manage_users(actor):
        return "forbidden", None

    username = (username or "").strip()
    full_name = (full_name or "").strip() or None
    email = (email or "").strip() or None
    if not username:
        return "invalid", None

    if role not in ROLE_HIERARCHY:
        return "invalid", None

    if not can_create_user_with_role(actor, role):
        return "forbidden", None

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            return "duplicate", None

        user_id = f"{USER_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        password = generate_random_password()
        password_hash_val = hash_password(password)
        created_at = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """INSERT INTO users (
                   id, username, password_hash, role, full_name, email, created_at, created_by_user_id, last_login_at,
                   disabled_at, must_change_password, password_changed_at
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 1, NULL)""",
            (user_id, username, password_hash_val, role, full_name, email, created_at, actor["id"]),
        )
        conn.commit()

        _write_audit_event(
            config.database_path,
            "user_created",
            "success",
            actor["id"],
            f"created user {username} with role {role}",
        )

        return "ok", {
            "user": {
                "id": user_id,
                "username": username,
                "role": role,
                "full_name": full_name,
                "email": email,
                "created_at": created_at,
                "created_by_user_id": actor["id"],
                "must_change_password": True,
                "domain_ids": [],
            },
            "password": password,
        }
    finally:
        conn.close()


def update_user(
    config: Config,
    actor: dict,
    target_user_id: str,
    new_username: str | None = None,
    new_role: str | None = None,
    new_full_name: str | object = _UNSET,
    new_email: str | object = _UNSET,
) -> tuple[str, dict[str, Any] | None]:
    """
    Update user username and/or role.
    Returns ('ok', user) or ('forbidden'|'not_found'|'invalid'|'duplicate', None).
    """
    if not can_manage_users(actor):
        return "forbidden", None

    target = get_user_by_id(config, target_user_id)
    if not target:
        return "not_found", None

    allowed, reason = can_update_user(actor, target, new_role)
    if not allowed:
        return "forbidden", None

    new_username = (new_username or "").strip() if new_username is not None else None
    if new_username is not None and not new_username:
        return "invalid", None
    if new_full_name is not _UNSET:
        new_full_name = (new_full_name or "").strip() or None
    if new_email is not _UNSET:
        new_email = (new_email or "").strip() or None

    if new_role is not None and new_role not in ROLE_HIERARCHY:
        return "invalid", None

    conn = get_connection(config.database_path)
    try:
        if new_username and new_username != target["username"]:
            cur = conn.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (new_username, target_user_id))
            if cur.fetchone():
                return "duplicate", None

        updates = []
        params = []
        summary_parts = []

        if new_username and new_username != target["username"]:
            updates.append("username = ?")
            params.append(new_username)
            summary_parts.append(f"username {target['username']} -> {new_username}")
        if new_role and new_role != target["role"]:
            updates.append("role = ?")
            params.append(new_role)
            summary_parts.append(f"role {target['role']} -> {new_role}")
        if new_full_name is not _UNSET and new_full_name != target["full_name"]:
            updates.append("full_name = ?")
            params.append(new_full_name)
            summary_parts.append("full_name updated")
        if new_email is not _UNSET and new_email != target["email"]:
            updates.append("email = ?")
            params.append(new_email)
            summary_parts.append("email updated")

        if not updates:
            return "ok", target

        params.append(target_user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", tuple(params))
        conn.commit()

        _write_audit_event(
            config.database_path,
            "user_updated",
            "success",
            actor["id"],
            f"updated user {target_user_id}: {'; '.join(summary_parts)}",
        )

        updated = get_user_by_id(config, target_user_id)
        if updated:
            domain_ids = list(get_user_domain_ids(config, target_user_id))
            updated["domain_ids"] = domain_ids
        return "ok", updated
    finally:
        conn.close()


def reset_password(
    config: Config,
    actor: dict,
    target_user_id: str,
) -> tuple[str, str | None]:
    """
    Reset user's password to a new random value.
    Returns ('ok', new_password) or ('forbidden'|'not_found', None).
    """
    if not can_manage_users(actor):
        return "forbidden", None

    target = get_user_by_id(config, target_user_id)
    if not target:
        return "not_found", None

    allowed, reason = can_reset_password(actor, target)
    if not allowed:
        return "forbidden", None

    new_password = generate_random_password()
    new_hash = hash_password(new_password)

    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """UPDATE users
               SET password_hash = ?, must_change_password = 1, password_changed_at = ?
               WHERE id = ?""",
            (new_hash, datetime.now(timezone.utc).isoformat(), target_user_id),
        )
        conn.commit()
        invalidate_user_sessions(config.database_path, target_user_id)

        _write_audit_event(
            config.database_path,
            "password_reset",
            "success",
            actor["id"],
            f"reset password for user {target_user_id}",
        )

        return "ok", new_password
    finally:
        conn.close()


def assign_domains(
    config: Config,
    actor: dict,
    target_user_id: str,
    domain_ids: list[str],
) -> tuple[str, dict[str, Any] | None]:
    """
    Assign domains to user.
    Returns ('ok', user) or ('forbidden'|'not_found'|'invalid_domain', None).
    """
    if not can_manage_users(actor):
        return "forbidden", None

    target = get_user_by_id(config, target_user_id)
    if not target:
        return "not_found", None

    actor_domain_ids = get_user_domain_ids(config, actor["id"]) if actor.get("role") != ROLE_SUPER_ADMIN else set()

    conn = get_connection(config.database_path)
    try:
        assigned_at = datetime.now(timezone.utc).isoformat()
        assigned_domains = []

        for domain_id in domain_ids:
            cur = conn.execute(
                "SELECT id FROM domains WHERE id = ? AND status = 'active'",
                (domain_id,),
            )
            if not cur.fetchone():
                return "invalid_domain", None

            allowed, reason = can_assign_domain(actor, target, actor_domain_ids, domain_id)
            if not allowed:
                return "forbidden", None

            cur = conn.execute(
                "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
                (target_user_id, domain_id),
            )
            if cur.fetchone():
                continue

            conn.execute(
                """INSERT INTO user_domain_assignments (user_id, domain_id, assigned_by_user_id, assigned_at)
                   VALUES (?, ?, ?, ?)""",
                (target_user_id, domain_id, actor["id"], assigned_at),
            )
            assigned_domains.append(domain_id)

        conn.commit()

        if assigned_domains:
            _write_audit_event(
                config.database_path,
                "domain_assigned",
                "success",
                actor["id"],
                f"assigned domains {assigned_domains} to user {target_user_id}",
            )

        updated = get_user_by_id(config, target_user_id)
        if updated:
            updated["domain_ids"] = list(get_user_domain_ids(config, target_user_id))
        return "ok", updated
    finally:
        conn.close()


def remove_domain(
    config: Config,
    actor: dict,
    target_user_id: str,
    domain_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """
    Remove domain assignment from user.
    Returns ('ok', user) or ('forbidden'|'not_found', None).
    """
    if not can_manage_users(actor):
        return "forbidden", None

    target = get_user_by_id(config, target_user_id)
    if not target:
        return "not_found", None

    actor_domain_ids = get_user_domain_ids(config, actor["id"]) if actor.get("role") != ROLE_SUPER_ADMIN else set()

    allowed, reason = can_remove_domain(actor, target, actor_domain_ids, domain_id)
    if not allowed:
        return "forbidden", None

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
            (target_user_id, domain_id),
        )
        if not cur.fetchone():
            updated = get_user_by_id(config, target_user_id)
            if updated:
                updated["domain_ids"] = list(get_user_domain_ids(config, target_user_id))
            return "ok", updated

        conn.execute(
            "DELETE FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
            (target_user_id, domain_id),
        )
        conn.commit()

        _write_audit_event(
            config.database_path,
            "domain_removed",
            "success",
            actor["id"],
            f"removed domain {domain_id} from user {target_user_id}",
        )

        updated = get_user_by_id(config, target_user_id)
        if updated:
            updated["domain_ids"] = list(get_user_domain_ids(config, target_user_id))
        return "ok", updated
    finally:
        conn.close()


def _find_new_dashboard_owner(
    conn,
    dashboard_id: str,
    dashboard_domain_ids: list[str],
    deleted_user_id: str,
) -> str | None:
    """
    Find a new owner for a dashboard using deterministic fallback order:
    1. Assigned manager with access to all dashboard domains
    2. Admin with access to all dashboard domains (ordered by username)
    3. Super-admin (ordered by username)
    Returns user_id or None if no eligible owner found.
    """
    domain_set = set(dashboard_domain_ids)

    # 1. Try assigned managers first
    cur = conn.execute(
        """SELECT ua.user_id FROM dashboard_user_access ua
           JOIN users u ON u.id = ua.user_id
           WHERE ua.dashboard_id = ? AND ua.access_level = 'manager'
             AND u.disabled_at IS NULL AND ua.user_id != ?
           ORDER BY u.username""",
        (dashboard_id, deleted_user_id),
    )
    for (candidate_id,) in cur.fetchall():
        candidate_domains = _get_user_domain_ids_internal(conn, candidate_id)
        if domain_set <= candidate_domains:
            return candidate_id

    # 2. Try admins with access to all dashboard domains
    cur = conn.execute(
        """SELECT id FROM users
           WHERE role = 'admin' AND disabled_at IS NULL AND id != ?
           ORDER BY username""",
        (deleted_user_id,),
    )
    for (candidate_id,) in cur.fetchall():
        candidate_domains = _get_user_domain_ids_internal(conn, candidate_id)
        if domain_set <= candidate_domains:
            return candidate_id

    # 3. Try super-admins (they have access to all domains)
    cur = conn.execute(
        """SELECT id FROM users
           WHERE role = 'super-admin' AND disabled_at IS NULL AND id != ?
           ORDER BY username""",
        (deleted_user_id,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    return None


def _get_user_domain_ids_internal(conn, user_id: str) -> set[str]:
    """Get domain IDs assigned to a user (internal, uses existing connection)."""
    cur = conn.execute(
        "SELECT domain_id FROM user_domain_assignments WHERE user_id = ?",
        (user_id,),
    )
    return {r[0] for r in cur.fetchall()}


def delete_user(
    config: Config,
    actor: dict,
    target_user_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """
    Delete (soft-delete) a user. Transfers dashboard ownership using fallback rules.
    Returns ('ok', {transfers: [...]}) or error code.
    """
    if not can_manage_users(actor):
        return "forbidden", None

    target = get_user_by_id(config, target_user_id)
    if not target:
        return "not_found", None

    allowed, reason = can_delete_user(actor, target)
    if not allowed:
        if reason == "cannot_self_delete":
            return "self_delete", None
        return "forbidden", None

    conn = get_connection(config.database_path)
    try:
        # Find dashboards owned by this user
        cur = conn.execute(
            """SELECT d.id, d.name FROM dashboards d
               WHERE d.owner_user_id = ?""",
            (target_user_id,),
        )
        owned_dashboards = cur.fetchall()

        transfers = []
        audit_events = []
        for dash_id, dash_name in owned_dashboards:
            # Get dashboard domain IDs
            cur = conn.execute(
                "SELECT domain_id FROM dashboard_domain_scope WHERE dashboard_id = ?",
                (dash_id,),
            )
            dash_domain_ids = [r[0] for r in cur.fetchall()]

            new_owner_id = _find_new_dashboard_owner(conn, dash_id, dash_domain_ids, target_user_id)
            if not new_owner_id:
                return "no_fallback_owner", None

            # Transfer ownership
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE dashboards SET owner_user_id = ?, updated_at = ? WHERE id = ?",
                (new_owner_id, now, dash_id),
            )
            transfers.append({
                "dashboard_id": dash_id,
                "dashboard_name": dash_name,
                "new_owner_id": new_owner_id,
            })

            audit_events.append((
                "dashboard_ownership_transferred",
                "success",
                f"transferred dashboard {dash_id} from deleted user {target_user_id} to {new_owner_id}",
            ))

        # Remove user from all dashboard_user_access
        conn.execute(
            "DELETE FROM dashboard_user_access WHERE user_id = ?",
            (target_user_id,),
        )

        # Soft-delete the user
        disabled_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE users SET disabled_at = ? WHERE id = ?",
            (disabled_at, target_user_id),
        )
        conn.commit()
    finally:
        conn.close()

    # Write audit events after releasing the connection
    for action_type, outcome, summary in audit_events:
        _write_audit_event(config.database_path, action_type, outcome, actor["id"], summary)

    _write_audit_event(
        config.database_path,
        "user_deleted",
        "success",
        actor["id"],
        f"deleted user {target_user_id} ({target['username']})",
    )

    return "ok", {"transfers": transfers}
