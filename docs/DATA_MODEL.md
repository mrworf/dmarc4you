# Data Model

The database is SQLite in v1, but the logical model should not assume SQLite forever.

## Core entities

### Users

Fields:

- `id`
- `username`
- `full_name` (optional)
- `email` (optional)
- `password_hash`
- `role`
- `created_at`
- `created_by_user_id`
- `last_login_at`
- `disabled_at` (optional)

### Domains

Fields:

- `id`
- `name`
- `status` (`active`, `archived`)
- `created_at`
- `archived_at`
- `archived_by_user_id`
- `retention_days`
- `retention_delete_at`
- `retention_paused`
- `retention_paused_at`
- `retention_pause_reason`
- `retention_remaining_seconds` or equivalent resumable counter field
- `monitoring_enabled`
- `monitoring_last_checked_at` (last successful DNS poll)
- `monitoring_next_check_at`
- `monitoring_last_change_at`
- `monitoring_last_triggered_at`
- `monitoring_failure_active`
- `monitoring_last_failure_at`
- `monitoring_last_failure_summary`

### User-domain assignments

Fields:

- `user_id`
- `domain_id`
- `assigned_by_user_id`
- `assigned_at`

For `super-admin`, treat all-domain visibility as role-derived rather than normal assignments.

### API keys

Fields:

- `id`
- `nickname`
- `description`
- `key_hash`
- `enabled`
- `created_by_user_id`
- `created_at`
- `expires_at`
- `last_used_at`
- `last_used_ip`
- `last_used_user_agent`

Related tables:

- `api_key_domains`
- `api_key_scopes`

## Dashboard model

### Dashboards

Fields:

- `id`
- `name`
- `description`
- `owner_user_id`
- `created_by_user_id`
- `created_at`
- `updated_at`
- `visible_columns`
- `is_dormant`
- `dormant_reason`

### Dashboard domain scope

- `dashboard_id`
- `domain_id`

### Dashboard user access

- `dashboard_id`
- `user_id`
- `access_level` (`viewer`, `manager`)
- `granted_by_user_id`
- `granted_at`

### Widgets and filters

Store widget definitions and dashboard filters as structured configuration rows or JSON documents with strong validation.

Dashboards also persist an ordered `visible_columns` list. When no explicit list is stored, the backend applies a default aggregate-analysis column set.

## Ingest model

### Ingest jobs

Fields:

- `id`
- `actor_type` (`user`, `api_key`, `system`)
- `actor_user_id`
- `actor_api_key_id`
- `submitted_at`
- `started_at`
- `completed_at`
- `state` (`queued`, `processing`, `completed`, `completed_with_warnings`, `failed`)
- `last_error`
- `retry_count`

### Ingest job items

Fields:

- `id`
- `job_id`
- `sequence_no`
- `report_type_detected`
- `domain_detected`
- `status` (`accepted`, `duplicate`, `invalid`, `rejected`)
- `status_reason`
- `started_at`
- `completed_at`

### Domain maintenance jobs

Fields:

- `id`
- `domain_id`
- `domain_name`
- `action` (`recompute_aggregate_reports` in the first slice)
- `actor_user_id` (nullable when system/API-key triggered)
- `actor_api_key_id` (nullable)
- `submitted_at`
- `started_at`
- `completed_at`
- `state` (`queued`, `processing`, `completed`, `completed_with_warnings`, `failed`)
- `reports_scanned`
- `reports_skipped`
- `records_updated`
- `last_error`
- `summary`

These jobs are separate from ingest jobs. They exist so admins can refresh derived aggregate fields for one domain without re-submitting source payloads.

DNS monitoring reuses this same job table with action `check_dns_monitoring`.

### Domain DNS monitoring

Per-domain DKIM selectors:

- `domain_id`
- `selector`
- `added_at`

Current state snapshot:

- `domain_id`
- `checked_at`
- `observed_state_json`
- `dmarc_record_raw`
- `spf_record_raw`
- `dkim_records_json`
- `ttl_seconds`
- `error_summary`

This row represents the latest known DNS state plus freshness metadata from successful polling. Successful polls that do not change the normalized DNS values update freshness without creating a new history row. Failed polls do not overwrite this snapshot.

History rows:

- `id`
- `domain_id`
- `changed_at`
- `summary`
- `previous_state_json`
- `current_state_json`
- `dmarc_record_raw`
- `spf_record_raw`
- `dkim_records_json`

Only real DNS state transitions are stored in history. Unchanged polls are not written, and missing/restored observations are stored as explicit state transitions.

### Source files / archived artifacts

Fields:

- `id`
- `job_id`
- `storage_backend`
- `storage_key`
- `original_filename`
- `content_type`
- `content_hash`
- `compressed_size`
- `stored_at`

### Aggregate reports

Suggested normalized fields:

- report org name
- report id
- date range start/end
- report contact email / extra contact info / reporter errors
- policy domain
- adkim / aspf / p / sp / pct
- source IP
- resolved hostname (optional)
- resolved hostname domain/grouping key (optional)
- country code/name/provider (optional)
- message count
- disposition
- DKIM result
- SPF result
- DKIM alignment
- SPF alignment
- DMARC alignment
- header-from / envelope-from / envelope-to
- override reasons/comments
- multi-value auth_results rows for DKIM/SPF details

`header_from` is the visible RFC5322.From domain used as the DMARC alignment anchor. `dkim_alignment` and `spf_alignment` capture strict/relaxed/none/unknown outcomes, and `dmarc_alignment` captures the final pass/fail/unknown outcome for the row.

### Forensic reports

Store normalized and searchable fields only:

- reported domain
- source IP
- resolved hostname (optional)
- resolved hostname domain/grouping key (optional)
- country code/name/provider (optional)
- arrival time
- reporting organization
- envelope/header identifiers
- SPF/DKIM/DMARC result fields
- failure categories
- artifact linkage if archival is enabled

Do not store raw full message bodies in the DB.

## Audit model

### Audit log

Fields:

- `id`
- `timestamp`
- `actor_type`
- `actor_user_id`
- `actor_api_key_id`
- `actor_label`
- `action_type`
- `target_type`
- `target_id`
- `target_label`
- `domain_id`
- `domain_name`
- `source_ip`
- `user_agent`
- `outcome`
- `summary`
- `metadata_json`

## Restoration state for archived domains

Need restorable metadata for:

- prior user-domain assignments
- prior dashboard accessibility/ownership context if needed
- prior API key domain bindings

Prefer dedicated history/snapshot tables over ad hoc JSON blobs when relationships need selective restore.
