# API v1

Base path: `/api/v1`

This guide documents the currently implemented HTTP surface at a high level. For browser writes, the backend enforces CSRF validation through the session flow used by the frontend.

## Authentication

Session endpoints:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `PUT /auth/me`
- `PUT /auth/password`

API key authentication:

- Use `Authorization: Bearer <api-key>`
- Supported on ingest and ingest-job endpoints
- API keys are domain-bound and scope-bound

## Health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check with database status |

## Auth and session

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/login` | Start a browser session and set session/CSRF cookies |
| `POST` | `/auth/logout` | End the current browser session |
| `GET` | `/auth/me` | Return the current user plus domain visibility |
| `PUT` | `/auth/me` | Update the current user profile fields |
| `PUT` | `/auth/password` | Change the current user password and force re-login |

Example login body:

```json
{
  "username": "admin",
  "password": "secret"
}
```

Example login response fields now include:

- `user`
- `password_change_required`

Login throttling:

- keyed by normalized username plus source IP
- after 5 failed attempts in 15 minutes, the next login is blocked for 15 minutes
- blocked responses return `429` with error code `login_throttled`
- error details include `retry_after_seconds`

Password change request:

```json
{
  "current_password": "old secret",
  "new_password": "correct horse battery staple"
}
```

Notes:

- generated passwords require a change at next sign-in
- password changes invalidate all sessions for that user
- new passwords must be 12-128 characters

## Domains and domain maintenance

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/domains` | List visible domains |
| `POST` | `/domains` | Create a domain |
| `GET` | `/domains/{domain_id}` | Domain detail |
| `GET` | `/domains/{domain_id}/stats` | Domain metrics summary |
| `POST` | `/domains/{domain_id}/archive` | Archive a domain |
| `POST` | `/domains/{domain_id}/restore` | Restore an archived domain |
| `POST` | `/domains/{domain_id}/retention` | Set archived-domain retention days |
| `POST` | `/domains/{domain_id}/retention/pause` | Pause retention countdown |
| `POST` | `/domains/{domain_id}/retention/unpause` | Resume retention countdown |
| `DELETE` | `/domains/{domain_id}` | Permanently delete an archived domain |
| `GET` | `/domains/{domain_id}/artifacts` | List archived raw artifacts |
| `GET` | `/domains/{domain_id}/artifacts/{artifact_id}` | Download one archived raw artifact |
| `GET` | `/domain-maintenance-jobs/{job_id}` | Domain maintenance job detail |

## Ingest and search

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/reports/ingest` | Submit one or more report payloads |
| `GET` | `/ingest-jobs` | List ingest jobs for the current user or API key |
| `GET` | `/ingest-jobs/{job_id}` | Fetch ingest job detail |
| `GET` | `/reports/aggregate` | List aggregate reports |
| `GET` | `/reports/aggregate/{report_id}` | Aggregate report detail |
| `GET` | `/reports/forensic` | List forensic reports |
| `GET` | `/reports/forensic/{report_id}` | Forensic report detail |
| `POST` | `/search` | Flat record search |
| `POST` | `/search/grouped` | Hierarchical grouped aggregate search |
| `POST` | `/search/timeseries` | Aggregate time-series search |

Example ingest body:

```json
{
  "source": "cli",
  "reports": [
    {
      "content_type": "application/xml",
      "content_encoding": "",
      "content_transfer_encoding": "base64",
      "content": "PD94bWwgdmVyc2lvbj0iMS4wIj8+..."
    }
  ]
}
```

Search request fields supported today include:

- `domains`
- `from`
- `to`
- `include`
- `exclude`
- `country`
- `query`
- `group_by`
- `page`
- `page_size`

Grouped search uses `grouping` and `path`. Time-series search uses `y_axis`.

## Dashboards

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/dashboards` | List visible dashboards |
| `POST` | `/dashboards` | Create a dashboard |
| `POST` | `/dashboards/import` | Import dashboard YAML with `domain_remap` |
| `GET` | `/dashboards/{dashboard_id}` | Dashboard detail |
| `PUT` | `/dashboards/{dashboard_id}` | Update dashboard fields |
| `DELETE` | `/dashboards/{dashboard_id}` | Delete a dashboard |
| `POST` | `/dashboards/{dashboard_id}/owner` | Transfer ownership |
| `GET` | `/dashboards/{dashboard_id}/export` | Export portable YAML |
| `GET` | `/dashboards/{dashboard_id}/shares` | List share assignments |
| `POST` | `/dashboards/{dashboard_id}/share` | Add or update a share |
| `DELETE` | `/dashboards/{dashboard_id}/share/{user_id}` | Remove a share |
| `POST` | `/dashboards/{dashboard_id}/validate-update` | Validate scope changes before save |

## Users, API keys, and audit

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/users` | List manageable users |
| `POST` | `/users` | Create a user |
| `GET` | `/users/{user_id}` | User detail |
| `PUT` | `/users/{user_id}` | Update a user |
| `DELETE` | `/users/{user_id}` | Delete a user |
| `POST` | `/users/{user_id}/reset-password` | Reset password and return a new one |
| `POST` | `/users/{user_id}/domains` | Assign domains |
| `DELETE` | `/users/{user_id}/domains/{domain_id}` | Remove one domain assignment |
| `GET` | `/apikeys` | List API keys |
| `POST` | `/apikeys` | Create an API key and return the raw secret once |
| `PUT` | `/apikeys/{key_id}` | Update nickname, description, and scopes |
| `DELETE` | `/apikeys/{key_id}` | Revoke an API key |
| `GET` | `/audit` | List audit log entries |

User-management responses now include:

- `must_change_password` on listed and detailed users so the UI can show pending password rotation

## Common response notes

- `401` indicates missing or invalid authentication.
- `429` on `/auth/login` indicates temporary login throttling after repeated failed attempts.
- `403` indicates the caller is authenticated but not authorized.
- `404` is also used to avoid leaking ownership or visibility details.
- Ingest creation returns a queued job immediately; report acceptance happens asynchronously.
