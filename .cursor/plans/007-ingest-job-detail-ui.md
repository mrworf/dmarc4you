# Plan: Ingest job list + detail UI (Phase 3 — ingest job detail UI/API)

## Goal

Complete the “ingest job detail UI/API” item from Phase 3: add a **list ingest jobs** endpoint and a **frontend view** so users can see their recent ingest jobs and open one to view state, item counts, and per-report outcomes. No new auth or domain logic; reuse existing session and owner rule (actor_user_id = current user).

## Why this slice

- Slices 1–6 are done (bootstrap through dashboard). Phase 3 calls out “ingest job detail UI/API”; the **API** for a single job already exists (`GET /api/v1/ingest-jobs/{job_id}`). The **UI** and a way to discover job IDs (list) are missing.
- Smallest vertical slice: one new backend endpoint (list), one new UI flow (list + detail), no schema changes, no new policies.
- Advances the product: after submitting reports (e.g. via API or future CLI), the user can open the app and see job status and per-report results.

## Scope (in)

- **Backend**
  - `GET /api/v1/ingest-jobs`: list ingest jobs for the current user (session required). Query params: `limit` (default 50, max 100), optional `cursor`/page if needed (keep minimal: single page with limit). Return list of `{ job_id, state, submitted_at }` ordered by `submitted_at` desc. Owner = rows where `actor_user_id = current_user_id`.
  - Ingest service: add `list_jobs(config, user_id, limit)` returning list of dicts; handler calls it.
- **Frontend**
  - New “Ingest jobs” view: nav link (e.g. from Domains/Dashboards area), list of recent jobs (from `GET /api/v1/ingest-jobs`), each row linking to a detail view.
  - Ingest job detail view: show job_id, state, submitted_at, accepted_count, duplicate_count, invalid_count, rejected_count, and a table of items (item_id, report_type_detected, domain_detected, status, status_reason). Data from existing `GET /api/v1/ingest-jobs/{job_id}`. Back link to list.
- **Docs**: Document `GET /api/v1/ingest-jobs` in `docs/API_V1.md`.
- **Tests**: Integration test for `GET /api/v1/ingest-jobs` (200 with list; only current user’s jobs; 401 when not authenticated).

## Scope (out)

- API key auth or API-key-submitted jobs (actor_user_id null); list/detail owner rule stays “actor_user_id = current user” for this slice.
- Pagination (cursor) beyond a single `limit`; optional.
- Submitting reports from the UI (no ingest form in this slice).
- Changes to job runner or ingest pipeline.

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/ingest_service.py` | Add `list_jobs(config, user_id, limit)` → list of `{ job_id, state, submitted_at }`. |
| `backend/api/v1/handlers/reports.py` | Add `GET /ingest-jobs` (on `ingest_jobs_router`) with optional `limit` query param; call `ingest_service.list_jobs`; return `{ jobs: [...] }`. |
| `docs/API_V1.md` | Document `GET /api/v1/ingest-jobs` (query params, response shape). |

### Frontend

| Path | Action |
|------|--------|
| `frontend/index.html` | Add section `#ingest-jobs-view` (list + optional “View job by ID” input) and `#ingest-job-detail-view` (job detail: state, counts, items table). Add nav link “Ingest jobs” (e.g. next to Dashboards) that shows ingest-jobs-view. |
| `frontend/js/app.js` | Add `showIngestJobs()`, `showIngestJobDetail()`; `loadIngestJobsPage()` (fetch list, render links); `loadIngestJobDetail(jobId)` (fetch `GET /ingest-jobs/{id}`, render state + counts + items); wire nav and back link. Ensure both views hide/show correctly with existing login/domains/dashboards views. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_ingest.py` (or new `test_ingest_jobs.py`) | Add test: create job as user A, list as user A → job in list; list as user B (or unauthenticated) → 401 or empty/not visible. Prefer extending existing ingest tests if they already have session fixtures. |

---

## Acceptance criteria

1. **GET /api/v1/ingest-jobs** with valid session: 200, body `{ jobs: [ { job_id, state, submitted_at }, ... ] }` containing only jobs where `actor_user_id` = current user, ordered by `submitted_at` desc, up to `limit` (default 50, max 100). Without session: 401.
2. **UI — List**: User can open “Ingest jobs” from the app; sees list of their recent jobs (job_id, state, submitted_at); can click a job to open detail.
3. **UI — Detail**: User can view a single job (by click from list or by entering job_id): state, submitted_at, accepted/duplicate/invalid/rejected counts, and table of items (report_type_detected, domain_detected, status, status_reason). 404 handled (e.g. “Job not found” or redirect to list).
4. **Owner rule**: List and existing detail endpoint return only jobs owned by the current user (actor_user_id = current user).

---

## Tests and validation

1. **Integration**
   - `GET /api/v1/ingest-jobs` without auth → 401.
   - Create ingest job as user A; `GET /api/v1/ingest-jobs` as user A → 200, list includes that job.
   - As user B, `GET /api/v1/ingest-jobs` → list does not include user A’s job; `GET /api/v1/ingest-jobs/{job_id}` for A’s job → 404.
2. **Manual**: Log in, create a job (e.g. via existing POST /reports/ingest in tests or curl), open Ingest jobs in UI, see job in list, open detail and see state and items.
3. **Run**: `pytest tests/` passes.

---

## Dependencies

- Existing: `GET /api/v1/ingest-jobs/{job_id}`, session auth, `ingest_service.get_job_detail`, `ingest_service.create_ingest_job`.
- No new migrations; no changes to RBAC or domain scoping (ingest jobs are user-scoped by existing owner check).

---

## Notes

- When API key ingest is added later, list/detail may need to include jobs where the actor is an API key “owned” by the current user (e.g. keys created by them); that can be a follow-up. This slice keeps owner = `actor_user_id = current_user_id` only.
