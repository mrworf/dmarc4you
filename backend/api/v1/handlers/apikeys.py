"""API key endpoints: GET list, POST create (returns key once), DELETE revoke."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import api_key_service

router = APIRouter(prefix="/apikeys", tags=["apikeys"])


class CreateApiKeyBody(BaseModel):
    nickname: str = ""
    description: str = ""
    domain_ids: list[str] = []
    scopes: list[str] = []


@router.get("")
def list_apikeys(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/apikeys: list keys (no secret). Admin/super-admin only."""
    keys, err = api_key_service.list_api_keys(config, current_user)
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"keys": keys}


@router.post("", status_code=201)
def create_apikey(
    body: CreateApiKeyBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/apikeys: create key; response includes raw key once."""
    key_id, raw_secret, err = api_key_service.create_api_key(
        config,
        (body.nickname or "").strip(),
        body.description or "",
        body.domain_ids or [],
        body.scopes or [],
        current_user["id"],
        current_user,
    )
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if err == "invalid" or not key_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="nickname, at least one domain_id, and at least one scope required",
        )
    return {"id": key_id, "nickname": (body.nickname or "").strip(), "key": raw_secret}


@router.delete("/{key_id}", status_code=204)
def delete_apikey(
    key_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> None:
    """DELETE /api/v1/apikeys/{id}: revoke key. Creator or super-admin only."""
    result = api_key_service.delete_api_key(config, key_id, current_user)
    if result == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if result == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
