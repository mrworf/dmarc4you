# Plan: API key CRUD + minimal UI (Phase 6)

## Goal

Implement API key storage and REST CRUD: **schema** (api_keys, api_key_domains, api_key_scopes), **create** (return raw key once), **list** (no secrets), **delete** (revoke). Restrict create/list/delete to **admin** and **super-admin**; domain scope must be subset of caller's allowed domains. Add minimal **/app/apikeys** page: list keys, create form. **Out of scope this slice:** using API key to authenticate ingest (Bearer token); that is a follow-up slice.

## Why this slice

- Phase 6: "API key management UI". DATA_MODEL and API_V1 already describe API keys; no table or endpoints exist. Ingest currently uses session only (actor_api_key_id always NULL). Smallest slice: schema + create + list + delete + minimal UI; ingest auth by key later.

## Scope (in)

- **Migration**: New migration for `api_keys` (id, nickname, description, key_hash, enabled, created_by_user_id, created_at, expires_at, last_used_at, last_used_ip, last_used_user_agent), `api_key_domains` (api_key_id, domain_id), `api_key_scopes` (api_key_id, scope). Use existing domain_id references; scope is a string e.g. `reports:ingest`.
- **Service**: `create_api_key(config, nickname, description, domain_ids, scopes, created_by_user_id, current_user)` → (key_id, raw_secret) or error; enforce domain_ids ⊆ allowed; hash secret (e.g. same as password hash); store. `list_api_keys(config, current_user)` → list of key summaries (id, nickname, description, domain_ids/names, scopes, created_at, expires_at); no secret; super-admin sees all, others see keys they created. `delete_api_key(config, key_id, current_user)` → ok/forbidden/not_found; only creator or super-admin may delete.
- **Handler**: POST /api/v1/apikeys (body: nickname, description?, domain_ids[], scopes[]); GET /api/v1/apikeys; DELETE /api/v1/apikeys/{id}. Session required; 403 for non–admin/super-admin. Create returns 201 with `{ "id", "nickname", "key": "<raw_once>" }` (key only in create response).
- **Docs**: Document the three endpoints in API_V1.md (request/response, who may create/list/delete).
- **Frontend**: Route /app/apikeys; page lists keys (table: nickname, description, domains, scopes, created_at); form to create (nickname, description, domain checkboxes from allowed domains, scopes e.g. single checkbox or dropdown "reports:ingest"); link from nav for admin/super-admin. Delete: optional button per row or follow-up.
- **Tests**: Create as super-admin → 201 and key present once; list as super-admin; delete as creator; create as non-admin → 403; create with disallowed domain → 403; list as manager (no keys) or admin sees own keys.

## Scope (out)

- Ingest endpoint accepting API key (Bearer) and setting actor_api_key_id; that is a separate slice.
- Key rotation / update (PUT); expires_at enforcement on use; last_used_* updates (can be later).
- Scope validation at use time (ingest slice).

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/storage/sqlite/migrations/007_api_keys.sql` (new) | Create api_keys, api_key_domains, api_key_scopes tables per DATA_MODEL. |
| `backend/services/api_key_service.py` (new) | create_api_key, list_api_keys, delete_api_key; use list_domains + policy for allowed domains; hash secret (reuse auth password hashing or secure random + hash). |
| `backend/policies/api_key_policy.py` (new) or in auth | can_create_api_key(role), can_list_api_keys(role), can_delete_api_key(role, key_creator_id). |
| `backend/api/v1/handlers/apikeys.py` (new) | Router GET /apikeys, POST /apikeys (201 + key once), DELETE /apikeys/{id}. |
| `backend/api/v1/__init__.py` | Include apikeys router. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document GET/POST/DELETE /api/v1/apikeys: body for POST, response for create (key once), list shape, 403 rules. |

### Frontend

| Path | Action |
|------|--------|
| `frontend/index.html` | Add #apikeys-view, #apikeys-list, create form (nickname, description, domain checkboxes, scopes), link in nav (for admin/super-admin). |
| `frontend/js/app.js` | showApikeys, loadApikeysPage (fetch list, render table); create form submit → POST apikeys, show key once (e.g. alert or copy box), then reload list; link-audit style for link-apikeys; back/logout. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_apikeys.py` (new) | Fixture with temp DB, admin, domains. Test: create as super-admin → 201, body has key; list → 200; delete → 204; create as viewer/manager → 403; create with domain not in allowed → 403. |

---

## Acceptance criteria

1. **POST /api/v1/apikeys** with session (admin or super-admin), body with nickname, domain_ids (subset of allowed), scopes (e.g. ["reports:ingest"]): 201, response includes `id`, `nickname`, and `key` (raw secret, only in this response). Key is stored hashed; domains and scopes persisted.
2. **GET /api/v1/apikeys** with session (admin or super-admin): 200, list of keys (id, nickname, description, domain_ids or domain_names, scopes, created_at); no raw key. Super-admin sees all keys; others see only keys they created.
3. **DELETE /api/v1/apikeys/{id}** with session: 204 if caller is creator or super-admin; 403 otherwise; 404 if key not found.
4. **/app/apikeys** page: visible to admin/super-admin; lists keys; create form creates key and shows key once; no raw key in list.

---

## Tests and validation

1. **Integration**: Create key as super-admin → 201, key in body; list → 200, keys array; delete → 204; create as non-admin → 403; create with disallowed domain → 403.
2. **Run**: `pytest tests/`; optional UI smoke for /app/apikeys.

---

## Key format and hashing

- Generate a random secret (e.g. 32 bytes hex or `dmarc_` + 32 bytes hex). Store only hash (reuse backend.auth.password hash function if appropriate for secrets; otherwise use a dedicated hash). Return raw key in POST response only once.
