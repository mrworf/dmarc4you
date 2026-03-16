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
- header-from / envelope-from / envelope-to
- override reasons/comments
- multi-value auth_results rows for DKIM/SPF details

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
