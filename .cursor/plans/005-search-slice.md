# Plan: Search slice (Phase 3 — list aggregate results with domain/time filters and domain scoping)

## Goal

Implement the Search vertical slice: list normalized aggregate report records with domain scoping (user sees only domains they are allowed to see), optional domain filter, optional time range filter (from/to), pagination, and sort. No FTS or free-text query in this slice; no include/exclude filters on SPF/DKIM/disposition (aggregate_reports has only minimal fields).

## Why this slice

- Bootstrap, Auth, Domain, and Ingest are done; aggregate_reports is populated by the ingest runner.
- Search slice is next in `docs/IMPLEMENTATION_PLAN.md`; required before Dashboards (widgets query report data) and for any UI that shows “report list” or “results”.
- Delivers: GET /api/v1/reports/aggregate with domain scoping, time filter, pagination, and sort.

## Scope (in)

- **Domain scoping**: Same as list_domains — super-admin sees all active domains; others see only domains in user_domain_assignments. Results are restricted to aggregate_reports rows whose `domain` is in the user’s allowed domain set (by name).
- **Time filter**: Optional `from` and `to` (Unix timestamps or ISO 8601). Filter rows where (date_begin, date_end) overlaps [from, to]: e.g. `date_begin <= to AND date_end >= from`.
- **Domain filter**: Optional `domains` query param (list of domain names). Intersect with allowed domains; filter results to those domains only.
- **Pagination**: Optional `page` and `page_size` (e.g. default page_size=50, max cap). Return total count or “has_more” so client can paginate.
- **Sort**: Optional sort (e.g. `date_begin` desc default). Single field sort is enough.
- **Response**: List of aggregate report records: id, report_id, org_name, domain, date_begin, date_end, created_at (and optionally job_item_id). Plus pagination metadata (total, page, page_size or next_page).
- **Index**: Add index on aggregate_reports(domain, date_begin) or (date_begin, domain) for efficient filtered queries.

## Scope (out)

- FTS / free-text search (Phase 3 “FTS-backed free-text search” can be a follow-up).
- POST /api/v1/search with full request body (can add later; this slice uses GET with query params).
- Include/exclude filters on SPF/DKIM/disposition (not in current schema).
- Forensic reports (GET /api/v1/reports/forensic).
- Dashboard or UI; this slice is API-only.

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/storage/sqlite/migrations/005_search_index.sql` | CREATE INDEX on aggregate_reports(domain, date_begin) and optionally (date_begin DESC). |
| `backend/services/search_service.py` | list_aggregate_reports(config, current_user, domains=None, from_ts=None, to_ts=None, page=1, page_size=50, sort_by='date_begin', sort_dir='desc') → { items, total, page, page_size }. Domain scoping: resolve allowed domain names for user; filter aggregate_reports by domain IN allowed and optional domains param; apply from/to overlap; count and slice for pagination; sort. |
| `backend/api/v1/handlers/reports.py` (extend) | GET /reports/aggregate: query params domains (comma-separated or repeated), from, to, page, page_size, sort_by, sort_dir. Call search_service; return JSON. |
| `tests/integration/test_search.py` | As super-admin, create domain and ingest one report; GET /reports/aggregate → 200, list contains record; filter by domain → same or subset; filter by time (from/to) → correct subset; as non-super-admin with no assignments → empty list; as non-super-admin with assignment → only that domain’s results. |

### Edit

| Path | Change |
|------|--------|
| `backend/api/v1/handlers/reports.py` | Add GET /reports/aggregate route (reports_router). |
| `docs/IMPLEMENTATION_PLAN.md` | Mark Search slice done. |
| `docs/API_V1.md` | Document GET /api/v1/reports/aggregate (params, response shape, scoping). |

---

## Acceptance criteria

1. **GET /api/v1/reports/aggregate** with valid session: 200, body has `items` (list of aggregate records) and pagination (e.g. `total`, `page`, `page_size`).
2. **Domain scoping**: Super-admin sees all aggregate_reports rows (subject to optional domains/time filters). Non-super-admin sees only rows whose domain is in their user_domain_assignments.
3. **Time filter**: Params `from` and `to` (Unix or ISO) restrict to rows where (date_begin, date_end) overlaps [from, to].
4. **Domain filter**: Param `domains` (e.g. comma-separated) restricts to those domains; still intersected with allowed domains.
5. **Pagination**: `page` and `page_size` return the correct slice; `total` allows client to compute pages.
6. **Sort**: Default or param sort_by=date_begin, sort_dir=desc returns newest first.

---

## Tests and validation

1. **Integration**: Ingest one aggregate report for domain example.com; as super-admin GET /reports/aggregate → items include it; GET with domains=example.com → same; GET with from/to spanning date_begin/date_end → same; from/to outside range → empty. Create user with assignment to example.com only; as that user GET /reports/aggregate → only example.com row; user with no assignments → empty items.
2. **Run**: `pytest tests/` passes.

---

## Risks and mitigations

- **Time param format**: Accept both Unix (integer) and ISO 8601; convert ISO to Unix for comparison with date_begin/date_end.
- **Large result sets**: Cap page_size (e.g. max 500) to avoid heavy queries.

---

## Dependencies

- Ingest slice: aggregate_reports table with domain, date_begin, date_end.
- Domain scoping: same as domain_service.list_domains (allowed domain names for current user).
