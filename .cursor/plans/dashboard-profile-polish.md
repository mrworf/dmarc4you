# Dashboard and shell polish plan

1. Extend dashboard/search data plumbing
- Add owner summary fields to dashboard list/detail payloads.
- Add current-user profile update endpoint/service path.
- Add country-name filtering and page-size support to aggregate explorer state/search service.

2. Refresh dashboard UI
- Show cleaner overview/list metadata (name, description, linked owner, last updated).
- Add country filter input, flag rendering, and page-size selector in dashboard results.
- Keep grouped and flat result views aligned with the new state.

3. Refresh shared shell UX
- Rename product chrome to DMARCWatch/DWatch.
- Remove the "Operations console" heading and tighten user identity block.
- Make section headers/title bars more compact with side-by-side title/description layout.
- Add profile modal from the user name with editable full name/email and read-only role/username/domains.

4. Verify and document
- Update API docs for dashboard payload and auth profile update endpoint.
- Run the smallest relevant frontend/backend tests or checks for touched areas.
