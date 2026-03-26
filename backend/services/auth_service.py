"""Auth service: login, logout, current user lookup, and self profile updates."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.auth.login_throttle import (
    clear_login_failures,
    extend_login_block,
    get_login_retry_after_seconds,
    record_failed_login,
)
from backend.auth.password import hash_password, validate_new_password, verify_password
from backend.auth.session import create_session, get_session_user_id, invalidate_session, invalidate_user_sessions
from backend.auth.user_lookup import get_user_by_id, get_user_by_username
from backend.auth.audit import (
    write_login_event,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGIN_FAILURE,
    ACTION_LOGIN_THROTTLED,
    OUTCOME_SUCCESS,
    OUTCOME_FAILURE,
)
from backend.storage.sqlite import get_connection

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ROLE_SUPER_ADMIN = "super-admin"
ACTION_PASSWORD_CHANGE = "password_changed"


def _write_password_change_event(
    database_path: str,
    actor_user_id: str,
    summary: str,
) -> None:
    event_id = f"aud_{uuid.uuid4().hex[:16]}"
    timestamp = datetime.now(timezone.utc).isoformat()
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO audit_log (id, timestamp, actor_type, actor_user_id, actor_api_key_id,
               action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, 'user', ?, NULL, ?, 'success', NULL, NULL, ?, NULL)""",
            (event_id, timestamp, actor_user_id, ACTION_PASSWORD_CHANGE, summary),
        )
        conn.commit()
    finally:
        conn.close()


def validate_username(username: str) -> bool:
    """Username must match ^[A-Za-z0-9_-]+$ (SECURITY_AND_AUDIT)."""
    return bool(username and USERNAME_RE.match(username))


def login(
    config: Config,
    username: str,
    password: str,
    *,
    source_ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, int | None]:
    """
    Validate username, verify password, create session, audit.
    Return (user_dict, session_id, retry_after_seconds) on success/failure.
    Do not leak password-check failure reason to caller.
    """
    if not validate_username(username):
        write_login_event(
            config.database_path,
            action_type=ACTION_LOGIN_FAILURE,
            outcome=OUTCOME_FAILURE,
            actor_user_id=None,
            source_ip=source_ip,
            user_agent=user_agent,
            summary="invalid_username",
        )
        return None, None, None
    retry_after_seconds = get_login_retry_after_seconds(config.database_path, username, source_ip)
    if retry_after_seconds is not None:
        retry_after_seconds = extend_login_block(config.database_path, username, source_ip)
        write_login_event(
            config.database_path,
            action_type=ACTION_LOGIN_THROTTLED,
            outcome=OUTCOME_FAILURE,
            actor_user_id=None,
            source_ip=source_ip,
            user_agent=user_agent,
            summary="login_throttled",
        )
        return None, None, retry_after_seconds
    user = get_user_by_username(config.database_path, username)
    if not user or not verify_password(password, user["password_hash"]):
        record_failed_login(config.database_path, username, source_ip)
        write_login_event(
            config.database_path,
            action_type=ACTION_LOGIN_FAILURE,
            outcome=OUTCOME_FAILURE,
            actor_user_id=user["id"] if user else None,
            source_ip=source_ip,
            user_agent=user_agent,
            summary="invalid_credentials",
        )
        return None, None, None
    clear_login_failures(config.database_path, username, source_ip)
    session_id = create_session(
        config.database_path,
        user["id"],
        config.session_max_age_days,
    )
    write_login_event(
        config.database_path,
        action_type=ACTION_LOGIN_SUCCESS,
        outcome=OUTCOME_SUCCESS,
        actor_user_id=user["id"],
        source_ip=source_ip,
        user_agent=user_agent,
        summary="login",
    )
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "full_name": user.get("full_name"),
        "email": user.get("email"),
        "must_change_password": bool(user.get("must_change_password")),
    }, session_id, None


def logout(config: Config, session_id: str | None) -> None:
    """Invalidate session server-side."""
    if session_id:
        invalidate_session(config.database_path, session_id)


def get_current_user(config: Config, session_id: str | None) -> dict[str, Any] | None:
    """Return user dict (id, username, role) if valid session; else None."""
    if not session_id:
        return None
    user_id = get_session_user_id(config.database_path, session_id)
    if not user_id:
        return None
    return get_user_by_id(config.database_path, user_id)


def me_response_user(config: Config, user: dict[str, Any]) -> dict[str, Any]:
    """Build /me response: user + domain visibility. Super-admin -> all_domains true; others -> domain_ids from assignments."""
    from backend.services.domain_service import get_domain_ids_for_user
    all_domains = user["role"] == ROLE_SUPER_ADMIN
    domain_ids = get_domain_ids_for_user(config, user["id"], user["role"]) if not all_domains else []
    return {
        "user": user,
        "all_domains": all_domains,
        "domain_ids": domain_ids,
        "password_change_required": bool(user.get("must_change_password")),
    }


def update_own_profile(
    config: Config,
    current_user: dict[str, Any],
    *,
    new_full_name: str | None = None,
    new_email: str | None = None,
) -> dict[str, Any]:
    """Update the signed-in user's optional profile fields and return the fresh user record."""
    full_name = (new_full_name or "").strip() or None
    email = (new_email or "").strip() or None

    conn = get_connection(config.database_path)
    try:
        conn.execute(
            "UPDATE users SET full_name = ?, email = ? WHERE id = ? AND disabled_at IS NULL",
            (full_name, email, current_user["id"]),
        )
        conn.commit()
        updated_user = get_user_by_id(config.database_path, current_user["id"])
    finally:
        conn.close()

    if not updated_user:
        return current_user

    return updated_user


def change_own_password(
    config: Config,
    current_user: dict[str, Any],
    *,
    current_password: str,
    new_password: str,
) -> str:
    """Change the signed-in user's password and invalidate all of their sessions."""
    user = get_user_by_username(config.database_path, current_user["username"])
    if not user or not verify_password(current_password, user["password_hash"]):
        return "invalid_current_password"

    validation_error = validate_new_password(new_password)
    if validation_error:
        return validation_error

    if verify_password(new_password, user["password_hash"]):
        return "password_reuse"

    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """UPDATE users
               SET password_hash = ?, must_change_password = 0, password_changed_at = ?
               WHERE id = ? AND disabled_at IS NULL""",
            (hash_password(new_password), datetime.now(timezone.utc).isoformat(), current_user["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    invalidate_user_sessions(config.database_path, current_user["id"])
    _write_password_change_event(config.database_path, current_user["id"], "changed own password")
    return "ok"
