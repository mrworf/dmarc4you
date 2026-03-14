"""Domain policy: only super-admin may create, archive, restore, or delete domains."""

ROLE_SUPER_ADMIN = "super-admin"


def can_create_domain(user: dict) -> bool:
    """Only super-admin may add domains (AGENTS.md)."""
    return user.get("role") == ROLE_SUPER_ADMIN


def can_archive_domain(user: dict) -> bool:
    """Only super-admin may archive a domain."""
    return user.get("role") == ROLE_SUPER_ADMIN


def can_restore_domain(user: dict) -> bool:
    """Only super-admin may restore an archived domain."""
    return user.get("role") == ROLE_SUPER_ADMIN


def can_delete_domain(user: dict) -> bool:
    """Only super-admin may delete an archived domain."""
    return user.get("role") == ROLE_SUPER_ADMIN
