# Plan: Dormant dashboard — hide from list when scope has archived domain (Phase 5)

## Goal

Implement **dormant dashboard** behavior for non–super-admins: when a dashboard’s scope includes any **archived** domain, that dashboard must not appear in **list_dashboards** for non–super-admin users. Super-admin continues to see all owned dashboards. **GET** dashboard already returns 403 for non–super-admin when the dashboard has an archived domain (because `list_domains` excludes archived, so `can_view_dashboard` fails); no change to get_dashboard in this slice. Backend only; minimal change.

## Why this slice

- Phase 5 calls for “dormant dashboard behavior”. DOMAIN_LIFECYCLE: “dashboards referencing the domain become dormant/inaccessible to non-super-admin users”. Inaccessibility is already enforced (403 on GET). This slice adds “dormant” by hiding such dashboards from the list so non–super-admins don’t see dashboards they cannot open.
- Small scope: one behavioral change in `list_dashboards` (filter by archived domains when caller is not super-admin), plus tests and a short doc note.

## Scope (in)

- **Dashboard service**: `list_dashboards(config, current_user)` — today it takes `current_user_id` and returns all dashboards where `owner_user_id = current_user_id`. Change to accept `current_user` (dict with `id`, `role`). When `role != 'super-admin'`, exclude dashboards that have at least one `domain_id` in `dashboard_domain_scope` for which the domain has `status = 'archived'` (join with `domains` or subquery). Super-admin: unchanged (all owned dashboards).
- **Handler**: `list_dashboards` currently passes `current_user["id"]`; change to pass `current_user` and update the service signature.
- **Docs**: Short note in `docs/API_V1.md` or `docs/DOMAIN_LIFECYCLE.md` / `docs/FRONTEND_AND_DASHBOARDS.md`: list returns only non-dormant dashboards for non–super-admin (dashboards whose scope includes an archived domain are excluded).
- **Tests**: Integration test: create dashboard with domain A, archive A, list as owner (non–super-admin): dashboard not in list. List as super-admin: dashboard still in list. Optional: owner is super-admin, archive one domain, list as super-admin still sees it.

## Scope (out)

- Setting or persisting `is_dormant` on the dashboard row; no schema change. Computing “dormant” only at list time.
- UI changes or “dormant” label in the UI.
- Dashboard sharing (dashboard_user_access); list still “owned by current user” only.
- Changes to get_dashboard (already 403 for non–super-admin when scope has archived domain).

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/dashboard_service.py` | Change `list_dashboards(config, current_user_id)` to `list_dashboards(config, current_user: dict)`. When `current_user["role"] != "super-admin"`, exclude dashboards that have any scope domain with `status = 'archived'` (e.g. subquery or join with `domains`). |
| `backend/api/v1/handlers/dashboards.py` | Pass `current_user` into `list_dashboards` instead of only `current_user["id"]`. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` (or `docs/FRONTEND_AND_DASHBOARDS.md`) | State that GET /dashboards for non–super-admin excludes dashboards whose scope contains an archived domain (dormant dashboards). |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_dashboards.py` | Add test: create dashboard (owner = non–super-admin) with one domain; archive that domain; list dashboards as that owner → dashboard not in list. Add test: same setup, list as super-admin → dashboard still in list (super-admin sees all owned). |

---

## Acceptance criteria

1. **GET /api/v1/dashboards** as **non–super-admin** (e.g. admin/manager/viewer): response does **not** include any dashboard whose `dashboard_domain_scope` contains a domain with `status = 'archived'`. Other owned dashboards (all scope domains active) still appear.
2. **GET /api/v1/dashboards** as **super-admin**: unchanged; all dashboards owned by the user are returned, including those with archived domains in scope.
3. **GET /api/v1/dashboards/{id}** for a dashboard with an archived domain, as non–super-admin: still 403 (existing behavior; no change in this slice).

---

## Tests and validation

1. **Integration**: Create user (admin); create domain D1; assign D1 to user; create dashboard with scope [D1]; archive D1; list dashboards as that user → list does not include the dashboard. As super-admin, list dashboards → dashboard is in list (super-admin owns it and sees it despite dormant scope).
2. **Run**: `pytest tests/` passes.

---

## Implementation note

Query for non–super-admin: “dashboards where owner_user_id = ? and not exists (select 1 from dashboard_domain_scope s join domains d on d.id = s.domain_id where s.dashboard_id = dashboards.id and d.status = 'archived')”. Or: fetch owned dashboard ids, then for each get scope domain ids, filter domains by status, exclude dashboard if any scope domain is archived. Prefer a single SQL query for clarity and performance.
