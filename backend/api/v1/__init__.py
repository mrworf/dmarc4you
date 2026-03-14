"""API v1 router."""

from fastapi import APIRouter, Depends

from backend.api.v1.handlers import health, auth, domains, reports, dashboards, audit, apikeys, users
from backend.api.v1.deps import validate_csrf

router = APIRouter(prefix="/api/v1", tags=["v1"], dependencies=[Depends(validate_csrf)])
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(domains.router)
router.include_router(reports.reports_router)
router.include_router(reports.ingest_jobs_router)
router.include_router(reports.search_router)
router.include_router(dashboards.router)
router.include_router(audit.router)
router.include_router(apikeys.router)
router.include_router(users.router)
