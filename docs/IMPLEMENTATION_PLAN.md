# Implementation Plan

Implement this project as thin, testable vertical slices.

## Phase 1 — Foundations

Goal: establish the skeleton without overcommitting to implementation details.

Deliver:

- repo structure
- config loader and YAML schema
- logging bootstrap
- SQLite storage interfaces + migrations
- bootstrap `admin` super-admin creation
- local auth/session scaffolding
- basic role/domain model
- audit scaffold
- versioned API skeleton under `/api/v1`

## Phase 2 — Background jobs + ingest core

Deliver:

- persisted ingest jobs and job items
- restart-safe in-process job runner
- JSON envelope ingest API
- XML + compressed report support
- aggregate and forensic parsing
- dedupe and per-report outcomes
- API key auth for ingest

## Phase 3 — Query/search base

Deliver:

- normalized report read models
- structured search API
- SQLite indexes
- FTS-backed free-text search over curated fields
- ingest job detail UI/API

## Phase 4 — Dashboards and SPA shell

Deliver:

- frontend shell and router
- auth flow and app layout
- dashboard CRUD
- ownership/sharing model
- widget query execution
- URL-state drill-down/filtering

## Phase 5 — Domain lifecycle and archival

Deliver:

- archive storage interface + filesystem adapter
- archive/restore/delete domain flows
- dormant dashboard behavior
- retention scheduler
- restore of user assignments and API key bindings

## Phase 6 — Admin polish and portability

Deliver:

- user/domain/admin UI
- API key management UI
- dashboard YAML import/export with domain remapping
- audit browsing/search UI
- break-glass local admin CLI

## Suggested first vertical slices

1. **Bootstrap slice** ✓ (done)
   - config, logging, DB init, migrations, bootstrap admin, health endpoint
2. **Auth slice** ✓ (done)
   - login/logout/me, session storage, username validation, audit login events
3. **Domain slice** ✓ (done)
   - create/list domains, role/domain visibility, basic admin UI page
4. **Ingest slice** ✓ (done)
   - enqueue ingest job, worker, parse a simple aggregate XML, persist normalized result
5. **Search slice** ✓ (done)
   - list aggregate results with domain/time filters and domain scoping
6. **Dashboard slice** ✓ (done)
   - create dashboard, assign owner, render first widget from live query
7. **Ingest job detail UI** ✓ (done)
   - GET /api/v1/ingest-jobs list, ingest jobs view + job detail view in UI
8. **Domain archive and restore** ✓ (done)
   - POST .../archive, POST .../restore (super-admin only); list_domains: super-admin sees all, others only active
9. **Domain delete when archived** ✓ (done)
   - DELETE .../domains/{id} (super-admin only, domain must be archived); purges domain and related data
10. **Dormant dashboard list** ✓ (done)
   - list_dashboards for non–super-admin excludes dashboards whose scope contains an archived domain
11. **Break-glass CLI** ✓ (done)
   - python -m cli reset-admin-password: resets admin password, prints new password; config via file or env
12. **Dashboard YAML export** ✓ (done)
   - GET /dashboards/{id}/export: portable YAML (name, description, domains); same auth as get dashboard
18. **Dashboard export UI** ✓ (done)
   - Dashboard detail: Export link; GET …/export → download YAML file
19. **Configure retention on archive** ✓ (done)
   - POST …/archive optional body `retention_days`; persist retention_delete_at; list_domains returns retention fields
20. **Retention scheduler** ✓ (done)
   - Background run_retention_purge in job loop; purge archived domains past retention_delete_at (not paused)
21. **Retention pause/unpause API** ✓ (done)
   - POST …/retention/pause (optional reason), POST …/retention/unpause; super-admin only; remaining time stored on pause, restored on unpause
22. **User management API** ✓ (done)
   - GET/POST/PUT /users, reset-password, domain assign/remove; admin sees domain-scoped users; RBAC enforced
23. **User management UI** ✓ (done)
   - Users link (admin+ only); list, create, edit, reset-password, domain assign forms in SPA
