# Frontend Migration Slices

This file is retained as the migration execution record.

## Status

- the migration is complete
- `frontend-next/` is now the primary and only supported frontend
- the legacy backend-served SPA has been retired

## Migration principles that were followed

- keep the migration frontend-only
- preserve `/api/v1` as the primary application API
- keep RBAC, domain scoping, ingest, retention, and archival rules on the backend
- prefer additive backend changes over endpoint redesigns unless required

## Completed phases

1. Platform foundation
2. Core app shell migration
3. Search and dashboard read paths
4. Dashboard management workflows
5. Admin and ingest workflows
6. Migration hardening and cutover

## Suggested migration slices

1. **Frontend contract/config slice** ✓ (done)
   - typed schemas for `auth`, `domains`, and `health`
   - standardized API error envelopes
   - frontend origin, API URL, CORS, and cookie policy config
   - Next.js shell, auth bootstrap, shared API client, route guards, and URL-state helpers
   - readiness endpoint and migration docs

2. **Domains page slice** ✓ (done)
   - Next.js `/domains` route with live domain listing
   - shared shell integration and React Query data loading
   - preserves existing backend visibility and archival behavior

3. **Dashboards landing slice** ✓ (done)
   - typed dashboard list/create API contract
   - Next.js `/dashboards` route with owned dashboards list
   - create-dashboard form with domain selection and mutation handling

4. **Dashboard detail read slice** ✓ (done)
   - Next.js `/dashboards/[id]` route
   - load dashboard metadata plus live widget/search results
   - preserve backend filtering/query behavior without redesign
   - read-only first: no edit/share in this slice

5. **Dashboard detail URL-state slice** ✓ (done)
   - migrate dashboard filter controls to query params
   - include date range, include/exclude filters, grouping, and pagination
   - preserve bookmarkability currently implemented via hash state

6. **Search route slice** ✓ (done)
   - Next.js `/search` route backed by the existing search/report APIs
   - aggregate/forensic toggle
   - query-param persistence for filters, pagination, and free-text query
   - shared results table primitives reused later by dashboard detail

7. **Report detail slice** ✓ (done)
   - aggregate and forensic detail views in the new frontend
   - modal or dedicated route pattern selected once and reused
   - keep backend domain scoping authoritative

8. **Dashboard edit/delete slice** ✓ (done)
   - dashboard edit form in Next.js
   - delete action with confirmation and refresh behavior
   - preserve owner/admin/super-admin rules

9. **Dashboard sharing slice** ✓ (done)
   - list shares in the new UI
   - add/remove viewer/manager assignments
   - reuse role-aware form and feedback patterns

10. **Dashboard ownership/import-export slice** ✓ (done)
   - ownership transfer UI
   - export action in new frontend
   - import form with domain remapping workflow
   - scope preflight and validation messaging

11. **Upload slice** ✓ (done)
   - Next.js `/upload` route for pasted XML and file upload
   - preserve client-side base64 packaging and CSRF/session behavior
   - link to resulting ingest job detail

12. **Ingest jobs slice** ✓ (done)
   - Next.js ingest jobs list and detail routes
   - owner-scoped job visibility preserved
   - polling or manual refresh pattern standardized

13. **Users admin slice** ✓ (done)
   - users list/create/edit/reset-password
   - domain assignment UX
   - admin/super-admin route guard and action visibility

14. **API keys admin slice** ✓ (done)
   - list/create/edit/delete API keys
   - domain and scope selection UI
   - copy-once secret display pattern handled consistently

15. **Audit slice** ✓ (done)
   - audit log table and filter form in Next.js
   - super-admin-only route
   - query-param persistence for filters and pagination

16. **Frontend test harness foundation slice** ✓ (done)
   - add browser-level test tooling for `frontend-next/`
   - reusable seeded auth/session helpers that preserve FastAPI auth and CSRF behavior
   - smoke tests for login, domains, dashboards landing, dashboard detail, and route guards
   - keep coverage narrow at first, but runnable locally and in CI

17. **Search route slice coverage slice** ✓ (done)
   - extend the frontend harness for the migrated `/search` route
   - verify query-param restoration, pagination, and aggregate/forensic mode switching
   - reuse the same browser-level helpers and fixtures as the harness foundation

18. **Contract verification slice** ✓ (done)
   - add schema/contract checks for all frontend-dependent endpoints
   - focus on `auth`, `domains`, `dashboards`, `search`, `users`, `apikeys`, `audit`, `upload`
   - catch backend drift before later route migrations

19. **Frontend critical flows expansion slice** ✓ (done)
   - expand browser-level coverage for migrated dashboard management, upload, and admin routes
   - cover at least the critical role-based happy paths before cutover
   - add URL-state restoration checks wherever migrated filters/pagination exist

20. **Deployment ergonomics slice** ✓ (done)
   - document local split-origin workflow clearly
   - document recommended same-origin production reverse proxy
   - verify cookie/CSRF/CORS settings for both modes

21. **Observability slice** ✓ (done)
   - add correlation-friendly request logging around frontend/API interactions
   - expose the minimum health/readiness detail needed for separate frontend/backend deployment
   - document operational expectations for web + worker separation later

22. **Legacy SPA cutover slice** ✓ (done)
   - verify all required routes exist in `frontend-next/`
   - verify critical e2e matrix across roles using the frontend harness
   - switch primary user-facing frontend to Next.js
   - retire the legacy SPA mount after parity was confirmed

## Final outcome

- the web product now runs on Next.js
- FastAPI is API-only in the supported deployment model
- seeded browser coverage and route-cutover checks remain part of the repository for regression protection
