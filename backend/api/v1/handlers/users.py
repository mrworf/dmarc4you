"""User management endpoints: list, create, update, delete, reset-password, domain assign/remove."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


class CreateUserBody(BaseModel):
    username: str
    role: str


class UpdateUserBody(BaseModel):
    username: str | None = None
    role: str | None = None


class AssignDomainsBody(BaseModel):
    domain_ids: list[str]


@router.get("")
def list_users(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/users: list users visible to current admin/super-admin."""
    status_code, users = user_service.list_users(config, current_user)
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"users": users}


@router.post("", status_code=201)
def create_user(
    body: CreateUserBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/users: create user with random password (admin+ only)."""
    result_status, data = user_service.create_user(
        config,
        current_user,
        body.username,
        body.role,
    )
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "invalid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid username or role")
    if result_status == "duplicate":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    return data


@router.get("/{user_id}")
def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/users/{user_id}: get single user."""
    from backend.policies.user_policy import can_manage_users

    if not can_manage_users(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user = user_service.get_user_by_id(config, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user["domain_ids"] = list(user_service.get_user_domain_ids(config, user_id))
    return {"user": user}


@router.put("/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """PUT /api/v1/users/{user_id}: update username and/or role."""
    result_status, user = user_service.update_user(
        config,
        current_user,
        user_id,
        new_username=body.username,
        new_role=body.role,
    )
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if result_status == "invalid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid username or role")
    if result_status == "duplicate":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    return {"user": user}


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> None:
    """DELETE /api/v1/users/{user_id}: delete user with ownership transfer."""
    result_status, data = user_service.delete_user(config, current_user, user_id)
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if result_status == "self_delete":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    if result_status == "no_fallback_owner":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete user: no eligible owner for their dashboards"
        )


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/users/{user_id}/reset-password: reset to random password."""
    result_status, new_password = user_service.reset_password(config, current_user, user_id)
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"password": new_password}


@router.post("/{user_id}/domains")
def assign_domains(
    user_id: str,
    body: AssignDomainsBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/users/{user_id}/domains: assign domains to user."""
    if not body.domain_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="domain_ids required")

    result_status, user = user_service.assign_domains(
        config,
        current_user,
        user_id,
        body.domain_ids,
    )
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if result_status == "invalid_domain":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or inactive domain")
    return {"user": user}


@router.delete("/{user_id}/domains/{domain_id}")
def remove_domain(
    user_id: str,
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """DELETE /api/v1/users/{user_id}/domains/{domain_id}: remove domain from user."""
    result_status, user = user_service.remove_domain(config, current_user, user_id, domain_id)
    if result_status == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if result_status == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"user": user}
