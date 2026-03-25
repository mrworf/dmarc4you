# Domain Lifecycle

Domains move between two operational states:

- `active`
- `archived`

## Active domains

When a domain is active:

- authorized users and dashboards can see it
- ingest is allowed when the user or API key is authorized
- normal search, dashboard, and reporting behavior applies

## Archiving a domain

Only `super-admin` can archive a domain.

Archive effects:

- non-`super-admin` users lose visibility of the domain
- ingest for that domain is rejected
- dashboards that depend on the domain are no longer usable for non-`super-admin` users
- restorable metadata is retained so assignments and bindings can return on restore

## Archived-domain retention

Archived domains can have a retention period in days.

Behavior:

- countdown begins from the archive state
- paused time does not count toward expiration
- retention state survives restarts
- automatic purge removes the domain when its deadline is reached

Only `super-admin` can:

- set retention
- pause retention
- unpause retention

Pause requires a reason.

## Restoring a domain

Only `super-admin` can restore an archived domain.

Restore effects:

- the domain becomes active again
- prior user-domain assignments return
- prior dashboard-domain relationships reactivate
- prior API key bindings return

## Deleting a domain

Only archived domains can be deleted, and deletion is permanent.

Deletion removes:

- normalized report data
- archived artifacts
- archived/restorable assignment metadata
- related dashboard domain links and domain-specific records

## Operational endpoints

These lifecycle actions are exposed through the API:

- `POST /api/v1/domains/{domain_id}/archive`
- `POST /api/v1/domains/{domain_id}/restore`
- `POST /api/v1/domains/{domain_id}/retention`
- `POST /api/v1/domains/{domain_id}/retention/pause`
- `POST /api/v1/domains/{domain_id}/retention/unpause`
- `DELETE /api/v1/domains/{domain_id}`