24. **Dashboard edit and delete** ✓ (done)
   - PUT /dashboards/{id}: update name, description, domain_ids; owner/admin/super-admin only
   - DELETE /dashboards/{id}: remove dashboard; owner/admin/super-admin only; viewer forbidden
   - Edit/Delete links in dashboard detail UI (hidden for viewer role)
25. **Dashboard ownership transfer** ✓ (done)
   - POST /dashboards/{id}/owner: transfer ownership to another user; admin/super-admin only
   - New owner cannot be viewer; must have access to all dashboard domains
26. **Dashboard sharing** ✓ (done)
   - POST /dashboards/{id}/share: add viewer/manager assignment; owner/manager/admin/super-admin
   - DELETE /dashboards/{id}/share/{user_id}: remove assignment
   - POST /dashboards/{id}/validate-update: dry-run validation before scope changes
   - Target must have access to all dashboard domains; viewer cannot be granted manager
27. **Search UI** ✓ (done)
   - /app/search route with domain/time/include/exclude filters calling POST /api/v1/search
   - URL hash state for bookmarkable searches; pagination controls; results table
28. **Forensic report support** ✓ (done)
   - forensic_reports table migration; forensic_parser.py for AFRF XML format
   - runner.py auto-detects aggregate vs forensic, dispatches to correct parser/persistence
   - GET /api/v1/reports/forensic endpoint with domain scoping and pagination
   - dedupe for forensic reports; integration tests for ingest and list
29. **Forensic reports UI** ✓ (done)
   - Report type selector (Aggregate/Forensic) in Search view
   - Forensic search calls GET /api/v1/reports/forensic with domain/time/page params
   - Forensic results table with domain, source IP, header from, SPF/DKIM/DMARC results, failure type, arrival time
   - URL hash state includes report_type for bookmarkable forensic searches
30. **FTS free-text search** ✓ (done)
   - FTS5 virtual table `aggregate_records_fts` indexing source_ip, header_from, envelope_from, envelope_to, org_name
   - Triggers to keep FTS in sync on INSERT/DELETE
   - `query` parameter in POST /api/v1/search for free-text search with prefix matching
   - Search UI text input for query; URL hash state includes query for bookmarks
   - Unit tests for FTS query escaping and search_records with query parameter
31. **Audit search filters** ✓ (done)
   - GET /api/v1/audit query params: action_type, from, to, actor for filtering
   - audit_service.list_audit_events extended with optional filter parameters
   - Audit UI filter form with action type dropdown, date range inputs, actor ID field
   - URL hash state for bookmarkable filtered audit views; pagination controls
   - Integration tests for filtered audit queries
32. **Upload UI** ✓ (done)
   - /app/upload route with textarea paste and file upload for XML or gzip-compressed XML
   - Client-side base64 encoding; calls POST /api/v1/reports/ingest with session auth
   - Gzip detection by file extension or magic bytes; job_id link to ingest job detail on success
