"""Dashboard policy: authorization for view, create, edit, delete."""

from typing import Any

ROLE_SUPER_ADMIN = "super-admin"
ROLE_ADMIN = "admin"
ROLE_VIEWER = "viewer"


def can_view_dashboard(dashboard_domain_ids: list[str], user_allowed_domain_ids: list[str]) -> bool:
    """User may view dashboard only if every dashboard domain is in their allowed set. Super-admin has all."""
    if not dashboard_domain_ids:
        return True
    allowed = set(user_allowed_domain_ids)
    return all(did in allowed for did in dashboard_domain_ids)


def can_create_dashboard_with_domains(domain_ids: list[str], user_allowed_domain_ids: list[str]) -> bool:
    """User may create dashboard only with domain_ids that are all in their allowed set."""
    if not domain_ids:
        return False
    allowed = set(user_allowed_domain_ids)
    return all(did in allowed for did in domain_ids)


def can_edit_dashboard(
    current_user: dict[str, Any],
    dashboard: dict[str, Any],
    user_allowed_domain_ids: list[str],
) -> bool:
    """
    User may edit dashboard if:
    - user is not viewer role, AND
    - user is owner, admin, or super-admin, AND
    - user has access to all dashboard domains.
    """
    role = current_user.get("role", "")
    if role == ROLE_VIEWER:
        return False
    user_id = current_user.get("id", "")
    owner_id = dashboard.get("owner_user_id", "")
    is_owner = user_id == owner_id
    is_admin_or_above = role in (ROLE_ADMIN, ROLE_SUPER_ADMIN)
    if not is_owner and not is_admin_or_above:
        return False
    dashboard_domain_ids = dashboard.get("domain_ids", [])
    return can_view_dashboard(dashboard_domain_ids, user_allowed_domain_ids)


def can_delete_dashboard(
    current_user: dict[str, Any],
    dashboard: dict[str, Any],
    user_allowed_domain_ids: list[str],
) -> bool:
    """
    User may delete dashboard if:
    - user is not viewer role, AND
    - user is owner, admin, or super-admin, AND
    - user has access to all dashboard domains.
    """
    return can_edit_dashboard(current_user, dashboard, user_allowed_domain_ids)


def can_transfer_ownership(
    current_user: dict[str, Any],
    dashboard: dict[str, Any],
    new_owner: dict[str, Any],
    current_user_domain_ids: list[str],
    new_owner_domain_ids: list[str],
) -> tuple[bool, str | None]:
    """
    Check if current user can transfer dashboard ownership to new_owner.
    Returns (True, None) if allowed, or (False, reason_code).
    
    Rules:
    - Current user must be admin or super-admin
    - Current user must have access to all dashboard domains
    - New owner cannot be viewer
    - New owner must have access to all dashboard domains
    """
    role = current_user.get("role", "")
    if role not in (ROLE_ADMIN, ROLE_SUPER_ADMIN):
        return False, "forbidden"
    dashboard_domain_ids = dashboard.get("domain_ids", [])
    if not can_view_dashboard(dashboard_domain_ids, current_user_domain_ids):
        return False, "forbidden"
    new_owner_role = new_owner.get("role", "")
    if new_owner_role == ROLE_VIEWER:
        return False, "invalid_owner"
    if not can_view_dashboard(dashboard_domain_ids, new_owner_domain_ids):
        return False, "invalid_owner"
    return True, None


ROLE_MANAGER = "manager"


def can_share_dashboard(
    current_user: dict[str, Any],
    dashboard: dict[str, Any],
    current_user_domain_ids: list[str],
) -> bool:
    """
    User may share a dashboard if:
    - user is owner, manager with access, admin, or super-admin
    - user has access to all dashboard domains
    - user is not viewer role
    """
    role = current_user.get("role", "")
    if role == ROLE_VIEWER:
        return False
    user_id = current_user.get("id", "")
    owner_id = dashboard.get("owner_user_id", "")
    is_owner = user_id == owner_id
    is_admin_or_above = role in (ROLE_ADMIN, ROLE_SUPER_ADMIN)
    is_manager = role == ROLE_MANAGER
    if not is_owner and not is_admin_or_above and not is_manager:
        return False
    dashboard_domain_ids = dashboard.get("domain_ids", [])
    return can_view_dashboard(dashboard_domain_ids, current_user_domain_ids)


def can_unshare_dashboard(
    current_user: dict[str, Any],
    dashboard: dict[str, Any],
    current_user_domain_ids: list[str],
) -> bool:
    """Same rules as share: owner, manager, admin, super-admin with domain access."""
    return can_share_dashboard(current_user, dashboard, current_user_domain_ids)


def can_be_shared_with(
    target_user: dict[str, Any],
    access_level: str,
    target_user_domain_ids: list[str],
    dashboard_domain_ids: list[str],
) -> tuple[bool, str | None]:
    """
    Check if target_user can receive the given access_level on a dashboard.
    Returns (True, None) if allowed, or (False, reason_code).
    
    Rules:
    - Target user must have access to all dashboard domains
    - Viewer-role users cannot be granted manager access
    """
    if not can_view_dashboard(dashboard_domain_ids, target_user_domain_ids):
        return False, "invalid_target"
    target_role = target_user.get("role", "")
    if access_level == "manager" and target_role == ROLE_VIEWER:
        return False, "invalid_access_level"
    return True, None
