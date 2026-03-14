# Plan: Domain slice (Phase 1 — create/list domains, role/domain visibility, basic admin UI)

## Goal

Implement the Domain vertical slice: domains table and user-domain assignments, create domain (super-admin only), list domains (scoped by role), optional assign-user-to-domain API so non-super-admins see only assigned domains, update /me with real domain_ids, and a minimal admin UI (login page + domains list + add domain for super-admin). No archive/restore/delete or retention in this slice.

## Why this slice

- Bootstrap and Auth slices are done.
- Domain slice is next in `docs/IMPLEMENTATION_PLAN.md`; required before Ingest (domains must exist to accept reports) and before Dashboards (domain-scoped data).
- Delivers: GET/POST /api/v1/domains, role-based list visibility, minimal admin UI page.

## Scope (in)

- **Schema**: `domains` table (id, name, status, created_at; nullable archived_at, archived_by_user_id, retention_* for future). `user_domain_assignments` (user_id, domain_id, assigned_by_user_id, assigned_at).
- **Policy**: Only super-admin may create domains. List: super-admin sees all active domains; others see only domains they are assigned to. Only super-admin may assign users to domains.
- **API**: GET /api/v1/domains (returns list scoped by current user). POST /api/v1/domains (super-admin only; body e.g. { name }). Optional: POST /api/v1/users/{user_id}/domains (super-admin only; body e.g. { domain_id } or { domain_ids }) to assign.
- **/me**: Update response so non-super-admin `domain_ids` are loaded from user_domain_assignments (super-admin keeps all_domains true / domain_ids as-is).
- **Frontend**: Minimal SPA shell: static files served by backend; one page that (1) calls GET /me, (2) if 401 shows login form (POST /api/v1/auth/login then redirect/reload), (3) if 200 shows “admin” area with GET /api/v1/domains (list); if user.role === 'super-admin' show form to POST /api/v1/domains (add domain). No full router required; single-page flow (login → domains) is enough.
- **Audit**: Optionally audit domain create and user-domain assign (can be minimal: action_type, outcome, actor_user_id).

## Scope (out)

- Archive, restore, delete domain (Phase 5).
- Retention policy endpoints (Phase 5).
- User CRUD (GET/POST/PUT users, reset-password) — only “assign domains to user” in this slice if included.
- API keys, dashboards, ingest, search.

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/storage/sqlite/migrations/003_domains_user_assignments.sql` | Create `domains` table (id, name, status, created_at, nullable archived_*, retention_*). Create `user_domain_assignments` (user_id, domain_id, assigned_by_user_id, assigned_at). |
| `backend/policies/domain_policy.py` | can_create_domain(user), can_assign_domains_to_user(actor, target_user) — super-admin only. |
| `backend/services/domain_service.py` | create_domain(config, name, actor_user_id), list_domains(config, current_user), assign_user_to_domain(config, user_id, domain_id, actor_user_id). |
| `backend/api/v1/handlers/domains.py` | GET /domains (scoped list), POST /domains (super-admin, body { name }). Optional: POST /users/{user_id}/domains. |
| `backend/api/v1/schemas/domains.py` or inline | Request/response shapes for domain create and list. |
| `frontend/index.html` | Single page: login form or (after auth) domains list + add form for super-admin; calls /me, /auth/login, /domains. |
| `frontend/css/main.css` | Minimal styles. |
| `frontend/js/app.js` | Fetch /me; if 401 show login; on success fetch /domains and render list; if super-admin render add form and handle submit. |
| `tests/integration/test_domains.py` | Create domain as super-admin (201/200); list as super-admin returns all; list as non-super-admin returns only assigned; create as non-super-admin 403; optional assign and list. |
| `tests/unit/test_domain_policy.py` or in integration | can_create_domain only for super-admin. |

### Edit

| Path | Change |
|------|--------|
| `backend/api/v1/__init__.py` | Include domains router. |
| `backend/services/auth_service.py` or `backend/api/v1/handlers/auth.py` | /me: load domain_ids from user_domain_assignments for non-super-admin. |
| `backend/app.py` | Mount static file serving for frontend (e.g. /app or / → frontend/). |
| `docs/IMPLEMENTATION_PLAN.md` | Mark Domain slice done. |
| `docs/API_V1.md` | Document GET/POST /domains request/response and optional POST /users/{id}/domains. |

---

## Acceptance criteria

1. **POST /api/v1/domains** as super-admin with body `{ "name": "example.com" }`: 201 or 200, domain created with status active.
2. **POST /api/v1/domains** as non-super-admin: 403.
3. **GET /api/v1/domains** as super-admin: 200, list includes all active domains.
4. **GET /api/v1/domains** as user with assignments: 200, list includes only assigned domains.
5. **GET /api/v1/auth/me** for non-super-admin returns `domain_ids` from user_domain_assignments.
6. **Optional**: POST /api/v1/users/{user_id}/domains with body { domain_id } as super-admin: user is assigned; GET /domains as that user returns that domain.
7. **UI**: Opening the app unauthenticated shows login; after login, domains list is visible; as super-admin, add-domain form is visible and submitting creates a domain.

---

## Tests and validation

1. **Integration**: Create domain as super-admin; list domains as super-admin (contains new domain); create domain as non-super-admin → 403; list as user with no assignments → empty list; (if implemented) assign user to domain, list as that user → contains assigned domain.
2. **Unit** (optional): Domain policy: can_create_domain(super_admin) true, can_create_domain(admin) false.
3. **Manual**: Serve app, log in, open domains page, add domain as super-admin.
4. **Run**: `pytest tests/` passes.

---

## Risks and mitigations

- **Domain name validation**: Accept a minimal format (e.g. non-empty, no leading/trailing dots); do not over-validate (no FQDN required) unless PRODUCT specifies.
- **Duplicate domain name**: Reject duplicate name with 409 or 400; policy: one domain per name.
- **Static serving**: Serve frontend from backend so one deployment works; path prefix (e.g. /app) to avoid clashing with /api.

---

## Dependencies

- Auth slice: session, current user, /me.
- DATA_MODEL: domains and user_domain_assignments fields.
- AGENTS.md: only super-admin can add domains; domain scope on every query.
