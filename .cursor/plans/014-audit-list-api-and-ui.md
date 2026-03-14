# Plan: Audit list API + minimal audit UI (Phase 6)

## Goal

Implement **GET /api/v1/audit** (or **GET /api/v1/audit-log**): list audit log entries with pagination. Restrict to **super-admin** in v1. Add a minimal **/app/audit** page that fetches and displays the list. Reuse existing `audit_log` table and `write_login_event` shape; no schema change.

## Why this slice

- Phase 6 calls for "audit browsing/search UI". The repo already has `audit_log` and login events; there is no list endpoint or UI. Smallest slice: one read API + one read-only page.
- PRODUCT.md: "Provide a clear audit trail for security-sensitive actions." SECURITY_AND_AUDIT: invalid/insufficient API key usage must be logged and audited (future); for now we only have login events to display.

## Scope (in)

- **Audit service** (new or under auth): `list_audit_events(config, current_user, limit, offset)` → list of event dicts (id, timestamp, actor_type, actor_user_id, action_type, outcome, source_ip, user_agent, summary). Enforce: only super-admin may list; others get no data (403).
- **Handler**: `GET /api/v1/audit` (or `GET /api/v1/audit-log`). Query params: `limit` (default 50, max 100), `offset` (default 0). Session required. Return `{ "events": [...], "total"?: N }` or paginated list only. 403 for non–super-admin.
- **Docs**: Document GET .../audit in API_V1.md (super-admin only; query params; response shape).
- **Frontend**: Add route `/app/audit`; page fetches GET /api/v1/audit and renders a simple table (timestamp, action_type, outcome, summary, actor_user_id if present). No filters in this slice beyond limit/offset.
- **Tests**: Integration test: super-admin GET audit → 200 and list; non–super-admin GET audit → 403; unauthenticated → 401.

## Scope (out)

- Search/filter by action_type, date range, actor (future slice).
- API key–triggered audit events (ingest auth); only login events exist in DB for now.
- Schema changes; read-only from existing table.

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/audit_service.py` (new) or `backend/auth/audit.py` | Add `list_audit_events(config, current_user, limit, offset)` → (events_list, total_count or None). If current_user role ≠ super-admin, return ([], 0) or signal 403 at handler. Query `audit_log` ORDER BY timestamp DESC LIMIT/OFFSET; return list of dicts with id, timestamp, actor_type, actor_user_id, action_type, outcome, source_ip, user_agent, summary. |
| `backend/api/v1/handlers/audit.py` (new) or extend `auth` | Add router for `GET /audit` (prefix under /api/v1). Parse limit/offset; call list_audit_events; if forbidden return 403; else 200 with `{ "events": [...] }`. |
| `backend/api/v1/__init__.py` | Include the new audit router. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document GET /api/v1/audit: super-admin only; query params limit, offset; response body with events array and field descriptions. |

### Frontend

| Path | Action |
|------|--------|
| `frontend/` (router + audit page) | Add route `/app/audit`; add a minimal page that GETs /api/v1/audit and displays events in a table (timestamp, action_type, outcome, summary). Follow existing SPA patterns (e.g. how /app/domains or /app/dashboards is done). |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_audit.py` (new) or add to existing | Test: login as super-admin, GET /api/v1/audit → 200, body has events array. Login as manager/viewer (or admin without super-admin), GET /api/v1/audit → 403. No session GET /api/v1/audit → 401. |

---

## Acceptance criteria

1. **GET /api/v1/audit** with valid session and super-admin role: 200, body includes `events` (array of objects with at least timestamp, action_type, outcome, summary; actor_user_id when present). Support `limit` and `offset` query params.
2. **GET /api/v1/audit** with valid session and non–super-admin role: 403.
3. **GET /api/v1/audit** without session: 401.
4. **/app/audit** page loads for authenticated super-admin and shows audit events in a table; non–super-admin can be redirected or see an empty/forbidden state per existing app pattern.

---

## Tests and validation

1. **Integration**: Super-admin GET audit → 200 and events array; non–super-admin GET audit → 403; unauthenticated GET → 401.
2. **Run**: `pytest tests/` and manual or smoke check for /app/audit when logged in as super-admin.

---

## Route naming

Use **GET /api/v1/audit** (singular) to align with "audit" as the resource; alternative is GET /api/v1/audit-log. Prefer `/audit` for brevity and match frontend route `/app/audit`.
