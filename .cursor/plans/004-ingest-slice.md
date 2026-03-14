# Plan: Ingest slice (Phase 2 — enqueue job, worker, parse aggregate XML, persist normalized)

## Goal

Implement the Ingest vertical slice: POST /api/v1/reports/ingest creates a persisted ingest job and job items (one per report); an in-process job runner processes queued jobs; for each item decode/decompress as needed, parse a simple DMARC aggregate XML, check domain (configured, not archived, actor authorized), dedupe, and persist minimal normalized data; GET /api/v1/ingest-jobs/{job_id} returns job detail with per-report outcomes. Session auth only (no API key in this slice).

## Why this slice

- Bootstrap, Auth, and Domain slices are done; domains exist and can be listed.
- Ingest slice is next in `docs/IMPLEMENTATION_PLAN.md`; required before Search (query normalized data) and Dashboards.
- Delivers: async ingest API, job + items persistence, restart-safe runner, minimal aggregate parsing, normalized storage, job detail API.

## Scope (in)

- **Schema**: `ingest_jobs` (id, actor_type, actor_user_id, submitted_at, started_at, completed_at, state, last_error, retry_count), `ingest_job_items` (id, job_id, sequence_no, raw_content_type, raw_content_encoding, raw_content, report_type_detected, domain_detected, status, status_reason, started_at, completed_at), minimal `aggregate_reports` or `aggregate_report_records` (e.g. report_id, org_name, domain, date_begin, date_end, job_item_id, created_at) for dedupe and normalized storage.
- **POST /api/v1/reports/ingest**: JSON envelope with `reports[]` (content_type, content_encoding, content_transfer_encoding, content, optional metadata). Validate envelope; create job (state=queued), create one item per report (store raw content or reference). Return `{ job_id, state: "queued" }`. Auth: session required; no domain check at submit time (done in worker).
- **Job runner**: In-process (e.g. background thread or async loop). Periodically or on trigger, claim one job with state=queued (or retry processing), set state=processing; for each item: decode base64 if present, decompress gzip if present, parse XML, detect aggregate, extract report_metadata (org_name, report_id, date_range) and policy_published (domain); check domain exists and status=active and actor has access; dedupe by (report_id, domain); if duplicate set item status duplicate; if domain reject set rejected; if parse error set invalid; else persist normalized row(s) and set accepted. Update job state when all items done. Restart-safe: jobs left in "processing" can be re-picked and retried (idempotent via dedupe).
- **GET /api/v1/ingest-jobs/{job_id}**: Return job + items (job_id, state, counts, items with item_id, report_type_detected, domain_detected, status, status_reason). Scope: only jobs created by current user (actor_user_id = current user).
- **Policy**: Actor can ingest for domain only if super-admin or has user_domain_assignment for that domain. Archived domain → reject.
- **Dedupe**: Deterministic key (report_id + domain). One row in normalized table per (report_id, domain) or use unique constraint.

## Scope (out)

- API key auth for ingest (Phase 2 deliverable but can be follow-up slice).
- Forensic reports, MIME/email parsing, zip (only gzip + base64 + plain XML in this slice).
- GET /api/v1/ingest-jobs list (optional; can add in same slice or later).
- Archive storage (store raw artifact); only DB persistence.
- Full aggregate record fields (only minimal: report_id, org_name, domain, date_begin, date_end).

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/storage/sqlite/migrations/004_ingest_jobs.sql` | Tables: ingest_jobs, ingest_job_items, aggregate_reports (report_id, org_name, domain, date_begin, date_end, job_item_id, created_at; unique on report_id+domain for dedupe). |
| `backend/ingest/__init__.py` | Package. |
| `backend/ingest/aggregate_parser.py` | Parse aggregate XML (safe): extract org_name, report_id, date_begin, date_end, policy_domain from feedback/report_metadata and policy_published; return dict or None on parse error. |
| `backend/ingest/domain_check.py` | Given domain name, config, actor_user_id, actor_role: lookup domain by name; return (allowed bool, reason). Super-admin allowed for all active; others only if assigned. |
| `backend/ingest/dedupe.py` | Check if (report_id, domain) already in aggregate_reports; return True if duplicate. |
| `backend/jobs/__init__.py` | Package. |
| `backend/jobs/runner.py` | Loop: claim next queued/processing job, process each item (decode, decompress, parse, domain check, dedupe, persist or set status), update job state. Call from main or app lifespan. |
| `backend/services/ingest_service.py` | create_ingest_job(config, envelope, actor_user_id) → job_id; get_job_detail(config, job_id, current_user_id) → job dict or None. |
| `backend/api/v1/handlers/reports.py` | POST /reports/ingest (body envelope, create job, return job_id); GET /ingest-jobs/{job_id} (return detail, 404 if not found or not owner). |
| `tests/integration/test_ingest.py` | POST ingest with minimal aggregate XML (plain or base64/gzip), run runner, GET job detail, assert item accepted and normalized row exists; reject unconfigured domain; duplicate report_id+domain → duplicate; invalid XML → invalid. |

### Edit

| Path | Change |
|------|--------|
| `backend/api/v1/__init__.py` | Include reports router (prefix /reports) and ingest-jobs route (under same or separate router). |
| `backend/main.py` | Start job runner (thread or asyncio task) after app ready; ensure runner stops on shutdown. |
| `docs/IMPLEMENTATION_PLAN.md` | Mark Ingest slice done. |
| `docs/API_V1.md` | Document POST /reports/ingest and GET /ingest-jobs/{id} (already partially there). |

---

## Acceptance criteria

1. **POST /api/v1/reports/ingest** with valid session and envelope (one report, plain XML or base64+gzip): 202 or 200, body `{ job_id, state: "queued" }`.
2. **Worker** processes job: item with valid aggregate XML and configured domain (actor has access) → status accepted, one row in aggregate_reports.
3. **GET /api/v1/ingest-jobs/{job_id}** as job owner: 200, job state, items with status.
4. **Domain not configured or archived** → item status rejected (do not leak reason in API; internal log ok).
5. **Duplicate** (same report_id + domain already in aggregate_reports) → item status duplicate.
6. **Invalid XML** → item status invalid.
7. **Restart-safe**: Job in "processing" can be re-run; dedupe prevents double-insert; no crash on restart.

---

## Tests and validation

1. **Integration**: Create job via POST ingest with minimal valid aggregate XML (inline or base64); run runner once; GET job detail; assert one item accepted, one aggregate_reports row. Same envelope resubmitted → second job, item duplicate. Submit report for domain not in DB → item rejected. Submit malformed XML → item invalid.
2. **Unit** (optional): aggregate_parser returns expected dict for valid XML; returns None for invalid.
3. **Run**: `pytest tests/` passes.

---

## Risks and mitigations

- **XML safety**: Use defusedxml or stdlib xml.etree with safe defaults (no external entities, bounded size).
- **Decompress limits**: Limit gzip expanded size to avoid DoS.
- **Actor scope**: GET job detail only for job owner (actor_user_id = current user).

---

## Dependencies

- Domain slice: domains table, user_domain_assignments; domain_service or policy for "can user ingest for domain?"
- DATA_MODEL: ingest jobs/items, aggregate report fields.
- INGESTION_PIPELINE: per-report outcome, restart-safe, dedupe.
