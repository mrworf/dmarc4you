---
name: Audit Search Filters
overview: "Add search/filter capabilities to the audit log: action type, date range, and actor filtering in both the API and UI, completing the Phase 6 \"audit browsing/search UI\" deliverable."
todos:
  - id: audit-service
    content: Extend list_audit_events with action_type, from_date, to_date, actor_user_id filters
    status: completed
  - id: audit-api
    content: Add query parameters to GET /api/v1/audit endpoint
    status: completed
  - id: audit-ui-form
    content: Add filter form to audit-view in HTML with action type, dates, actor inputs
    status: completed
  - id: audit-ui-js
    content: Implement loadAuditPage with filters, URL hash state, and pagination
    status: completed
  - id: audit-tests
    content: Add integration tests for filtered audit queries
    status: completed
---

# Audit Search and Filter UI

## Goal

Complete the Phase 6 "audit browsing/search UI" deliverable by adding filtering capabilities to the audit log. Currently the audit view only displays a paginated table with no filtering.

## Key Files

**Backend:**

- [`backend/services/audit_service.py`](backend/services/audit_service.py) - extend `list_audit_events` with optional filters
- [`backend/api/v1/handlers/audit.py`](backend/api/v1/handlers/audit.py) - add query params for filtering

**Frontend:**

- [`frontend/index.html`](frontend/index.html) - add filter form to audit-view section
- [`frontend/js/app.js`](frontend/js/app.js) - implement filter form handling and URL state

**Tests:**

- [`tests/integration/test_audit.py`](tests/integration/test_audit.py) - add tests for filtered queries

## Implementation

### 1. Extend audit_service.list_audit_events

Add optional parameters:

- `action_type: str | None` - filter by action type (e.g., "login", "domain.archive")
- `from_date: str | None` - ISO date string for start of range
- `to_date: str | None` - ISO date string for end of range  
- `actor_user_id: str | None` - filter by actor

Build SQL WHERE clauses conditionally based on provided filters.

### 2. Update GET /api/v1/audit endpoint

Add query parameters:

```
GET /api/v1/audit?action_type=login&amp;from=2026-03-01&amp;to=2026-03-12&amp;actor=usr_xxx&amp;limit=50&amp;offset=0
```

### 3. Add filter form to audit UI

Add to `audit-view` section:

- Action type dropdown (dynamically populated or static list of common types)
- Date range inputs (from/to)
- Actor ID text input
- URL hash state for bookmarkable filtered views (similar to search view)
- Pagination controls

### 4. Tests

- Test filtering by action_type returns only matching events
- Test date range filtering
- Test actor_user_id filtering
- Test combined filters
- Test empty results when no matches

## Acceptance Criteria

- Super-admin can filter audit log by action type, date range, and actor
- Filtered results are paginated
- Filter state is preserved in URL hash for bookmarking
- Non-super-admin still receives 403
- Existing tests continue to pass