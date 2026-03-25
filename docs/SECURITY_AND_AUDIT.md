# Security and Audit

This service is security-sensitive because it manages local identities, domain-scoped authorization, API keys, ingest workflows, and archived report data.

## Authentication

User auth:

- local username/password only
- bootstrap `admin` account is created on first startup
- no self-service password reset or password change flow
- password resets are admin operations

Break-glass recovery:

- `python -m cli reset-admin-password [config.yaml]`
- local-only workflow
- prints a newly generated password

Browser session protections:

- HttpOnly session cookie
- CSRF cookie and backend CSRF enforcement on write requests
- configurable `Secure` and `SameSite` cookie settings

## Authorization rules

- `super-admin` always has access to all domains.
- Only `super-admin` can add domains, archive or restore domains, delete archived domains, or change an admin's domain assignments.
- `admin` can create users up to `admin`, but cannot grant `super-admin`.
- Dashboard access requires access to all dashboard domains.
- Viewers cannot own dashboards.
- Archived domains are hidden from non-`super-admin` users and reject ingest.

## API keys

- API keys are not user-bound.
- Keys are domain-bound and scope-bound.
- The raw secret is shown only once at creation time.
- Use `Authorization: Bearer <api-key>` on supported endpoints.

For ingest automation, the relevant scope is:

- `reports:ingest`

## Audit coverage

The system records audit entries for security-relevant actions including:

- login attempts
- logout
- user create, update, delete, and password reset
- role or domain-assignment changes
- API key create, update, and delete
- ingest submissions and denials
- dashboard create, update, share, ownership transfer, and delete
- domain archive, restore, retention updates, and deletion

Audit log endpoint:

- `GET /api/v1/audit`

This endpoint is intended for `super-admin`.

## Logging guidance

Configured log levels:

- `VERBOSE`
- `INFO`
- `WARN`
- `ERROR`

Do not treat logs as a place to store secrets. In particular, avoid logging:

- raw passwords
- raw API keys
- full message bodies by default
- config secrets copied from the environment

## Dependency audits

The repository enforces dependency vulnerability checks in CI for both shipped dependency sets:

- frontend production dependencies via `npm audit --omit=dev --audit-level=moderate`
- backend Python dependencies via `pip-audit -r requirements.txt`

Python test-only packages are intentionally kept out of `requirements.txt` and belong in `requirements-dev.txt` so the audit gate matches shipped/runtime dependencies.

Run the same gate locally before pushing changes:

```bash
bash scripts/check_dependency_audits.sh
```

This is a CI security gate rather than a unit test. It is intended to fail when known moderate-or-higher vulnerabilities are present in committed dependencies.
