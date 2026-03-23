"""Ingest, job detail, and aggregate list endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user, get_ingest_actor
from backend.services import ingest_service
from backend.services import search_service

reports_router = APIRouter(prefix="/reports", tags=["reports"])
ingest_jobs_router = APIRouter(prefix="/ingest-jobs", tags=["ingest-jobs"])
search_router = APIRouter(prefix="/search", tags=["search"])


class ReportEnvelopeItem(BaseModel):
    content_type: str = ""
    content_encoding: str = ""
    content_transfer_encoding: str = ""
    content: str = ""


class IngestEnvelope(BaseModel):
    source: str = ""
    reports: list[ReportEnvelopeItem] = []


class SearchRequest(BaseModel):
    domains: list[str] | None = None
    from_ts: str | int | None = Field(default=None, alias="from")
    to_ts: str | int | None = Field(default=None, alias="to")
    include: dict[str, list[str]] | None = None
    exclude: dict[str, list[str]] | None = None
    country: str = ""
    query: str = ""
    group_by: str | None = None
    page: int = 1
    page_size: int = 50

    model_config = {"populate_by_name": True}


class GroupPathPart(BaseModel):
    field: str
    value: str = ""


class GroupedSearchRequest(BaseModel):
    domains: list[str] | None = None
    from_ts: str | int | None = Field(default=None, alias="from")
    to_ts: str | int | None = Field(default=None, alias="to")
    include: dict[str, list[str]] | None = None
    exclude: dict[str, list[str]] | None = None
    country: str = ""
    query: str = ""
    grouping: list[str] = []
    path: list[GroupPathPart] = []
    page: int = 1
    page_size: int = 50

    model_config = {"populate_by_name": True}


class TimeSeriesSearchRequest(BaseModel):
    domains: list[str] | None = None
    from_ts: str | int | None = Field(default=None, alias="from")
    to_ts: str | int | None = Field(default=None, alias="to")
    include: dict[str, list[str]] | None = None
    exclude: dict[str, list[str]] | None = None
    country: str = ""
    query: str = ""
    y_axis: str = "message_count"

    model_config = {"populate_by_name": True}


@reports_router.get("/aggregate")
def get_reports_aggregate(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
    domains: str | None = Query(None, description="Comma-separated domain names to filter"),
    from_ts: str | int | None = Query(None, alias="from", description="Start of time range (Unix or ISO 8601)"),
    to_ts: str | int | None = Query(None, alias="to", description="End of time range (Unix or ISO 8601)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("date_begin"),
    sort_dir: str = Query("desc"),
) -> dict:
    """GET /api/v1/reports/aggregate: list aggregate reports with domain scoping, time filter, pagination."""
    domains_list = [d.strip() for d in domains.split(",")] if domains else None
    return search_service.list_aggregate_reports(
        config,
        current_user,
        domains_param=domains_list,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@reports_router.get("/aggregate/{report_id}")
def get_aggregate_report_detail(
    report_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/reports/aggregate/{id}: single aggregate report with all records."""
    code, report = search_service.get_aggregate_report_detail(config, current_user, report_id)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return report


@reports_router.get("/forensic")
def get_reports_forensic(
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
    domains: str | None = Query(None, description="Comma-separated domain names to filter"),
    from_ts: str | int | None = Query(None, alias="from", description="Start of time range (Unix or ISO 8601)"),
    to_ts: str | int | None = Query(None, alias="to", description="End of time range (Unix or ISO 8601)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
) -> dict:
    """GET /api/v1/reports/forensic: list forensic reports with domain scoping, time filter, pagination."""
    domains_list = [d.strip() for d in domains.split(",")] if domains else None
    return search_service.list_forensic_reports(
        config,
        current_user,
        domains_param=domains_list,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@reports_router.get("/forensic/{report_id}")
def get_forensic_report_detail(
    report_id: str,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/reports/forensic/{id}: single forensic report with all fields."""
    code, report = search_service.get_forensic_report_detail(config, current_user, report_id)
    if code == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if code == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return report


@reports_router.post("/ingest")
def post_reports_ingest(
    body: IngestEnvelope,
    actor: dict = Depends(get_ingest_actor),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/reports/ingest: create ingest job (queued). Session or Bearer API key (scope reports:ingest)."""
    reports = [{"content_type": r.content_type, "content_encoding": r.content_encoding, "content_transfer_encoding": r.content_transfer_encoding, "content": r.content} for r in (body.reports or [])]
    if actor["type"] == "user":
        job_id = ingest_service.create_ingest_job(config, {"source": body.source, "reports": reports}, "user", actor_user_id=actor["user_id"], actor_api_key_id=None)
    else:
        job_id = ingest_service.create_ingest_job(config, {"source": body.source, "reports": reports}, "api_key", actor_user_id=None, actor_api_key_id=actor["key_id"])
    return {"job_id": job_id, "state": "queued"}


@ingest_jobs_router.get("")
def list_ingest_jobs(
    actor: dict = Depends(get_ingest_actor),
    config: Config = Depends(get_config),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    """GET /api/v1/ingest-jobs: list jobs for current user or API key (session or Bearer)."""
    if actor["type"] == "user":
        jobs = ingest_service.list_jobs(config, actor_user_id=actor["user_id"], limit=limit)
    else:
        jobs = ingest_service.list_jobs(config, actor_api_key_id=actor["key_id"], limit=limit)
    return {"jobs": jobs}


@ingest_jobs_router.get("/{job_id}")
def get_ingest_job(
    job_id: str,
    actor: dict = Depends(get_ingest_actor),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/ingest-jobs/{job_id}: job detail with items (owner: user or API key)."""
    if actor["type"] == "user":
        job = ingest_service.get_job_detail(config, job_id, actor_user_id=actor["user_id"])
    else:
        job = ingest_service.get_job_detail(config, job_id, actor_api_key_id=actor["key_id"])
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return job


@search_router.post("")
def post_search(
    body: SearchRequest,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/search: structured + free-text search with domain scoping."""
    return search_service.search_records(
        config,
        current_user,
        domains_param=body.domains,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        include=body.include,
        exclude=body.exclude,
        country=body.country or None,
        query=body.query or None,
        group_by=body.group_by,
        page=body.page,
        page_size=body.page_size,
    )


@search_router.post("/grouped")
def post_grouped_search(
    body: GroupedSearchRequest,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/search/grouped: hierarchical aggregate search for explorer views."""
    try:
        return search_service.search_grouped_records(
            config,
            current_user,
            domains_param=body.domains,
            from_ts=body.from_ts,
            to_ts=body.to_ts,
            include=body.include,
            exclude=body.exclude,
            country=body.country or None,
            query=body.query or None,
            grouping=body.grouping,
            path=[part.model_dump() for part in body.path],
            page=body.page,
            page_size=body.page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@search_router.post("/timeseries")
def post_timeseries_search(
    body: TimeSeriesSearchRequest,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/search/timeseries: aggregate dashboard/search records into daily auth-family trend buckets."""
    return search_service.search_timeseries_records(
        config,
        current_user,
        domains_param=body.domains,
        from_ts=body.from_ts,
        to_ts=body.to_ts,
        include=body.include,
        exclude=body.exclude,
        country=body.country or None,
        query=body.query or None,
        y_axis=body.y_axis,
    )
