"""Dashboard API schemas."""

from pydantic import BaseModel


class CreateDashboardBody(BaseModel):
    name: str = ""
    description: str = ""
    domain_ids: list[str] = []
    visible_columns: list[str] = []


class DashboardSummary(BaseModel):
    id: str
    name: str
    description: str
    owner_user_id: str
    created_at: str
    updated_at: str
    domain_ids: list[str]
    domain_names: list[str] | None = None
    visible_columns: list[str]


class DashboardsListResponse(BaseModel):
    dashboards: list[DashboardSummary]
