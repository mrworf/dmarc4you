"""Domain maintenance job detail endpoint."""

from fastapi import APIRouter, Depends, status

from backend.api.errors import api_http_exception
from backend.api.v1.deps import get_config, get_current_user
from backend.api.v1.schemas.common import ErrorResponse
from backend.api.v1.schemas.domains import DomainMaintenanceJobMutationResponse
from backend.config.schema import Config
from backend.services import domain_maintenance_service

router = APIRouter(prefix="/domain-maintenance-jobs", tags=["domain-maintenance-jobs"])


ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}


@router.get("/{job_id}", response_model=DomainMaintenanceJobMutationResponse, responses=ERROR_RESPONSES)
def get_domain_maintenance_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/domain-maintenance-jobs/{job_id}: fetch one maintenance job detail."""
    status_code, job = domain_maintenance_service.get_job_detail(
        config,
        job_id=job_id,
        actor=current_user,
    )
    if status_code == "forbidden":
        raise api_http_exception(status.HTTP_403_FORBIDDEN, "forbidden", "Forbidden")
    if status_code == "not_found":
        raise api_http_exception(status.HTTP_404_NOT_FOUND, "domain_maintenance_job_not_found", "Not found")
    return {"job": job}
