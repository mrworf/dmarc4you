# Domain Lifecycle

## States

A domain can be at least:

- `active`
- `archived`

## Active state

In active state:

- domain is visible to authorized actors
- ingest may proceed if actor/key is authorized
- dashboards using the domain may be rendered normally
- normal search/reporting applies

## Archive transition

Only super-admin may archive a domain.

Effects of archive:

- non-super-admin users lose visibility of the domain
- ingest for the domain is rejected
- dashboards referencing the domain become dormant/inaccessible to non-super-admin users
- the system preserves enough metadata for full restoration
- archived-domain metrics remain visible to super-admin only

## Archived-domain view

Show only high-level information such as:

- domain name
- archived date
- record counts
- artifact counts or storage usage if available
- retention state
- remaining days before deletion
- scheduled deletion date
- pause state and pause reason if any

## Restore

Only super-admin may restore.

Restore effects:

- domain becomes active again
- prior user-domain assignments return
- prior dashboard relationships reactivate
- prior API key domain bindings return
- dormant dashboards resume normal access where otherwise valid

## Delete

Only archived domains may be deleted.

Delete means permanent purge of:

- normalized report data
- archived artifacts
- archived/restorable assignment metadata
- dashboard-domain relationships and domain-specific records

Require explicit confirmation in UI/API.

## Retention

Super-admin may set a retention period for archived domains.

Rules:

- after X days archived, the domain is automatically deleted
- countdown pauses do not count toward elapsed retention time
- retention state must survive restart

## Pause / unpause

Pause requires a reason.

While paused:

- automatic deletion countdown stops
- only restore and unpause actions remain available

On unpause:

- countdown resumes from remaining time

## Scheduler behavior

A retention scheduler should periodically:

- scan archived domains
- ignore paused ones
- calculate expirations
- purge domains that have reached their deadline
- audit every automatic purge
