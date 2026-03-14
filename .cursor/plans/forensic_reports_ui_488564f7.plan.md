---
name: Forensic Reports UI
overview: Add a Forensic Reports tab/view to the Search page, allowing users to query and view forensic (ruf) reports using the existing GET /api/v1/reports/forensic endpoint.
todos:
  - id: html-selector
    content: Add report type selector to search form in index.html
    status: completed
  - id: js-state
    content: Update hash state handling for report_type in app.js
    status: completed
  - id: js-visibility
    content: Hide aggregate filters when forensic selected
    status: completed
  - id: js-api
    content: Branch doSearch() to call forensic endpoint when report_type=forensic
    status: completed
  - id: js-render
    content: Render forensic-specific results table with appropriate columns
    status: completed
---

# Forensic Reports UI Slice

## Context

The forensic report backend is complete (slice #28):
- `forensic_reports` table exists with domain, source_ip, arrival_time, org_name, header_from, envelope_from, envelope_to, spf_result, dkim_result, dmarc_result, failure_type
- `GET /api/v1/reports/forensic` endpoint returns paginated, domain-scoped results
- Ingest pipeline auto-detects and stores forensic reports

However, **no UI exists to view forensic reports**. The current Search page only queries aggregate records via `POST /api/v1/search`.

## Approach

Add a "Report type" selector to the Search view. When "Forensic" is selected:
- Call `GET /api/v1/reports/forensic` instead of `POST /api/v1/search`
- Display forensic-specific columns (source_ip, header_from, spf/dkim/dmarc results, failure_type)
- Maintain URL hash state for bookmarkable forensic searches

## Files to Edit

- [frontend/index.html](frontend/index.html) - Add report type selector to search form
- [frontend/js/app.js](frontend/js/app.js) - Handle forensic search flow and results rendering

## Implementation Details

### HTML Changes (search form)

Add a report type selector above the domains fieldset:

```html
<label>Report type
  <select name="report_type" id="search-report-type">
    <option value="aggregate">Aggregate records</option>
    <option value="forensic">Forensic reports</option>
  </select>
</label>
```

### JavaScript Changes

1. **State management**: Add `report_type` to hash state (`getSearchStateFromHash`, `setSearchStateInHash`)

2. **Form visibility**: When forensic is selected, hide aggregate-specific filters (include/exclude SPF/DKIM/disposition selects) since forensic endpoint doesn't support them yet

3. **API call**: In `doSearch()`, branch based on report type:
   - `aggregate`: existing `POST /api/v1/search` call
   - `forensic`: new `GET /api/v1/reports/forensic?domains=...&from=...&to=...&page=...`

4. **Results table**: Render different columns for forensic results:
   - Domain, Source IP, Arrival Time, Header From, SPF, DKIM, DMARC, Failure Type

## Acceptance Criteria

1. Search page has "Report type" selector with Aggregate/Forensic options
2. Selecting "Forensic" hides aggregate-specific include/exclude filters
3. Forensic search calls `GET /api/v1/reports/forensic` with domain/time/page params
4. Results table shows forensic-specific columns
5. URL hash includes `report_type=forensic` for bookmarkable state
6. Domain scoping enforced (only shows forensic reports for user's allowed domains)

## Validation Steps

- Manual: Log in, navigate to Search, select Forensic, run search, verify results display
- Manual: Bookmark forensic search URL, reload, verify state restored
- Manual: As non-super-admin with limited domains, verify only allowed domains' forensic reports appear
