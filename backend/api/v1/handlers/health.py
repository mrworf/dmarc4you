"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    """Return minimal success payload for GET /api/v1/health."""
    return {"status": "ok"}
