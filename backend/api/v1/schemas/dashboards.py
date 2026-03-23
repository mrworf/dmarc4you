"""Dashboard API schemas."""

from pydantic import BaseModel


class CreateDashboardBody(BaseModel):
    name: str = ""
    description: str = ""
    domain_ids: list[str] = []
    visible_columns: list[str] = []
    chart_y_axis: str = "message_count"


class DashboardOwnerSummary(BaseModel):
    id: str
    username: str
    full_name: str | None = None
    email: str | None = None


class DashboardSummary(BaseModel):
    id: str
    name: str
    description: str
    owner_user_id: str
    owner: DashboardOwnerSummary | None = None
    created_at: str
    updated_at: str
    domain_ids: list[str]
    domain_names: list[str] | None = None
    visible_columns: list[str]
    chart_y_axis: str


class DashboardsListResponse(BaseModel):
    dashboards: list[DashboardSummary]
