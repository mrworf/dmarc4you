# Security and Audit

## Security posture for v1

This product is security-sensitive because it handles identity, domain-scoped access, API keys, audit trails, and potentially sensitive email-derived metadata.

## Authentication requirements

### User auth

- local username/password only in v1
- usernames must match `^[A-Za-z0-9_-]+$`
- password hashing: prefer Argon2id; bcrypt acceptable fallback
- no self-service password change/reset in v1
- only admin/super-admin can reset passwords
- only another sufficiently privileged user can demote an admin or super-admin

### Break-glass

Provide a local-only admin CLI command to reset the `admin` password to a newly generated random value and print it locally. It must not be exposed via HTTP.

## Session security

- secure cookie settings where deployment allows
- HttpOnly
- SameSite appropriate for app model
- CSRF protection for browser-authenticated write endpoints
- server-side session invalidation on logout/reset

## API key security

- keys are shown once, hashed at rest
- keys are identified in logs by nickname and internal id, never by raw secret
- keys are domain-bound and scope-bound
- invalid, expired, disabled, or insufficient-scope key usage must be logged and audited

## Authorization invariants

1. Super-admin always has access to all domains.
2. Admin cannot add domains or grant `super-admin`.
3. Only super-admin can change an admin's domain assignments.
4. Dashboard access requires access to all dashboard domains.
5. Viewers can never own dashboards.
6. Archived domains are invisible to non-super-admin users.
7. Archived domains reject ingest even if the actor/key would otherwise be authorized.
8. External errors must not overexpose sensitive domain-state reasons when the product spec forbids it.

## Ingest security

- safe XML parsing only
- decompression limits
- archive recursion limits
- attachment count limits
- total expanded size limits
- malformed input should fail safely per report
- dedupe logic should prevent repeated persistence on retries/restarts

## Raw artifact handling

- archival storage is optional and config-driven
- use compressed storage when enabled
- store backend-agnostic references in DB
- delete artifacts during archived-domain purge

## Audit requirements

Audit at least the following:

- login success/failure
- logout
- user creation/update
- role changes
- domain assignment changes
- API key lifecycle operations
- ingest submissions and ingest denials
- dashboard create/edit/rename/delete/share/ownership changes
- domain archive/restore/delete/retention changes
- break-glass usage

## Login event capture

Capture when available:

- actor identity
- timestamp
- source IP
- user-agent
- success/failure

## API event capture

For API-key-authenticated requests, capture when available:

- API key nickname
- API key id
- source IP
- user-agent
- endpoint/method
- outcome
- domain involved if relevant

## Logging guidance

User-facing config levels:

- `VERBOSE`
- `INFO`
- `WARN`
- `ERROR`

Internally map `VERBOSE` to Python `DEBUG`.

Do not log:

- raw passwords
- raw API keys
- raw full message bodies by default
- secrets embedded in config or environment
