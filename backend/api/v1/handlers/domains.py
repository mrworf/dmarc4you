"""Domain endpoints: GET list (scoped), POST create (super-admin only), artifacts."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import Response

from backend.api.errors import api_http_exception
from backend.api.v1.schemas.common import ErrorResponse
from backend.api.v1.schemas.domains import (
    ArchiveDomainBody,
    ArtifactListResponse,
    CreateDomainBody,
    DomainMaintenanceJobListResponse,
    DomainMaintenanceJobMutationResponse,
    DomainMutationResponse,
    DomainStatsResponse,
    DomainsListResponse,
    PauseRetentionBody,
    SetRetentionBody,
)
from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services import domain_maintenance_service, domain_service

router = APIRouter(prefix="/domains", tags=["domains"])


ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.get("", response_model=DomainsListResponse, responses=ERROR_RESPONSES)
def list_domains(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains: list domains visible to current user (super-admin all, others assigned)."""
    items = domain_service.list_domains(config, current_user)
    return {"domains": items}


@router.post("", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "invalid":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "invalid_domain_name", "name required")
    if status_code == "duplicate":
        raise api_http_exception(status.HTTP_409_CONFLICT, "domain_conflict", "Domain name already exists")
    return {"domain": domain}


@router.post("/{domain_id}/archive", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "already_archived":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "domain_already_archived", "Domain already archived")
    return {"domain": domain}


@router.post("/{domain_id}/restore", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
def restore_domain(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/restore: restore archived domain (super-admin only)."""
    status_code, domain = domain_service.restore_domain(config, domain_id, current_user["role"])
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "not_archived":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "domain_not_archived", "Domain is not archived")
    return {"domain": domain}


@router.post("/{domain_id}/retention", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "not_archived":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "domain_not_archived", "Domain is not archived")
    if status_code == "invalid":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "invalid_retention_days", "retention_days must be > 0")
    return {"domain": domain}


@router.post("/{domain_id}/retention/pause", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "not_archived":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "domain_not_archived", "Domain is not archived")
    if status_code == "no_retention":
        raise api_http_exception(
            status.HTTP_400_BAD_REQUEST,
            "domain_retention_missing",
            "Domain has no retention configured",
        )
    if status_code == "already_paused":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "retention_already_paused", "Retention already paused")
    return {"domain": domain}


@router.post("/{domain_id}/retention/unpause", response_model=DomainMutationResponse, responses=ERROR_RESPONSES)
def unpause_retention(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/retention/unpause: unpause retention (super-admin only)."""
    status_code, domain = domain_service.unpause_retention(config, domain_id, current_user["role"])
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "not_archived":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "domain_not_archived", "Domain is not archived")
    if status_code == "not_paused":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "retention_not_paused", "Retention is not paused")
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "not_archived":
        raise api_http_exception(
            status.HTTP_400_BAD_REQUEST,
            "domain_delete_requires_archive",
            "Domain must be archived to delete",
        )


@router.get("/{domain_id}/stats", response_model=DomainStatsResponse, responses=ERROR_RESPONSES)
def get_domain_stats(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains/{domain_id}/stats: get report/record counts for domain."""
    status_code, stats = domain_service.get_domain_stats(config, domain_id, current_user)
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    return stats


@router.get("/{domain_id}/artifacts", response_model=ArtifactListResponse, responses=ERROR_RESPONSES)
def list_artifacts(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains/{domain_id}/artifacts: list artifact IDs for domain."""
    status_code, result = domain_service.list_artifacts(config, domain_id, current_user)
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
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
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "artifact_not_found", "Not found")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{artifact_id}.raw"'},
    )


@router.post(
    "/{domain_id}/recompute",
    response_model=DomainMaintenanceJobMutationResponse,
    responses=ERROR_RESPONSES,
)
def enqueue_domain_recompute(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/domains/{domain_id}/recompute: enqueue aggregate recompute maintenance job."""
    status_code, job = domain_maintenance_service.enqueue_recompute_job(
        config,
        domain_id=domain_id,
        actor=current_user,
    )
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    if status_code == "conflict":
        raise api_http_exception(
            status.HTTP_409_CONFLICT,
            "domain_maintenance_job_conflict",
            "A recompute job is already queued or running for this domain",
        )
    return {"job": job}


@router.get(
    "/{domain_id}/maintenance-jobs",
    response_model=DomainMaintenanceJobListResponse,
    responses=ERROR_RESPONSES,
)
def list_domain_maintenance_jobs(
    domain_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domains/{domain_id}/maintenance-jobs: list maintenance jobs visible for this domain."""
    status_code, jobs = domain_maintenance_service.list_domain_jobs(
        config,
        domain_id=domain_id,
        actor=current_user,
    )
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_not_found", "Not found")
    return {"jobs": jobs or []}
