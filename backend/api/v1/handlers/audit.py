"""Audit endpoint: GET /audit (super-admin only)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def get_audit(
    limit: int = 50,
    offset: int = 0,
    action_type: str | None = Query(default=None, alias="action_type"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    actor: str | None = Query(default=None),
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/audit: list audit log entries with optional filters. Super-admin only; 403 for others."""
    events, err = audit_service.list_audit_events(
        config,
        current_user,
        limit=limit,
        offset=offset,
        action_type=action_type,
        from_date=from_date,
        to_date=to_date,
        actor_user_id=actor,
    )
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"events": events}
