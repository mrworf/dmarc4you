# API v1 Specification

Base prefix: `/api/v1`

## Authentication modes

- browser session auth for UI-driven endpoints
- API key auth for service/CLI endpoints

## Core API rules

- all authorization is enforced server-side
- domain scope is intersected on every data query and mutation
- archived domains are non-ingestable
- ingest requests create background jobs; they do not synchronously finish full processing

## Auth endpoints

### `POST /api/v1/auth/login`

Request:

```json
{
  "username": "admin",
  "password": "..."
}
```

Response:

```json
{
  "user": {
    "id": "usr_123",
    "username": "admin",
    "role": "super-admin",
    "full_name": null,
    "email": null
  }
}
```

### `POST /api/v1/auth/logout`

Ends current session.

### `GET /api/v1/auth/me`

Returns current authenticated user and effective domain visibility.

### `GET /api/v1/audit`

List audit log entries. **Super-admin only**; 403 for other roles. Session required; 401 if not authenticated.

Query params: `limit` (default 50, max 100), `offset` (default 0).

Response (200): `{ "events": [ { "id", "timestamp", "actor_type", "actor_user_id", "action_type", "outcome", "source_ip", "user_agent", "summary" }, ... ] }`. Events are ordered by timestamp descending.

## Ingest endpoints

### `POST /api/v1/reports/ingest`

Creates an ingest job. **Authentication:** session (cookie) or `Authorization: Bearer <api_key>`. When using an API key, the key must have scope `reports:ingest`; invalid or missing-scope key returns 403. Missing auth returns 401.

Request envelope supports one or more reports. The XML may be plain or compressed and may be base64-encoded for transport.

Example:

```json
{
  "source": "cli",
  "reports": [
    {
      "content_type": "application/xml",
      "content_encoding": "gzip",
      "content_transfer_encoding": "base64",
      "content": "H4sIA...",
      "metadata": {
        "original_filename": "report.xml.gz",
        "submitted_at": "2026-03-08T12:00:00Z"
      }
    }
  ]
}
```

Immediate response:

```json
{
  "job_id": "job_123",
  "state": "queued"
}
```

### `GET /api/v1/ingest-jobs`

List ingest jobs for the current actor. **Authentication:** session or `Authorization: Bearer <api_key>`. With session, returns jobs where `actor_user_id` = current user; with API key, returns jobs where `actor_api_key_id` = that key. Ordered by `submitted_at` desc.

Query params:

- `limit` — optional; default 50, max 100.

Response:

```json
{
  "jobs": [
    { "job_id": "job_xxx", "state": "queued", "submitted_at": "2026-03-08T12:00:00Z" }
  ]
}
```

Returns 401 if not authenticated.

### `GET /api/v1/ingest-jobs/{job_id}`

Job detail with batch and per-report status. **Owner only:** session user must match job's `actor_user_id`, or API key (Bearer) must match job's `actor_api_key_id`. Returns 404 if not found or not owner.

Example:

```json
{
  "job_id": "job_123",
  "state": "completed_with_warnings",
  "accepted_count": 2,
  "duplicate_count": 1,
  "invalid_count": 0,
  "rejected_count": 1,
  "items": [
    {
      "item_id": "item_1",
      "report_type": "aggregate",
      "domain": "example.com",
      "status": "accepted"
    },
    {
      "item_id": "item_2",
      "report_type": "aggregate",
      "domain": "other.example",
      "status": "rejected"
    }
  ]
}
```

### Rejection semantics for ingest

Use generic external error semantics and detailed internal logs.

Recommended whole-request behavior:

- `202 Accepted` or `200 OK` on job creation
- job result carries per-report outcomes
- if synchronous preflight validation rejects the entire envelope format, return `400 Bad Request`
- do not leak archived-domain reasons to external callers

## Search/report endpoints

### `POST /api/v1/search`

Structured + free-text search.

Request example:

