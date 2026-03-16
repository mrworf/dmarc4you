"""Domain API schemas."""

from pydantic import BaseModel


class CreateDomainBody(BaseModel):
    name: str = ""


class ArchiveDomainBody(BaseModel):
    retention_days: int | None = None


class PauseRetentionBody(BaseModel):
    reason: str | None = None


class SetRetentionBody(BaseModel):
    retention_days: int


class DomainSummary(BaseModel):
    id: str
    name: str
    status: str
    created_at: str
    archived_at: str | None = None
    retention_days: int | None = None
    retention_delete_at: str | None = None
    retention_paused: int | bool | None = None
    retention_remaining_seconds: int | None = None


class DomainsListResponse(BaseModel):
    domains: list[DomainSummary]


class DomainMutationResponse(BaseModel):
    domain: DomainSummary


class DomainStatsResponse(BaseModel):
    domain_id: str
    aggregate_reports: int
    aggregate_records: int
    forensic_reports: int
    artifact_count: int | None = None


class ArtifactListResponse(BaseModel):
    domain_id: str
    artifacts: list[str]
