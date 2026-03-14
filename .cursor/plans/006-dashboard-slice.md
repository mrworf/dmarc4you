# Plan: Dashboard slice (Phase 4 — create dashboard, assign owner, render first widget from live query)

## Goal

Implement the Dashboard vertical slice: schema for dashboards and dashboard domain scope; POST create dashboard (current user becomes owner), GET list (dashboards owned by user), GET by id (dashboard + domain scope); access rule that viewer must have access to **all** dashboard domains; minimal UI to list dashboards, create one (name + domain selection), and open a dashboard view that renders one “widget” by calling existing GET /reports/aggregate with the dashboard’s domains (live query). No sharing table or widget table in this slice; no YAML import/export.

## Why this slice

- Bootstrap through Search are done; we have domains and aggregate report search.
- Dashboard slice is next in `docs/IMPLEMENTATION_PLAN.md`; enables “interactive dashboards” and sets up ownership/scope for later sharing and widgets.
- Delivers: dashboard CRUD (create, list, get), domain scope, owner assignment, and “first widget” = aggregate report list via existing search API.

## Scope (in)

- **Schema**: `dashboards` (id, name, description, owner_user_id, created_by_user_id, created_at, updated_at, is_dormant, dormant_reason). `dashboard_domain_scope` (dashboard_id, domain_id). No dashboard_user_access (sharing) in this slice; no widgets table (widget = client-side call to /reports/aggregate).
- **Policy**: Creator becomes owner. User may create dashboard only with domain_ids they are allowed to see. User may view dashboard only if they have access to **all** domains in the dashboard’s scope (same as AGENTS.md: “dashboard access always requires access to all dashboard domains”).
- **API**:
  - **POST /api/v1/dashboards**: body `{ name, description?, domain_ids[] }`. Validate domain_ids ⊆ user’s allowed domains; create dashboard, set owner_user_id = created_by_user_id = current user; insert dashboard_domain_scope. Return created dashboard + domain_ids.
  - **GET /api/v1/dashboards**: list dashboards where owner_user_id = current user. Return list with id, name, description, owner_user_id, domain_ids (or count).
  - **GET /api/v1/dashboards/{id}**: return dashboard + domain_ids (and optionally domain names for client). 404 if not found. 403 if current user does not have access to all dashboard domains (so they cannot view or run widget query).
- **First widget**: No new backend endpoint. Client that opens a dashboard calls GET /reports/aggregate?domains=... with the dashboard’s domain list and renders the result (e.g. table or list). That is “render first widget from live query.”
- **Frontend**: Minimal: dashboards list page (list from GET /dashboards, link to create form and to dashboard view); create form (name, domain multi-select from GET /domains); dashboard view page (GET /dashboards/{id}, then GET /reports/aggregate with those domains, render items). Reuse existing auth and layout.

## Scope (out)

- dashboard_user_access (sharing); PUT/DELETE dashboard (can be added in same or next slice).
- Widget table or GET /dashboards/{id}/widgets/... endpoint.
- YAML import/export, validate-update, share endpoints.
- Dormant behavior (is_dormant set but not enforced in this slice).

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/storage/sqlite/migrations/006_dashboards.sql` | Tables: dashboards, dashboard_domain_scope. |
| `backend/policies/dashboard_policy.py` | can_view_dashboard(current_user, dashboard_domain_ids, user_allowed_domain_ids) → bool (dashboard domains ⊆ user allowed). |
| `backend/services/dashboard_service.py` | create_dashboard(config, name, description, domain_ids, owner_user_id), list_dashboards(config, current_user_id), get_dashboard(config, dashboard_id, current_user) → dashboard + domain_ids or None (403/404). |
| `backend/api/v1/handlers/dashboards.py` | POST /dashboards, GET /dashboards, GET /dashboards/{id}. |
| `frontend/js/app.js` (extend) or new view | Dashboards list: GET /dashboards, render; create form: name + domain multi-select (from GET /domains), POST /dashboards; dashboard view: GET /dashboards/{id}, then GET /reports/aggregate?domains=... with dashboard domains, render items as first “widget”. |
| `frontend/index.html` (extend) | Add section or route for /app/dashboards and /app/dashboards/:id (hash-based or simple show/hide). |
| `tests/integration/test_dashboards.py` | POST create dashboard (201, owner set); GET list (only owned); GET by id (200 with domain_ids); GET by id as user without access to one of dashboard’s domains (403); create with domain_ids user cannot access (400/403). |

### Edit

| Path | Change |
|------|--------|
| `backend/api/v1/__init__.py` | Include dashboards router. |
| `docs/IMPLEMENTATION_PLAN.md` | Mark Dashboard slice done. |
| `docs/API_V1.md` | Document POST/GET /dashboards and GET /dashboards/{id} (request/response, access rule). |

---

## Acceptance criteria

1. **POST /api/v1/dashboards** with valid session and body `{ name, domain_ids }`: 201, dashboard created, owner_user_id = current user, dashboard_domain_scope populated. domain_ids must be subset of user’s allowed domains.
2. **GET /api/v1/dashboards**: 200, list of dashboards owned by current user (id, name, description, owner_user_id, domain_ids).
3. **GET /api/v1/dashboards/{id}**: 200 with dashboard + domain_ids when current user has access to all dashboard domains; 403 when user lacks access to any dashboard domain; 404 when dashboard does not exist.
4. **UI**: User can open a “dashboards” view, create a dashboard (name + domains), open a dashboard and see aggregate report list (first widget) for that dashboard’s domains via live call to /reports/aggregate.

---

## Tests and validation

1. **Integration**: Create dashboard as super-admin with domain_ids; GET list includes it; GET by id returns domain_ids. Create dashboard with domain user doesn’t have → 400/403. As another user (no access to dashboard’s domain), GET /dashboards/{id} → 403.
2. **Manual**: Log in, create dashboard, open it, see aggregate list.
3. **Run**: `pytest tests/` passes.

---

## Risks and mitigations

- **Empty domain_ids**: Reject POST with empty domain_ids (dashboard must have at least one domain for widget to be meaningful, or allow empty and widget returns no data).
- **Domain id vs name**: Store domain_id in dashboard_domain_scope; GET dashboard can return domain_ids and optionally resolve to names for client (search API uses domain names; so return names for widget query). Resolve domain_id → name in get_dashboard response.

---

## Dependencies

- Domain slice: domains, user_domain_assignments; list_domains for allowed domains.
- Search slice: GET /reports/aggregate for widget data.
- DATA_MODEL: dashboards, dashboard_domain_scope.
- AGENTS.md: dashboard access requires access to all dashboard domains.
