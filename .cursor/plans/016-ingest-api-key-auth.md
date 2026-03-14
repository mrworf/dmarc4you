# Plan: Ingest with API key auth (Phase 2)

## Goal

Allow **POST /api/v1/reports/ingest** to be authenticated with an **API key** (Bearer token) in addition to session. When a valid key with scope `reports:ingest` is used, create the job with `actor_type='api_key'`, `actor_api_key_id` set, and `actor_user_id` NULL. The **job runner** must authorize per-report domain using the key's bound domains (api_key_domains) instead of user assignments. Optionally allow **GET /api/v1/ingest-jobs** and **GET /api/v1/ingest-jobs/{id}** with API key auth so the CLI can list/poll jobs created by that key.

## Why this slice

- Phase 2: "API key auth for ingest". PRODUCT: "CLI uses API key only." Slice 015 added API key CRUD; keys have domains and scopes but ingest currently accepts only session. This slice wires key validation into ingest and the runner.

## Scope (in)

- **API key validation**: Add a function (e.g. in api_key_service or auth) that, given a raw Bearer token and config, finds an enabled API key whose key_hash verifies (using existing verify_password), and whose scopes include `reports:ingest`; returns (key_id, list of domain_ids for that key) or None. Iterate enabled keys and verify; keep scope small (few keys in v1).
- **Ingest endpoint**: Accept either session (current behavior) or `Authorization: Bearer <key>`. If Bearer present, validate key and scope; if valid, create job with actor_type='api_key', actor_api_key_id=key_id, actor_user_id=NULL. If invalid key or missing scope → 401 or 403. Session flow unchanged: actor_type='user', actor_user_id=current_user["id"], actor_api_key_id=NULL.
- **create_ingest_job**: Extend signature to accept actor_type, actor_user_id (optional), actor_api_key_id (optional). Persist all three in ingest_jobs.
- **Runner**: When claiming a job, read actor_api_key_id. If set, load key's domain_ids from api_key_domains; for each item use domain check that allows the report domain only if it is in that set and domain is active. If actor_user_id set (user job), keep current behavior (get_user_by_id, can_ingest_for_domain with user/role). If both NULL (shouldn't happen) treat as rejected.
- **domain_check**: Extend `can_ingest_for_domain` (or add overload) to support actor_api_key_id: when provided, resolve domain name to domain_id, check domain is active, and check domain_id is in api_key_domains for that key.
- **List/detail with key** (optional but useful for CLI): If request has valid Bearer key and no session, GET /ingest-jobs returns jobs where actor_api_key_id = that key. GET /ingest-jobs/{id} with Bearer returns job if actor_api_key_id matches. Session-based list/detail unchanged (user sees only their user_id jobs; API-key jobs have actor_user_id NULL so they don't appear in session list).
- **Docs**: Document that ingest (and optionally list/detail) accept session or Bearer API key; key must have scope reports:ingest.
- **Tests**: Ingest with valid API key → 201, job has actor_api_key_id; run job, report for key's domain → accepted. Ingest with invalid key → 401. Ingest with key without reports:ingest scope → 403. Ingest with key whose domain doesn't include report domain → job runs but item rejected.

## Scope (out)

- Rate limiting; last_used_* updates on key (future).
- Multiple scope types beyond reports:ingest.

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/services/api_key_service.py` | Add `validate_api_key_for_ingest(config, raw_token: str) -> tuple[str, list[str]] | None`. Load enabled keys (id, key_hash); for each verify_password(raw_token, key_hash); if match, load scopes (must include "reports:ingest") and domain_ids, return (key_id, domain_ids). Return None if no match or scope missing. |
| `backend/api/v1/deps.py` | Add `get_ingest_actor(request)` (or similar): try session via get_current_user; if 401, try Authorization Bearer; if valid key, return dict with type='api_key', key_id, domain_ids; else 401. Use this only for ingest (and optionally ingest-jobs) so other endpoints stay session-only. |
| `backend/api/v1/handlers/reports.py` | post_reports_ingest: use get_ingest_actor; if user, create_ingest_job(..., 'user', user_id, None); if api_key, create_ingest_job(..., 'api_key', None, key_id). Optionally: list_ingest_jobs and get_ingest_job can accept optional API key auth and filter by actor_api_key_id. |
| `backend/services/ingest_service.py` | create_ingest_job(config, envelope, actor_type, actor_user_id=None, actor_api_key_id=None). Persist actor_type, actor_user_id, actor_api_key_id. list_jobs(config, actor_user_id=None, actor_api_key_id=None): if actor_api_key_id set return jobs for that key; else return jobs for actor_user_id. get_job_detail: allow lookup by actor_api_key_id when key is caller. |
| `backend/ingest/domain_check.py` | Add signature or overload: `can_ingest_for_domain(config, domain_name, actor_user_id=None, actor_role=None, actor_api_key_id=None)`. When actor_api_key_id is set, resolve domain name to id, check active, check domain_id in api_key_domains for that key. When user, keep current logic. |
| `backend/jobs/runner.py` | When selecting job, also select actor_api_key_id. If actor_api_key_id set, load key's domain_ids once; for _process_one_item pass (actor_api_key_id, key_domain_ids) or equivalent so domain_check can allow by key. If user job, pass actor_user_id and role as now. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document that POST /reports/ingest accepts session or Authorization: Bearer <api_key>; key must have scope reports:ingest. Optionally document GET /ingest-jobs and GET /ingest-jobs/{id} with Bearer for key-created jobs. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_ingest.py` or new | Create API key with scope reports:ingest and one domain; POST ingest with Bearer key → 201, job has actor_api_key_id; run job with report for that domain → accepted. POST ingest with Bearer invalid key → 401. POST with key without reports:ingest scope → 403. (Scope test may require creating key with no scope or different scope.) |
| `tests/integration/test_apikeys.py` | No change unless we add a key-without-scope create path for test. |

---

## Acceptance criteria

1. **POST /api/v1/reports/ingest** with `Authorization: Bearer <valid_key>` where key has scope reports:ingest: 201, job created with actor_type='api_key', actor_api_key_id set, actor_user_id NULL.
2. **Runner** processes that job: for each report, domain is checked against key's api_key_domains and domain status active; if allowed, report accepted; otherwise rejected.
3. **POST /api/v1/reports/ingest** with invalid or missing Bearer (and no session): 401.
4. **POST /api/v1/reports/ingest** with valid key that does not have scope reports:ingest: 403.
5. Session-based ingest unchanged: POST with session creates user job; list/detail by session show only user's jobs (API-key jobs not listed).

---

## Tests and validation

1. **Integration**: Create key (reports:ingest + domain); POST ingest with Bearer key → 201; run_one_job; assert report for that domain accepted. Invalid Bearer → 401. Key without scope → 403 (if we can create such a key in test).
2. **Run**: `pytest tests/` and existing ingest tests still pass.

---

## Key lookup performance

Validating Bearer by iterating enabled keys and calling verify_password is O(n) with Argon2 cost. Acceptable for v1 with limited keys; if needed later we can add a fast lookup (e.g. key prefix stored in token format).