33. **Dashboard filter UI** ✓ (done)
   - Dashboard detail view: from/to date pickers, include/exclude filters for SPF/DKIM/disposition
   - URL hash state (#dashboard/id?from=...&include_spf=fail&page=2) for bookmarkable filters
   - Pagination controls for filtered dashboard results
   - Uses existing POST /api/v1/search endpoint with dashboard domains
34. **Email/MIME ingest support** ✓ (done)
   - backend/ingest/mime_parser.py: is_mime_message() detection and extract_attachments()
   - runner.py integrates MIME detection before XML parsing; extracts and processes attachments
   - Supports MIME emails with XML attachments, gzip-compressed attachments, and multiple attachments
   - Unit tests for MIME parser; integration tests for email-based ingest
35. **Dashboard sharing UI** ✓ (done)
   - GET /api/v1/dashboards/{id}/shares: list users with access (user_id, username, access_level, granted_at)
   - Dashboard detail page shows "Sharing" section with current shares table
   - Share form to add viewers/managers; unshare button to remove access
   - Only visible to owner/manager/admin/super-admin (not viewer role)
36. **User deletion with ownership fallback** ✓ (done)
   - DELETE /api/v1/users/{user_id}: soft-delete user (sets disabled_at)
   - Deterministic dashboard ownership transfer: assigned manager → admin → super-admin
   - Admin cannot delete another admin or super-admin; no self-deletion
   - UI delete button in user list (hidden for current user)
   - Audit events for user_deleted and dashboard_ownership_transferred
37. **Set/update retention on archived domains** ✓ (done)
   - POST /api/v1/domains/{domain_id}/retention: set or update retention_days on archived domain
   - Super-admin only; recalculates retention_delete_at (or retention_remaining_seconds if paused)
   - UI "Set retention" / "Update retention" button for archived domains
38. **Domain delete cleanup fix** ✓ (done)
   - _purge_domain_data now deletes forensic_reports and api_key_domains for the domain
   - Fixes orphaned data when deleting archived domains or via retention purge
   - Integration tests verify forensic_reports and api_key_domains are cleaned up
39. **CSRF protection** ✓ (done)
   - Double-submit cookie pattern: server sets csrf cookie on login, client sends X-CSRF-Token header
   - CSRF validation dependency on all POST/PUT/DELETE endpoints (except login and Bearer-authed requests)
   - Frontend updated to read csrf cookie and include header in all state-changing requests
   - Integration tests verify enforcement and API key exemption
40. **Raw artifact archival** ✓ (done)
   - backend/archive/ module with ArchiveStorage protocol and FilesystemArchiveStorage implementation
   - Config option archive_storage_path (optional); when set, archival is enabled
   - Runner stores raw payload bytes to {archive_path}/{domain}/{report_id}.raw after successful acceptance
   - GET /api/v1/domains/{id}/stats returns artifact_count when archive is configured
   - Unit tests for FilesystemArchiveStorage; integration tests for archive ingest and stats
41. **Artifact retrieval API** ✓ (done)
   - ArchiveStorage protocol extended with list() and retrieve() methods
   - FilesystemArchiveStorage implements list (sorted artifact IDs) and retrieve (raw bytes)
   - GET /api/v1/domains/{id}/artifacts: list artifact IDs for domain; same auth as stats
   - GET /api/v1/domains/{id}/artifacts/{artifact_id}: download raw artifact bytes
   - Unit tests for list/retrieve; integration tests for both endpoints with auth checks
42. **Aggregate report detail** ✓ (done)
   - GET /api/v1/reports/aggregate/{id}: single aggregate report with all records; domain scoped
   - search_service.get_aggregate_report_detail() returns report + records array
   - UI: clickable "View" link in search/dashboard results opens modal with full record list
   - Integration tests for 200, 403, 404, 401 cases
43. **Forensic report detail** ✓ (done)
   - GET /api/v1/reports/forensic/{id}: single forensic report with all fields; domain scoped
   - search_service.get_forensic_report_detail() returns report dict
   - UI: clickable "View" link in forensic search results opens modal with report metadata
   - Integration tests for 200, 403, 404, 401 cases
44. **Domain DNS monitoring** ✓ (done)
   - Opt-in DMARC/SPF/configured-DKIM monitoring with TTL-aware scheduling and per-domain change history
   - `GET/PUT /api/v1/domains/{id}/monitoring`, `POST /api/v1/domains/{id}/monitoring/check`
   - API key scope `domains:monitor` for programmatic trigger
   - Failure logging is edge-triggered: first failure in a streak only, reset on success
   - Next.js domain detail view shows current state, explanations, failure banner, and history
45. **DNS change timeline** ✓ (done)
   - Dedicated `GET /api/v1/domains/{id}/monitoring/timeline` endpoint with diff-classified history entries
   - Unchanged polls update freshness only; timeline remains change-only
   - Timeline entries are marked improved/degraded/neutral from DMARC/SPF/DKIM diff rules
   - Next.js timeline page shows a scrollable node-based history plus a separate last-polled freshness card

## Working rules for each slice

- keep changes reviewable
- create tests for new policy logic
- add docs when behavior changes
- do not mix large refactors with feature delivery unless required
- use feature flags or stub UI states when a full user flow spans multiple slices
