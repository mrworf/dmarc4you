"""Domain endpoints: GET list (scoped), POST create (super-admin only), artifacts."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import domain_service

router = APIRouter(prefix="/domains", tags=["domains"])


class CreateDomainBody(BaseModel):
    name: str = ""


class ArchiveDomainBody(BaseModel):
    retention_days: int | None = None


class PauseRetentionBody(BaseModel):
    reason: str | None = None


class SetRetentionBody(BaseModel):
    retention_days: int


@router.get("")
def list_domains(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains: list domains visible to current user (super-admin all, others assigned)."""
    items = domain_service.list_domains(config, current_user)
    return {"domains": items}


@router.post("")
def create_domain(
    body: CreateDomainBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains: create domain (super-admin only)."""
    status_code, domain = domain_service.create_domain(
        config,
        (body.name or "").strip(),
        current_user["id"],
        current_user["role"],
    )
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "invalid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name required")
    if status_code == "duplicate":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain name already exists")
    return {"domain": domain}


@router.post("/{domain_id}/archive")
def archive_domain(
    domain_id: str,
    body: ArchiveDomainBody | None = Body(None),
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/archive: archive domain (super-admin only). Optional retention_days in body."""
    retention_days = (body.retention_days if body else None) or None
    status_code, domain = domain_service.archive_domain(
        config, domain_id, current_user["id"], current_user["role"], retention_days=retention_days
    )
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "already_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain already archived")
    return {"domain": domain}


@router.post("/{domain_id}/restore")
def restore_domain(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/restore: restore archived domain (super-admin only)."""
    status_code, domain = domain_service.restore_domain(config, domain_id, current_user["role"])
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "not_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain is not archived")
    return {"domain": domain}


@router.post("/{domain_id}/retention")
def set_retention(
    domain_id: str,
    body: SetRetentionBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/retention: set or update retention (super-admin only)."""
    status_code, domain = domain_service.set_retention(
        config, domain_id, current_user["role"], body.retention_days
    )
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "not_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain is not archived")
    if status_code == "invalid":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="retention_days must be > 0")
    return {"domain": domain}


@router.post("/{domain_id}/retention/pause")
def pause_retention(
    domain_id: str,
    body: PauseRetentionBody | None = Body(None),
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/retention/pause: pause retention (super-admin only). Optional reason in body."""
    reason = (body.reason if body else None) or None
    status_code, domain = domain_service.pause_retention(
        config, domain_id, current_user["role"], reason=reason
    )
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "not_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain is not archived")
    if status_code == "no_retention":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain has no retention configured")
    if status_code == "already_paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Retention already paused")
    return {"domain": domain}


@router.post("/{domain_id}/retention/unpause")
def unpause_retention(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/retention/unpause: unpause retention (super-admin only)."""
    status_code, domain = domain_service.unpause_retention(config, domain_id, current_user["role"])
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "not_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain is not archived")
    if status_code == "not_paused":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Retention is not paused")
    return {"domain": domain}


@router.delete("/{domain_id}", status_code=204)
def delete_domain(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> None:
    """DELETE /api/v1/domains/{domain_id}: delete archived domain (super-admin only). Permanent."""
    status_code, _ = domain_service.delete_domain(config, domain_id, current_user["role"])
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if status_code == "not_archived":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain must be archived to delete")


@router.get("/{domain_id}/stats")
def get_domain_stats(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains/{domain_id}/stats: get report/record counts for domain."""
    status_code, stats = domain_service.get_domain_stats(config, domain_id, current_user)
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return stats


@router.get("/{domain_id}/artifacts")
def list_artifacts(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains/{domain_id}/artifacts: list artifact IDs for domain."""
    status_code, result = domain_service.list_artifacts(config, domain_id, current_user)
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return result


@router.get("/{domain_id}/artifacts/{artifact_id}")
def get_artifact(
    domain_id: str,
    artifact_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> Response:
    """GET /api/v1/domains/{domain_id}/artifacts/{artifact_id}: download raw artifact."""
    status_code, data = domain_service.get_artifact(config, domain_id, artifact_id, current_user)
    if status_code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if status_code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.raw"'},
    )
