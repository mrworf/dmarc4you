# Product Specification

## Product summary

Build a self-hosted DMARC analysis platform that ingests DMARC aggregate (`rua`) and forensic/failure (`ruf`) reports from files, API submissions, and a CLI tool, stores normalized data in SQLite in v1, and exposes interactive dashboards, search, domain administration, API key management, and archival lifecycle controls.

## Primary goals

- Ingest DMARC reports from XML, compressed XML, and RFC-compliant email messages with report attachments.
- Normalize aggregate and forensic data into a queryable backend model.
- Provide interactive dashboards with drill-down, include/exclude filters, and shareable URLs.
- Enforce strict domain-scoped RBAC and domain-bound API keys.
- Provide a clear audit trail for security-sensitive actions.
- Support domain archival, restore, retention, and purge.

## Explicit non-goals for v1

- Multi-tenant/org-in-org support.
- SSO/OIDC/LDAP.
- MFA/2FA.
- Self-service password reset or password change.
- Private/personal dashboard feature.
- Raw full-message storage for forensic reports inside the database.
- Separate worker service/container for jobs.

## Actors and roles

### Super-admin

- Full access to all configured domains.
- Can add domains.
- Can archive, restore, and delete archived domains.
- Can configure archived-domain retention and pause/unpause retention.
- Can create or promote users up to `super-admin`.
- Can change admin domain assignments.
- Can view archived domains and their metrics.

### Admin

- Domain-scoped administrator.
- Can create users up to role `admin`, but cannot create `super-admin`.
- Can manage viewers/managers within their own domain scope.
- Can create/edit/share/delete accessible dashboards.
- Cannot add domains.
- Cannot demote another admin.
- Cannot change an admin's domains.

### Manager

- Can be assigned a subset of domains.
- Can create dashboards.
- Can edit and share assigned dashboards.
- Can assign viewers and other managers to assigned dashboards.
- Cannot perform general admin/domain management.
- Can delete a dashboard only if they are the owner.

### Viewer

- Can view assigned dashboards.
- Can use temporary filters, drill-down, and URL state.
- Cannot save dashboard changes.
- Cannot import/export dashboards.

## Domain visibility model

- `super-admin` sees all domains.
- All other roles see only assigned domains.
- A dashboard may include any subset of domains that the editor is allowed to access.
- A user may only be assigned to a dashboard if they already have access to **all** dashboard domains.

## Authentication

### User authentication

- Local username/password only in v1.
- First boot creates a `super-admin` user with username `admin` and a random password printed to local console.
- No self-service password reset/change in v1.
- Break-glass recovery must be available locally via an admin CLI command.

### API key authentication

- API keys are not tied to users.
- API keys belong to one or more domains.
- API keys also have REST endpoint scopes.
- CLI uses API key only.

## Ingestion rules

- Ingest is asynchronous and handled by a background job.
- Requests may contain multiple reports.
- Acceptance is **per report**, not all-or-nothing.
- A report is accepted only if:
  1. the domain is configured
  2. the domain is not archived
  3. the actor or API key is authorized for that domain
  4. the payload parses successfully
  5. the report is not a duplicate

## UI requirements

- SPA-style frontend with bookmarkable/shareable URLs.
- Dashboards support drill-down, filters, include/exclude conditions, and time-domain selection.
- Viewer state is bookmarkable but not persisted as saved settings.
- Dashboards can be exported and imported as YAML.

## Dashboard rules

- No private/personal dashboards as a product feature.
- Each dashboard has exactly one owner.
- Creator becomes initial owner.
- Viewer can never own a dashboard.
- Admin and super-admin can change ownership.
- Owner deletion fallback is deterministic:
  1. another assigned manager if available
  2. first eligible admin with access to all dashboard domains
  3. eligible super-admin fallback

## Domain archival lifecycle

A domain has lifecycle states:

- `active`
- `archived`

When archived:

- only super-admin can see it
- ingest is rejected
- dashboards touching the domain become dormant for non-super-admin users
- archived view shows only high-level metrics and retention state

When restored:

- prior user-domain assignments return
- prior dashboard relationships reactivate
- API key domain bindings are restored

Archived domains may be deleted permanently. Deletion expunges all related normalized data, archived artifacts, and archived/restorable metadata.
