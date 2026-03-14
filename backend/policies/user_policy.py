"""User policy: authorization rules for user management (AGENTS.md RBAC rules)."""

ROLE_SUPER_ADMIN = "super-admin"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_VIEWER = "viewer"

ROLE_HIERARCHY = {
    ROLE_SUPER_ADMIN: 4,
    ROLE_ADMIN: 3,
    ROLE_MANAGER: 2,
    ROLE_VIEWER: 1,
}


def role_level(role: str) -> int:
    return ROLE_HIERARCHY.get(role, 0)


def can_manage_users(actor: dict) -> bool:
    """Admin and super-admin can manage users."""
    return actor.get("role") in (ROLE_SUPER_ADMIN, ROLE_ADMIN)


def can_create_user_with_role(actor: dict, target_role: str) -> bool:
    """
    Super-admin can create any role.
    Admin can create admin, manager, viewer but NOT super-admin.
    """
    actor_role = actor.get("role")
    if actor_role == ROLE_SUPER_ADMIN:
        return target_role in ROLE_HIERARCHY
    if actor_role == ROLE_ADMIN:
        return target_role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_VIEWER)
    return False


def can_update_user(actor: dict, target_user: dict, new_role: str | None = None) -> tuple[bool, str]:
    """
    Check if actor can update target user.
    Returns (allowed, reason).
    
    Rules:
    - No self-edit (username change must be by another admin)
    - Super-admin can update anyone
    - Admin cannot change another admin or super-admin
    - Admin cannot promote to super-admin
    """
    actor_role = actor.get("role")
    actor_id = actor.get("id")
    target_role = target_user.get("role")
    target_id = target_user.get("id")

    if actor_id == target_id:
        return False, "cannot_self_edit"

    if actor_role == ROLE_SUPER_ADMIN:
        if new_role and new_role not in ROLE_HIERARCHY:
            return False, "invalid_role"
        return True, "ok"

    if actor_role == ROLE_ADMIN:
        if target_role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
            return False, "cannot_modify_admin"
        if new_role == ROLE_SUPER_ADMIN:
            return False, "cannot_promote_to_super_admin"
        if new_role and new_role not in ROLE_HIERARCHY:
            return False, "invalid_role"
        return True, "ok"

    return False, "forbidden"


def can_reset_password(actor: dict, target_user: dict) -> tuple[bool, str]:
    """
    Check if actor can reset target user's password.
    Same rules as update: no self, admin cannot reset admin/super-admin.
    """
    actor_role = actor.get("role")
    actor_id = actor.get("id")
    target_role = target_user.get("role")
    target_id = target_user.get("id")

    if actor_id == target_id:
        return False, "cannot_self_reset"

    if actor_role == ROLE_SUPER_ADMIN:
        return True, "ok"

    if actor_role == ROLE_ADMIN:
        if target_role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
            return False, "cannot_reset_admin"
        return True, "ok"

    return False, "forbidden"


def can_assign_domain(actor: dict, target_user: dict, actor_domain_ids: set[str], domain_id: str) -> tuple[bool, str]:
    """
    Check if actor can assign domain_id to target_user.
    
    Rules:
    - Super-admin can assign any active domain to anyone
    - Admin can only assign domains they have
    - Admin cannot assign domains to another admin
    """
    actor_role = actor.get("role")
    target_role = target_user.get("role")

    if actor_role == ROLE_SUPER_ADMIN:
        return True, "ok"

    if actor_role == ROLE_ADMIN:
        if target_role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
            return False, "cannot_assign_to_admin"
        if domain_id not in actor_domain_ids:
            return False, "domain_not_in_scope"
        return True, "ok"

    return False, "forbidden"


def can_remove_domain(actor: dict, target_user: dict, actor_domain_ids: set[str], domain_id: str) -> tuple[bool, str]:
    """
    Check if actor can remove domain_id from target_user.
    Same rules as assign.
    """
    return can_assign_domain(actor, target_user, actor_domain_ids, domain_id)


def can_delete_user(actor: dict, target_user: dict) -> tuple[bool, str]:
    """
    Check if actor can delete target user.
    Returns (allowed, reason).

    Rules:
    - No self-deletion
    - Super-admin can delete anyone except self
    - Admin cannot delete another admin or super-admin
    """
    actor_role = actor.get("role")
    actor_id = actor.get("id")
    target_role = target_user.get("role")
    target_id = target_user.get("id")

    if actor_id == target_id:
        return False, "cannot_self_delete"

    if actor_role == ROLE_SUPER_ADMIN:
        return True, "ok"

    if actor_role == ROLE_ADMIN:
        if target_role in (ROLE_SUPER_ADMIN, ROLE_ADMIN):
            return False, "cannot_delete_admin"
        return True, "ok"

    return False, "forbidden"
