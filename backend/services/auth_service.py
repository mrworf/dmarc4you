"""Auth service: login (validate, verify, session, audit), logout, get_current_user."""

import re
from typing import Any

from backend.config.schema import Config
from backend.auth.password import verify_password
from backend.auth.session import create_session, get_session_user_id, invalidate_session
from backend.auth.user_lookup import get_user_by_id, get_user_by_username
from backend.auth.audit import (
    write_login_event,
    ACTION_LOGIN_SUCCESS,
    ACTION_LOGIN_FAILURE,
    OUTCOME_SUCCESS,
    OUTCOME_FAILURE,
)

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
ROLE_SUPER_ADMIN = "super-admin"


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
) -> tuple[dict[str, Any] | None, str | None]:
    """
    Validate username, verify password, create session, audit. Return (user_dict, session_id) on success;
    (None, None) on failure. User dict has id, username, role. Do not leak failure reason to caller.
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
        return None, None
    user = get_user_by_username(config.database_path, username)
    if not user or not verify_password(password, user["password_hash"]):
        write_login_event(
            config.database_path,
            action_type=ACTION_LOGIN_FAILURE,
            outcome=OUTCOME_FAILURE,
            actor_user_id=user["id"] if user else None,
            source_ip=source_ip,
            user_agent=user_agent,
            summary="invalid_credentials",
        )
        return None, None
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
    }, session_id


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
    }
