"""Health check endpoint."""

from fastapi import APIRouter, Depends

from backend.api.v1.deps import get_config
from backend.api.v1.schemas.health import HealthResponse, ReadinessResponse
from backend.config.schema import Config
from backend.services.health_service import live_status, readiness_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> dict[str, str]:
    """Return minimal success payload for GET /api/v1/health."""
    return live_status()


@router.get("/ready", response_model=ReadinessResponse)
def readiness(config: Config = Depends(get_config)) -> dict[str, object]:
    """Return readiness for serving API traffic."""
    return readiness_status(config)
