"""API key policy: only admin and super-admin may create/list/update/delete."""

ROLE_SUPER_ADMIN = "super-admin"
ROLE_ADMIN = "admin"


def can_create_api_key(role: str) -> bool:
    """Only admin and super-admin may create API keys."""
    return role in (ROLE_SUPER_ADMIN, ROLE_ADMIN)


def can_list_api_keys(role: str) -> bool:
    """Only admin and super-admin may list API keys."""
    return role in (ROLE_SUPER_ADMIN, ROLE_ADMIN)


def can_delete_api_key(role: str, key_created_by_user_id: str, current_user_id: str) -> bool:
    """Creator or super-admin may delete a key."""
    if role == ROLE_SUPER_ADMIN:
        return True
    return key_created_by_user_id == current_user_id


def can_update_api_key(role: str, key_created_by_user_id: str, current_user_id: str) -> bool:
    """Creator or super-admin may update a key."""
    return can_delete_api_key(role, key_created_by_user_id, current_user_id)
