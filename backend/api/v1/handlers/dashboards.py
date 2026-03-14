"""Dashboard endpoints: POST create, GET list, GET/PUT/DELETE by id, POST owner, GET export, POST import, share, unshare, validate-update."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import dashboard_service

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


class CreateDashboardBody(BaseModel):
    name: str = ""
    description: str = ""
    domain_ids: list[str] = []


class UpdateDashboardBody(BaseModel):
    name: str | None = None
    description: str | None = None
    domain_ids: list[str] | None = None


class TransferOwnershipBody(BaseModel):
    user_id: str


class ImportDashboardBody(BaseModel):
    yaml: str = ""
    domain_remap: dict[str, str] = {}


class ShareDashboardBody(BaseModel):
    user_id: str
    access_level: str = "viewer"


class ValidateUpdateBody(BaseModel):
    domain_ids: list[str] = []


@router.post("", status_code=201)
def post_dashboard(
    body: CreateDashboardBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/dashboards: create dashboard (current user = owner). domain_ids must be subset of allowed."""
    status_code, dashboard = dashboard_service.create_dashboard(
        config,
        (body.name or "").strip(),
        body.description or "",
        body.domain_ids or [],
        current_user["id"],
        current_user,
    )
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "invalid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name required and at least one domain")
    if not dashboard:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid")
    return dashboard


@router.get("")
def list_dashboards(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/dashboards: list dashboards owned by current user (dormant excluded for non-super-admin)."""
    items = dashboard_service.list_dashboards(config, current_user)
    return {"dashboards": items}


@router.post("/import", status_code=201)
def post_dashboard_import(
    body: ImportDashboardBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/dashboards/import: import dashboard from YAML + domain_remap; owner = current user."""
    code, dashboard = dashboard_service.import_dashboard_yaml(
        config, body.yaml or "", body.domain_remap or {}, current_user
    )
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if code == "invalid" or not dashboard:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YAML or domain_remap: name and domains required; every domain name must be in domain_remap",
        )
    return dashboard


@router.get("/{dashboard_id}")
def get_dashboard(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/dashboards/{id}: dashboard + domain_ids + domain_names. 403 if user lacks access; 404 if not found."""
    code, dashboard = dashboard_service.get_dashboard(config, dashboard_id, current_user)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return dashboard


@router.put("/{dashboard_id}")
def put_dashboard(
    dashboard_id: str,
    body: UpdateDashboardBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """PUT /api/v1/dashboards/{id}: update dashboard name, description, domain_ids. Owner/admin/super-admin only."""
    code, dashboard = dashboard_service.update_dashboard(
        config,
        dashboard_id,
        body.name,
        body.description,
        body.domain_ids,
        current_user,
    )
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if code == "invalid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name required and at least one domain",
        )
    return dashboard


@router.delete("/{dashboard_id}", status_code=204)
def delete_dashboard_endpoint(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> None:
    """DELETE /api/v1/dashboards/{id}: delete dashboard. Owner/admin/super-admin only."""
    code, _ = dashboard_service.delete_dashboard(config, dashboard_id, current_user)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/{dashboard_id}/owner")
def transfer_ownership(
    dashboard_id: str,
    body: TransferOwnershipBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/dashboards/{id}/owner: transfer ownership to another user. Admin/super-admin only."""
    code, dashboard = dashboard_service.transfer_dashboard_ownership(
        config, dashboard_id, body.user_id, current_user
    )
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    if code == "user_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if code == "invalid_owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid owner: viewer cannot own dashboards or user lacks access to dashboard domains",
        )
    return dashboard


@router.get("/{dashboard_id}/export")
def export_dashboard(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> Response:
    """GET /api/v1/dashboards/{id}/export: portable YAML (name, description, domains). Same auth as get dashboard."""
    yaml_str, err = dashboard_service.export_dashboard_yaml(config, dashboard_id, current_user)
    if err == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return Response(content=yaml_str or "", media_type="application/x-yaml")


@router.get("/{dashboard_id}/shares")
def list_dashboard_shares(
    dashboard_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/dashboards/{id}/shares: list users with access to dashboard."""
    code, shares = dashboard_service.list_dashboard_shares(config, dashboard_id, current_user)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return {"shares": shares or []}


@router.post("/{dashboard_id}/share", status_code=201)
def share_dashboard(
    dashboard_id: str,
    body: ShareDashboardBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/dashboards/{id}/share: add viewer or manager assignment."""
    code, result = dashboard_service.share_dashboard(
        config, dashboard_id, body.user_id, body.access_level, current_user
    )
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    if code == "user_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if code == "invalid_target":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have access to all dashboard domains",
        )
    if code == "invalid_access_level":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid access level or viewer cannot be granted manager access",
        )
    return result


@router.delete("/{dashboard_id}/share/{user_id}", status_code=204)
def unshare_dashboard(
    dashboard_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> None:
    """DELETE /api/v1/dashboards/{id}/share/{user_id}: remove assignment."""
    code = dashboard_service.unshare_dashboard(config, dashboard_id, user_id, current_user)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")
    if code == "assignment_not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@router.post("/{dashboard_id}/validate-update")
def validate_dashboard_update(
    dashboard_id: str,
    body: ValidateUpdateBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/dashboards/{id}/validate-update: dry-run validation before scope changes."""
    code, result = dashboard_service.validate_dashboard_update(
        config, dashboard_id, body.domain_ids or [], current_user
    )
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return result
