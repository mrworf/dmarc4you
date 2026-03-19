"""Domain API schemas."""

from __future__ import annotations

from pydantic import BaseModel


class DomainMaintenanceJobSummary(BaseModel):
    job_id: str
    domain_id: str
    domain_name: str
    action: str
    actor_user_id: str | None = None
    actor_api_key_id: str | None = None
    state: str
    submitted_at: str
    started_at: str | None = None
    completed_at: str | None = None
    reports_scanned: int = 0
    reports_skipped: int = 0
    records_updated: int = 0
    last_error: str | None = None
    summary: str | None = None


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
    monitoring_enabled: int | bool | None = None
    monitoring_last_checked_at: str | None = None
    monitoring_next_check_at: str | None = None
    monitoring_last_change_at: str | None = None
    monitoring_failure_active: int | bool | None = None
    monitoring_last_failure_at: str | None = None
    monitoring_last_failure_summary: str | None = None
    latest_maintenance_job: DomainMaintenanceJobSummary | None = None


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


class DomainMaintenanceJobMutationResponse(BaseModel):
    job: DomainMaintenanceJobSummary


class DomainMaintenanceJobListResponse(BaseModel):
    jobs: list[DomainMaintenanceJobSummary]


class DomainMonitoringSettingsBody(BaseModel):
    enabled: bool = False
    dkim_selectors: list[str] = []


class DomainMonitoringRecordState(BaseModel):
    status: str
    host: str
    raw_value: str | None = None
    parsed: dict[str, object] | None = None
    explanation: str | None = None
    summary: str | None = None
    ttl_seconds: int | None = None


class DomainMonitoringCurrentState(BaseModel):
    checked_at: str
    ttl_seconds: int | None = None
    error_summary: str | None = None
    dmarc: DomainMonitoringRecordState
    spf: DomainMonitoringRecordState
    dkim: list[DomainMonitoringRecordState]


class DomainMonitoringHistoryEntry(BaseModel):
    id: str
    changed_at: str
    summary: str
    overall_direction: str
    changes: list[dict[str, object]]
    previous_state: dict[str, object] | None = None
    current_state: dict[str, object]


class DomainMonitoringCheckResponse(BaseModel):
    state: str


class DomainMonitoringResponse(BaseModel):
    domain: DomainSummary
    dkim_selectors: list[str]
    current_state: DomainMonitoringCurrentState | None = None
    history: list[DomainMonitoringHistoryEntry]


class DomainMonitoringTimelineResponse(BaseModel):
    domain: DomainSummary
    last_checked_at: str | None = None
    history: list[DomainMonitoringHistoryEntry]