```json
{
  "domains": ["example.com"],
  "report_types": ["aggregate"],
  "from": "2026-03-01T00:00:00Z",
  "to": "2026-03-08T00:00:00Z",
  "include": {
    "spf_result": ["fail"]
  },
  "exclude": {
    "disposition": ["none"]
  },
  "query": "google dkim fail",
  "group_by": "source_ip",
  "page": 1,
  "page_size": 50,
  "sort": [{"field": "date", "direction": "desc"}]
}
```

`group_by` is optional and supported for aggregate search on `record_date`, `source_ip`, `resolved_name`, and `resolved_name_domain`.

### `GET /api/v1/reports/aggregate`

List normalized aggregate report records with domain scoping (same as list domains: super-admin sees all, others only assigned domains). Session required.

Query params:

- `domains` — optional; comma-separated domain names (intersected with allowed domains)
- `from`, `to` — optional; time range (Unix timestamp or ISO 8601); rows where (date_begin, date_end) overlaps [from, to]
- `page`, `page_size` — pagination (default page_size=50, max 500)
- `sort_by`, `sort_dir` — e.g. sort_by=date_begin, sort_dir=desc (default)

Response:

```json
{
  "items": [
    { "id": "agg_xxx", "report_id": "...", "org_name": "...", "domain": "example.com", "date_begin": 1735689600, "date_end": 1735776000, "record_date": "2025-01-01", "created_at": "..." }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

### `GET /api/v1/reports/aggregate/{id}`

Get a single aggregate report with all its per-source-IP records. Session required. User must have access to the report's domain (super-admin sees all; others see only assigned domains).

Response (200):

```json
{
  "id": "agg_xxx",
  "report_id": "r1.example.com-20260101",
  "org_name": "Example Org",
  "domain": "example.com",
  "date_begin": 1735689600,
  "date_end": 1735776000,
  "created_at": "2026-01-01T00:00:00Z",
  "records": [
    {
      "id": "rec_xxx",
      "source_ip": "192.0.2.1",
      "resolved_name": "mail.example.net",
      "resolved_name_domain": "example.net",
      "count": 10,
      "disposition": "none",
      "dkim_result": "pass",
      "spf_result": "pass",
      "header_from": "example.com",
      "envelope_from": null,
      "envelope_to": null
    }
  ]
}
```

Errors: 403 if user lacks access to the report's domain; 404 if report not found.

### `GET /api/v1/reports/forensic`

List normalized forensic report records with domain scoping (same as list domains: super-admin sees all, others only assigned domains). Session required.

Query params:

- `domains` — optional; comma-separated domain names (intersected with allowed domains)
- `from`, `to` — optional; time range (Unix timestamp or ISO 8601); filters by `created_at`
- `page`, `page_size` — pagination (default page_size=50, max 500)
- `sort_by`, `sort_dir` — e.g. sort_by=created_at, sort_dir=desc (default)

Response:

```json
{
  "items": [
    {
      "id": "for_xxx",
      "report_id": "...",
      "domain": "example.com",
      "source_ip": "192.0.2.1",
      "resolved_name": "mail.example.net",
      "resolved_name_domain": "example.net",
      "arrival_time": "2026-03-01T12:00:00Z",
      "org_name": "...",
      "header_from": "...",
      "envelope_from": "...",
      "envelope_to": "...",
      "spf_result": "fail",
      "dkim_result": "fail",
      "dmarc_result": "fail",
      "failure_type": "spf",
      "created_at": "..."
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50
}
```

### `GET /api/v1/reports/forensic/{id}`

Get a single forensic report. Session required. User must have access to the report's domain (super-admin sees all; others see only assigned domains).

Response (200):

```json
{
  "id": "for_xxx",
  "report_id": "ruf-example-20260301",
  "domain": "example.com",
  "source_ip": "192.0.2.99",
  "arrival_time": "2026-03-01T12:00:00Z",
  "org_name": "Example Org",
  "header_from": "bad@example.com",
  "envelope_from": null,
  "envelope_to": null,
  "spf_result": "fail",
  "dkim_result": "fail",
  "dmarc_result": "fail",
  "failure_type": "spf",
  "created_at": "2026-03-01T12:05:00Z"
}
```

Errors: 403 if user lacks access to the report's domain; 404 if report not found.

## Dashboard endpoints

### `GET /api/v1/dashboards`

List dashboards owned by the current user. Session required. For **non–super-admin**, dashboards whose scope includes any **archived** domain are excluded (dormant dashboards); super-admin sees all owned dashboards.

Response: `{ "dashboards": [ { "id", "name", "description", "owner_user_id", "created_at", "updated_at", "domain_ids" }, ... ] }`.

### `POST /api/v1/dashboards`

Create a dashboard. Current user becomes owner. Session required. `domain_ids` must be a non-empty subset of domains the user is allowed to see (same as list domains).

Request: `{ "name": "...", "description": "...?", "domain_ids": ["dom_xxx", ...] }`. Response (201): created dashboard with `domain_ids` and `domain_names` (for widget query). 400 if name empty or domain_ids empty; 403 if any domain_id not allowed.

### `GET /api/v1/dashboards/{dashboard_id}`

Get one dashboard with `domain_ids` and `domain_names`. User may view only if they have access to **all** dashboard domains (AGENTS.md). 200 with dashboard; 403 if access denied; 404 if not found.

### `POST /api/v1/dashboards/{dashboard_id}/validate-update`

Dry-run validation before applying scope changes that may remove users. Session required. Owner, admin, or super-admin only.

Request: `{ "domain_ids": ["dom_xxx", ...] }` — proposed new scope.

Response (200): `{ "valid": true/false, "impacted_users": [ { "user_id", "username", "access_level" }, ... ] }`. If `valid` is false, `impacted_users` lists users who would lose access due to the scope change.

403 if caller cannot edit dashboard; 404 if not found.

### `POST /api/v1/dashboards/{dashboard_id}/share`

Add viewer or manager assignment. Session required. Owner, manager with domain access, admin, or super-admin can share.

Request: `{ "user_id": "usr_xxx", "access_level": "viewer" | "manager" }`.

Response (201): `{ "dashboard_id", "user_id", "access_level", "granted_by_user_id", "granted_at" }`.

400 if target user lacks access to all dashboard domains, or if granting manager access to a viewer-role user. 403 if caller cannot share. 404 if dashboard or user not found.

### `GET /api/v1/dashboards/{dashboard_id}/shares`

List users who have been granted access to a dashboard. Session required. Same authorization as get dashboard (user must have access to **all** dashboard domains).

Response (200):

```json
{
  "shares": [
    {
      "user_id": "usr_xxx",
      "username": "alice",
      "access_level": "viewer",
      "granted_by_user_id": "usr_yyy",
      "granted_at": "2026-03-01T00:00:00Z"
    }
  ]
}
```

403 if caller lacks access to dashboard domains; 404 if dashboard not found.

### `DELETE /api/v1/dashboards/{dashboard_id}/share/{user_id}`

Remove a user's dashboard assignment. Session required. Same authorization as share.

204 on success; 403 if caller cannot unshare; 404 if dashboard or assignment not found.

### `GET /api/v1/dashboards/{dashboard_id}/export`

Export a portable YAML definition. Same auth as get dashboard (user must have access to **all** dashboard domains). 403 if access denied; 404 if not found. Response body is YAML with `name`, `description`, and `domains` (list of domain **names**, not ids). Content-Type: `application/x-yaml`.

### `POST /api/v1/dashboards/import`

Import a dashboard from a portable YAML definition with domain remapping. Session required. Request body (JSON):

- `yaml`: string — YAML with keys `name` (required), `description` (optional), `domains` (required list of domain **names**).
- `domain_remap`: object — maps each domain name in the YAML to a `domain_id` in this environment, e.g. `{ "example.com": "dom_xxx", "other.com": "dom_yyy" }`.

Validation: YAML must parse and have non-empty `name` and non-empty `domains`; every name in `domains` must appear as a key in `domain_remap`; every `domain_id` in `domain_remap` must be in the current user's allowed set (same rule as create dashboard). On success a new dashboard is created with that name, description, and remapped domain_ids; owner is the current user.

- **201**: dashboard created; response body is the created dashboard (same shape as GET dashboard).
- **400**: invalid YAML, empty name, empty or missing domains, or a domain name in YAML missing from `domain_remap`.
- **403**: at least one `domain_id` in `domain_remap` is not allowed for the current user.

## Domain/admin endpoints

### `GET /api/v1/domains`

Returns domains visible to the current user: **super-admin** sees all domains (active and archived); **others** see only domains they are assigned to (via `user_domain_assignments`) and only those with `status = active`. Archived domains are hidden from non–super-admins.

Response: each domain object includes `id`, `name`, `status`, `created_at`, and optionally `retention_days`, `retention_delete_at`, `retention_paused` (for archived domains with retention configured).

```json
{
  "domains": [
    { "id": "dom_xxx", "name": "example.com", "status": "active", "created_at": "2026-01-01T00:00:00Z", "retention_days": null, "retention_delete_at": null, "retention_paused": 0 }
  ]
}
```

### `POST /api/v1/domains`

Create a domain. **Super-admin only**; others receive 403.

Request:

```json
{ "name": "example.com" }
```

Response (201): `{ "domain": { "id", "name", "status", "created_at" } }`. Duplicate name → 409. Empty name → 400.

### `POST /api/v1/domains/{domain_id}/archive`

Archive a domain. **Super-admin only**; 403 for others. Domain must exist and be active.

Optional request body: `{ "retention_days": N }` (integer). When present and > 0, the domain is stored with `retention_days` and `retention_delete_at` = archived_at + N days (for use by a future retention scheduler).

On success returns 200 with `{ "domain": { "id", "name", "status": "archived", "created_at", "archived_at", "retention_days"?, "retention_delete_at"? } }`. 400 if domain is already archived; 404 if domain does not exist.

### `POST /api/v1/domains/{domain_id}/restore`

Restore an archived domain. **Super-admin only**; 403 for others. Domain must exist and be archived. On success returns 200 with `{ "domain": { "id", "name", "status": "active", "created_at" } }`. 400 if domain is not archived; 404 if domain does not exist.

### `DELETE /api/v1/domains/{domain_id}`

Permanently delete an archived domain. **Super-admin only**; 403 for others. Domain must exist and have `status = archived`; 400 if active. On success returns 204 No Content. Removes the domain row and related data (user_domain_assignments, dashboard_domain_scope, aggregate_reports for that domain). 404 if domain does not exist.

### `POST /api/v1/domains/{domain_id}/retention`

Set or update the retention policy for an archived domain. **Super-admin only**; 403 for others. Domain must exist and be archived.

Request body:

```json
{
  "retention_days": 30
}
```

`retention_days` must be a positive integer.

On success:
- Sets/updates `retention_days`
- Sets `retention_delete_at = now + retention_days` (if not paused)
- If domain is paused, updates `retention_remaining_seconds` to reflect the new period

Response (200):

```json
{
  "domain": {
    "id": "dom_xxx",
    "name": "example.com",
    "status": "archived",
    "created_at": "...",
    "archived_at": "...",
    "retention_days": 30,
    "retention_delete_at": "...",
    "retention_paused": 0
  }
}
```

Errors: 400 if domain is not archived or `retention_days` is invalid; 403 if not super-admin; 404 if domain not found.

### `POST /api/v1/domains/{domain_id}/retention/pause`

Pause the retention countdown for an archived domain that has retention configured. **Super-admin only**; 403 for others. Domain must exist, be archived, and have `retention_delete_at` set; 400 if not archived, no retention, or already paused.

Optional request body: `{ "reason": "..." }`. On success stores remaining seconds until `retention_delete_at`, sets `retention_paused=1`, and returns 200 with domain (including `retention_paused`, `retention_remaining_seconds`). The retention scheduler will not delete the domain while paused.

### `POST /api/v1/domains/{domain_id}/retention/unpause`

Resume the retention countdown. **Super-admin only**; 403 for others. Domain must exist, be archived, and currently paused; 400 if not paused. On success sets `retention_paused=0`, clears pause fields, and sets `retention_delete_at = now + retention_remaining_seconds`. Returns 200 with domain.

### `GET /api/v1/domains/{domain_id}/stats`

Get report and record counts for a domain. **Super-admin** can retrieve stats for any domain (active or archived); **other roles** can only retrieve stats for active domains they are assigned to.

Response (200):

```json
{
  "domain_id": "dom_xxx",
  "aggregate_reports": 42,
  "forensic_reports": 5,
  "aggregate_records": 128
}
```

Errors: 403 if not authorized (non-super-admin accessing archived or unassigned domain); 404 if domain not found.

### `GET /api/v1/domains/{domain_id}/artifacts`

List artifact IDs for a domain. Same authorization as domain stats: **super-admin** can list for any domain; **other roles** can only list for active domains they are assigned to. Session required.

Response (200):

```json
{
  "domain_id": "dom_xxx",
  "artifacts": ["report-id-1", "report-id-2"]
}
```

Returns empty `artifacts` list if archival is not configured or no artifacts exist.

Errors: 403 if not authorized; 404 if domain not found.

### `GET /api/v1/domains/{domain_id}/artifacts/{artifact_id}`

Download raw artifact bytes. Same authorization as list artifacts. Session required.

Response (200): Raw bytes with `Content-Type: application/octet-stream` and `Content-Disposition: attachment; filename="{artifact_id}.raw"`.

Errors: 403 if not authorized; 404 if domain not found, artifact not found, or archival not configured.

### `GET /api/v1/users`

List users visible to the current admin. **Admin and super-admin only**; 403 for other roles. Session required; 401 if not authenticated.

- **Super-admin** sees all users.
- **Admin** sees users who share at least one domain assignment with the admin.

Response:

```json
{
  "users": [
    {
      "id": "usr_xxx",
      "username": "example_user",
      "full_name": "Example User",
      "email": "user@example.com",
      "role": "viewer",
      "created_at": "2026-01-01T00:00:00Z",
      "created_by_user_id": "usr_yyy",
      "domain_ids": ["dom_aaa", "dom_bbb"]
    }
  ]
}
```

### `POST /api/v1/users`

Create a new user with a random password. **Admin and super-admin only**; 403 for other roles.

- Super-admin can create any role including `super-admin`.
- Admin can create `admin`, `manager`, `viewer` but **not** `super-admin`.

Request:

```json
{
  "username": "new_user",
  "full_name": "New User",
  "email": "new.user@example.com",
  "role": "viewer"
}
```

Response (201):

```json
{
  "user": {
    "id": "usr_xxx",
    "username": "new_user",
    "full_name": "New User",
    "email": "new.user@example.com",
    "role": "viewer",
    "created_at": "2026-01-01T00:00:00Z",
    "created_by_user_id": "usr_yyy",
    "domain_ids": []
  },
  "password": "randomly_generated_password"
}
```

The `password` is returned only in this response. 400 if username empty or invalid role; 409 if username already exists.

### `GET /api/v1/users/{user_id}`

Get a single user by ID. **Admin and super-admin only**; 403 for other roles. Returns 404 if user not found.

Response: `{ "user": { ... } }` (same shape as list item).

### `PUT /api/v1/users/{user_id}`

Update user's username and/or role. **Admin and super-admin only**.

Rules:
- Users cannot edit themselves (no self-edit).
- Admin cannot change another admin's role or a super-admin's anything.
- Admin cannot promote anyone to `super-admin`.

Request:

```json
{
  "username": "new_username",
  "full_name": "Updated User",
  "email": "updated.user@example.com",
  "role": "manager"
}
```

Both fields are optional; omit to leave unchanged. Response: `{ "user": { ... } }`. 403 if not allowed; 404 if not found; 409 if username already exists.

### `DELETE /api/v1/users/{user_id}`

Delete a user (soft-delete). **Admin and super-admin only**.

Rules:
- Cannot delete yourself.
- Admin cannot delete another admin or super-admin.
- Super-admin can delete anyone except themselves.
- If the user owns dashboards, ownership is transferred using deterministic fallback:
  1. Assigned manager with access to all dashboard domains
  2. Admin with access to all dashboard domains (ordered by username)
  3. Super-admin (ordered by username)

Response: 204 No Content on success.

- 400 if attempting to delete yourself.
- 403 if not allowed (role-based).
- 404 if user not found.
- 409 if ownership cannot be transferred (no eligible fallback owner).

### `POST /api/v1/users/{user_id}/reset-password`

Reset user's password to a new random value. **Admin and super-admin only**.

Rules:
- Cannot reset own password.
- Admin cannot reset another admin's or super-admin's password.

Response:

```json
{
  "password": "new_randomly_generated_password"
}
```

403 if not allowed; 404 if user not found.

### `POST /api/v1/users/{user_id}/domains`

Assign one or more domains to a user. **Admin and super-admin only**.

Rules:
- Super-admin can assign any active domain to any user.
- Admin can only assign domains they themselves have.
- Admin cannot assign domains to another admin or super-admin.

Request:

```json
{
  "domain_ids": ["dom_xxx", "dom_yyy"]
}
```

Response: `{ "user": { ... } }` with updated `domain_ids`. 400 if domain_ids empty or domain invalid/inactive; 403 if not allowed; 404 if user not found.

### `DELETE /api/v1/users/{user_id}/domains/{domain_id}`

Remove a domain assignment from a user. **Admin and super-admin only**. Same permission rules as assign.

Response: `{ "user": { ... } }` with updated `domain_ids`. 403 if not allowed; 404 if user not found.

## API key endpoints

**Admin and super-admin only** for create/list/update/delete. Session required; 401 if not authenticated; 403 for other roles.

### `GET /api/v1/apikeys`

List API keys (no raw secret). Super-admin sees all keys; admin sees only keys they created. Response: `{ "keys": [ { "id", "nickname", "description", "domain_ids", "domain_names", "scopes", "created_at" }, ... ] }`.

### `POST /api/v1/apikeys`

Create an API key. Request body: `{ "nickname": "...", "description": "...?", "domain_ids": ["dom_xxx", ...], "scopes": ["reports:ingest", ...] }`. `domain_ids` must be a subset of the caller's allowed domains. Response (201): `{ "id", "nickname", "key": "<raw_secret>" }`. The raw `key` is returned only in this response; store it securely. 400 if nickname empty or no domain_ids or no scopes; 403 if role not allowed or domain_ids not allowed.

### `PUT /api/v1/apikeys/{key_id}`

Update an API key's `nickname`, `description`, and `scopes`. Domain bindings remain immutable after creation. Creator or super-admin only. Response: `{ "key": { "id", "nickname", "description", "domain_ids", "domain_names", "scopes", "created_at" } }`. 400 if nickname empty or no scopes; 403 if not allowed; 404 if key not found.

### `DELETE /api/v1/apikeys/{key_id}`

Revoke an API key. Creator or super-admin only. 204 on success; 403 if not allowed; 404 if key not found.

## Error model

Use a consistent envelope:

```json
{
  "error": {
    "code": "forbidden",
    "message": "Operation not allowed.",
    "details": []
  }
}
```

Guidance:

- detailed internal reasoning goes to logs/audit
- external error messages should be safe and non-enumerating
