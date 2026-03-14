---
name: Search UI Slice
overview: Add a /app/search page to the SPA that provides an interactive interface for the existing POST /api/v1/search endpoint, enabling users to filter aggregate records by domain, time range, and include/exclude conditions.
todos:
  - id: search-html
    content: Add search-view section to index.html with form fields and results area
    status: completed
  - id: search-js
    content: Add showSearch, loadSearchPage, form handler, and results rendering to app.js
    status: completed
  - id: url-state
    content: Implement URL hash encoding/decoding for bookmarkable search state
    status: completed
  - id: nav-link
    content: Add Search link to navigation on domains view
    status: completed
  - id: docs-update
    content: Update FRONTEND_AND_DASHBOARDS.md to mark /app/search implemented
    status: completed
---

# Search UI Slice

## Goal

Create the `/app/search` route specified in [docs/FRONTEND_AND_DASHBOARDS.md](docs/FRONTEND_AND_DASHBOARDS.md) that provides a user interface for the existing `POST /api/v1/search` endpoint. This enables users to interactively search aggregate report records with domain, time, and field-level filters.

## Why this slice

- Phase 3 calls for "structured search API" which exists (`POST /api/v1/search`)
- The frontend routes doc lists `/app/search` but it doesn't exist
- The backend already supports include/exclude filtering on `spf_result`, `dkim_result`, `disposition`, `source_ip`
- Smallest slice: one new view wired to existing API

## Scope (in)

- **Frontend**: Add `search-view` section in [frontend/index.html](frontend/index.html)
  - Domain multi-select (from user's allowed domains)
  - Time range inputs (from/to date pickers or text inputs)
  - Include/exclude filter fields for `spf_result`, `dkim_result`, `disposition`
  - Results table with pagination
  - Link from nav on domains view

- **Frontend JS**: Add to [frontend/js/app.js](frontend/js/app.js)
  - `showSearch()` view toggle
  - `loadSearchPage()` to fetch allowed domains and render form
  - Form submit handler calling `POST /api/v1/search`
  - Results rendering with pagination controls

- **URL state**: Encode search params in URL hash for bookmarkability (e.g. `#search?domains=example.com&from=...`)

## Scope (out)

- FTS/free-text `query` param (future slice)
- Dashboard integration (separate slice for drill-down from dashboard to search)
- Export/download of search results

## Files to create or edit

- **Edit**: [frontend/index.html](frontend/index.html) - Add `search-view` div with form and results area, add nav link
- **Edit**: [frontend/js/app.js](frontend/js/app.js) - Add search view logic, form handling, API call, results rendering
- **Edit**: [docs/FRONTEND_AND_DASHBOARDS.md](docs/FRONTEND_AND_DASHBOARDS.md) - Mark `/app/search` as implemented

## Acceptance criteria

1. `/app/search` route renders a search form with:
   - Multi-select for domains (populated from user's allowed domains via GET /domains)
   - From/to date inputs
   - Dropdowns or checkboxes for include filters (spf_result, dkim_result, disposition values)
   - Dropdowns or checkboxes for exclude filters
2. Form submit calls `POST /api/v1/search` with selected filters
3. Results table shows: source_ip, count, disposition, dkim_result, spf_result, domain, org_name
4. Pagination controls (page, page_size) work correctly
5. URL hash reflects current search state for bookmarkability
6. Nav link "Search" appears on domains view (for all authenticated users)
7. Domain scoping enforced (API already handles this; UI only shows allowed domains)

## Tests and validation

1. **Manual smoke test**: Login, navigate to /app/search, select domain, set time range, apply filters, verify results
2. **URL state test**: Perform search, copy URL, open in new tab, verify same results load
3. **Domain scoping test**: Login as non-super-admin with limited domains, verify only those domains appear in dropdown
4. **Empty state**: Search with filters that match nothing, verify friendly "No results" message

## UI layout sketch

```
Search

[Domains: [ ] example.com  [ ] other.com]

[From: ________] [To: ________]

Include:
  SPF result: [All | pass | fail | ...]
  DKIM result: [All | pass | fail | ...]
  Disposition: [All | none | quarantine | reject]

Exclude:
  SPF result: [None | pass | fail | ...]
  ...

[Search]

Results (N total):
| Source IP | Count | Disposition | DKIM | SPF | Domain | Org |
|-----------|-------|-------------|------|-----|--------|-----|
| ...       | ...   | ...         | ...  | ... | ...    | ... |

[Prev] Page 1 of X [Next]
```
