# Frontend Migration Slices

Implement the Next.js migration as thin, testable slices that preserve FastAPI as the source of truth.

This plan is intentionally focused on the changes discussed for the frontend migration and related scalability work:

- typed API contracts for UI-facing endpoints
- a durable frontend platform in `frontend-next/`
- explicit split-origin deployment/auth configuration
- migration-safe validation and rollout
- preparation for later operational scaling without mixing in a backend rewrite

## Migration principles

- keep the migration **frontend-only**
- preserve `/api/v1` as the primary application API
- keep RBAC, domain scoping, ingest, retention, and archival rules on the backend
- migrate route-by-route while the legacy SPA remains available
- tighten API contracts before relying on them broadly from the new frontend
- prefer additive backend changes over endpoint redesigns unless required

## Phase 1 — Platform foundation

Goal: create the minimum platform needed to migrate screens safely.

Deliver:

- typed response schemas for initial UI-facing endpoints
- standardized API error envelopes
- cookie/CORS/frontend-origin config for split-origin development
- Next.js app shell, auth bootstrap, API client, route guards, and URL-state helpers
- readiness endpoint and migration docs

## Phase 2 — Core app shell migration

Goal: replace the top-level navigation and most-visited read/create flows first.

Deliver:

- login flow in Next.js
- domains list in Next.js
- dashboards list/create in Next.js
- shared layout, nav, status states, and role-aware route visibility

## Phase 3 — Search and dashboard read paths

Goal: migrate the most interactive views with reusable filter/query patterns.

Deliver:

- search route with query-param state
- dashboard detail read-only page
- report detail overlays or dedicated detail routes
- reusable tables, pagination, and filter state serialization

## Phase 4 — Dashboard management workflows

Goal: move the feature set that makes dashboards a real product surface.

Deliver:

- dashboard edit/delete
- sharing and ownership transfer
- dashboard export/import UX
- scope preflight validation and impacted-user messaging

## Phase 5 — Admin and ingest workflows

Goal: move the operational screens used by admins and day-to-day operators.

Deliver:

- ingest jobs list/detail
- upload flow
- users management
- API key management
- audit browsing/filtering

## Phase 6 — Migration hardening and cutover

Goal: make the Next.js frontend production-ready and removable from the legacy SPA path.

Deliver:

- browser-level test harness foundation early enough to protect later slices
- e2e coverage for critical role-based flows
- contract checks for frontend-dependent APIs
- deployment documentation for same-origin and split-origin setups
- reverse-proxy/cutover plan
- legacy SPA removal checklist

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
   - remove or retire legacy SPA mount only after parity is confirmed

## Suggested execution order

1. finish dashboard detail and search read paths
2. finalize the frontend test harness approach and land the harness foundation slice
3. migrate search and immediately extend harness coverage for its URL-state behavior
4. finish dashboard management workflows
5. migrate upload and ingest jobs plus admin routes: users, API keys, audit
6. expand browser/e2e coverage for critical migrated flows, then finish contract hardening
7. finalize deployment docs and cutover

## Validation expectations per slice

- backend:
  - unit or integration coverage for any touched API contract or policy behavior
  - OpenAPI/schema verification for newly typed endpoints
- frontend:
  - route smoke checks for migrated pages
  - manual or automated auth/CSRF verification for any mutation flow
  - URL-state restoration checks for any route with filters/pagination
- rollout:
  - keep legacy SPA functional until the matching Next.js replacement is verified
  - avoid removing old routes/UI in the same slice that introduces a new path unless parity is already proven

## Working rules for each slice

- keep slices reviewable and behavior-focused
- prefer one real migrated workflow per slice over broad scaffolding
- avoid bundling visual redesign, API redesign, and route migration into one change
- update docs when a slice changes deployment, auth, or migration sequencing
- record status in this file as slices are completed so the migration remains decision-complete
