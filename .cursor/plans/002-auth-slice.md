# Plan: Auth slice (Phase 1 — login, logout, me, session, audit)

## Goal

Implement the Auth vertical slice: session-based login/logout, GET /api/v1/auth/me (current user + domain visibility placeholder), username validation, and audit logging of login events. No domain CRUD; domain visibility for /me is “all” for super-admin and empty list for others until Domain slice.

## Why this slice

- Bootstrap slice is done (config, migrations, health, bootstrap admin).
- Auth slice is next in `docs/IMPLEMENTATION_PLAN.md`; required before Domain slice and any UI that needs “current user”.
- Delivers: POST login, POST logout, GET me, server-side sessions, username regex, audit login success/failure.

## Scope (in)

- **POST /api/v1/auth/login**: body `{ username, password }`; validate username with `^[A-Za-z0-9_-]+$`; verify password; create server-side session; set HttpOnly session cookie; write audit event (success or failure); return `{ user: { id, username, role } }`. On failure: 401, do not leak reason (log/audit only).
- **POST /api/v1/auth/logout**: invalidate current session (server-side), clear session cookie.
- **GET /api/v1/auth/me**: require session; return current user `{ id, username, role }` plus effective domain visibility. Until Domain slice: super-admin → e.g. `all_domains: true` or `domain_ids: null`; others → `domain_ids: []`.
- **Session storage**: persisted (e.g. SQLite table) so restart does not drop sessions; session cookie: HttpOnly, SameSite (Lax or Strict), secure when possible; configurable secret for signing/session id generation.
- **Audit**: minimal audit log table; on login success/failure write event (actor_user_id or null, action_type e.g. `login_success`/`login_failure`, outcome, source_ip, timestamp). Do not expose audit to API in this slice.
- **Config**: add session secret (or generate default) and optional cookie/session settings.

## Scope (out)

- Domain table or user-domain assignments (Domain slice).
- API key auth (Ingest slice).
- CSRF tokens (can be added later; not in plan).
- Password change/reset or break-glass CLI (Phase 6).
- Audit browse/search UI (Phase 6).

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/storage/sqlite/migrations/002_sessions_audit.sql` | Create `sessions` table (id, user_id, created_at, expires_at, etc.) and `audit_log` table (minimal fields: id, timestamp, actor_type, actor_user_id, action_type, outcome, source_ip, user_agent, summary). |
| `backend/auth/session.py` | Session create/lookup/invalidate using storage; generate secure session id; optional expiry. |
| `backend/auth/user_lookup.py` | Look up user by id (and by username for login). Thin wrapper over DB. |
| `backend/auth/audit.py` | Write audit event (e.g. login_success, login_failure) with actor_user_id, action_type, outcome, source_ip, user_agent. |
| `backend/services/auth_service.py` | Login (validate username, verify password, create session, audit); logout (invalidate session); get_current_user (from session). |
| `backend/api/v1/handlers/auth.py` | POST login, POST logout, GET me; call auth_service; set/clear cookie; return user/domain visibility. |
| `backend/api/v1/deps.py` or `backend/auth/deps.py` | Dependency: get current user from session cookie; return user or 401. |
| `backend/config/schema.py` | Add session_secret, session_cookie_name, session_max_age_days (or similar). |
| `tests/integration/test_auth.py` | Login success returns 200 and user; login wrong password 401; login invalid username 401; logout clears session; me with valid session returns user; me without session 401; audit has login event. |

### Edit

| Path | Change |
|------|--------|
| `backend/config/__init__.py` | Load new session config keys (with safe defaults). |
| `backend/app.py` | Register auth routes under /api/v1 (e.g. include auth router with prefix /auth). |
| `backend/api/v1/__init__.py` | Include auth router. |
| `docs/IMPLEMENTATION_PLAN.md` | Mark Auth slice done. |
| `docs/API_V1.md` | Optional: document /me response shape for domain visibility (e.g. `all_domains`, `domain_ids`). |

---

## Acceptance criteria

1. **POST /api/v1/auth/login** with valid username/password: 200, body `{ user: { id, username, role } }`, session cookie set (HttpOnly).
2. **POST /api/v1/auth/login** with wrong password: 401; no user info leaked; audit and logs record failure.
3. **POST /api/v1/auth/login** with invalid username (e.g. empty or invalid chars): 401 or 422; audit/log as needed.
4. **POST /api/v1/auth/logout** with valid session: 200; session invalidated; cookie cleared.
5. **GET /api/v1/auth/me** with valid session: 200, body includes user (id, username, role) and domain visibility (super-admin: all; others: empty list).
6. **GET /api/v1/auth/me** without session or with invalid session: 401.
7. **Session persistence**: after app restart, existing session cookie still authenticates until expiry/invalidation.
8. **Audit**: at least one audit row per login attempt (success or failure) with action_type and outcome.

---

## Tests and validation

1. **Integration tests** (`tests/integration/test_auth.py`):
   - Login with valid credentials → 200, user in body, cookie present.
   - Login with wrong password → 401, no session.
   - Login with invalid username → 401 or 422.
   - Logout with session → 200, subsequent me returns 401.
   - Me with valid session → 200, user + domain visibility.
   - Me without cookie → 401.
   - (Optional) One test that audit_log contains a row for a login attempt.
2. **Manual**: Start app, POST login, GET me with cookie, POST logout, GET me again.
3. **Run**: `pytest tests/` including new auth tests.

---

## Risks and mitigations

- **Session secret**: Must be configurable; generate a random default if missing and log a warning (or fail fast in production). Prefer fail-fast if no secret in config.
- **Leaking failure reason**: Use same 401 for wrong password and invalid username; log/audit reason only (per AGENTS.md and SECURITY_AND_AUDIT).
- **Cookie scope**: Use path=/ and SameSite=Lax (or Strict) per SECURITY_AND_AUDIT.

---

## Dependencies

- Bootstrap: users table, password hash in auth/password.py.
- SECURITY_AND_AUDIT: username `^[A-Za-z0-9_-]+$`; HttpOnly, SameSite; do not leak sensitive reasons to client.
- DATA_MODEL: audit log fields; sessions can be minimal (id, user_id, created_at, expires_at).
