# Plan: Domain archive and restore (Phase 5 — backend only)

## Goal

Implement the first part of Phase 5 (domain lifecycle): **archive** and **restore** domain transitions. Super-admin only. Backend only in this slice (no UI, no delete, no retention, no archive storage). Ingest already rejects archived domains via `domain_check`; this slice adds the transitions and ensures list visibility obeys the rule: non–super-admins do not see archived domains; super-admin sees all (active + archived) so they can restore.

## Why this slice

- Slices 1–7 are done. Phase 5 calls for “archive/restore/delete domain flows”. The schema already has `status`, `archived_at`, `archived_by_user_id` in `domains`. The smallest increment is archive + restore only.
- Advances the product: super-admin can archive a domain (it disappears from non–super-admin lists and ingest is rejected) and restore it (it becomes visible again). No new tables; no dormant dashboard behavior yet.

## Scope (in)

- **Policy**: `can_archive_domain(role)`, `can_restore_domain(role)` — true only for `super-admin`.
- **Domain service**:
  - `archive_domain(config, domain_id, actor_user_id, actor_role)` → (`ok` | `forbidden` | `not_found` | `already_archived`, domain dict | None). Require domain exists and `status = active`; set `status = 'archived'`, `archived_at = now`, `archived_by_user_id = actor_user_id`.
  - `restore_domain(config, domain_id, actor_role)` → (`ok` | `forbidden` | `not_found` | `not_archived`, domain dict | None). Require domain exists and `status = archived`; set `status = 'active'`, `archived_at = NULL`, `archived_by_user_id = NULL`.
- **list_domains**: For super-admin, return **all** domains (remove `WHERE status = ?` filter) so archived domains are visible and restorable. For non–super-admin, keep current behavior: only assigned and **active** domains.
- **Handlers**: `POST /api/v1/domains/{domain_id}/archive`, `POST /api/v1/domains/{domain_id}/restore`. Session required; super-admin only; return updated domain or 403/404/400 (e.g. already_archived → 400).
- **Docs**: Update `docs/API_V1.md` (and optionally `docs/DOMAIN_LIFECYCLE.md`) to state list behavior and archive/restore semantics.
- **Tests**: Archive as super-admin → 200, domain status archived; list as non–super-admin excludes archived domain; restore as super-admin → 200, status active; archive as non–super-admin → 403; archive already-archived → 400 or 409; restore active domain → 400 or 409; restore non-existent → 404.

## Scope (out)

- Domain delete (only when archived).
- Archive storage / artifact storage.
- Retention scheduler, pause/unpause.
- Dormant dashboard behavior (is_dormant).
- Restore of user assignments / API key bindings (we do **not** remove assignments on archive; restore is just status flip).
- UI for archive/restore (backend only in this slice).

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/policies/domain_policy.py` | Add `can_archive_domain(actor)`, `can_restore_domain(actor)` (super-admin only). |
| `backend/services/domain_service.py` | Add `archive_domain(...)`, `restore_domain(...)`. Update `list_domains`: for super-admin, select all domains (any status); for others, keep `status = 'active'` and assigned. |
| `backend/api/v1/handlers/domains.py` | Add `POST /{domain_id}/archive`, `POST /{domain_id}/restore`; call service; return 200 with domain or 403/404/400. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document archive/restore: request/response, super-admin only; note that GET /domains for super-admin returns active and archived. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_domains.py` (or new `test_domain_lifecycle.py`) | Tests: archive as super-admin (200, status archived); list as non–super-admin does not include archived domain; restore as super-admin (200, status active); archive as non–super-admin (403); archive already-archived (400/409); restore active (400/409); restore non-existent (404). |

---

## Acceptance criteria

1. **POST /api/v1/domains/{domain_id}/archive** as super-admin: domain exists and is active → 200, body includes domain with `status: "archived"`, `archived_at` set. As non–super-admin → 403. Already archived → 400 or 409. Non-existent domain → 404.
2. **POST /api/v1/domains/{domain_id}/restore** as super-admin: domain exists and is archived → 200, body includes domain with `status: "active"`, `archived_at` null. As non–super-admin → 403. Domain active → 400 or 409. Non-existent → 404.
3. **GET /api/v1/domains** as super-admin returns all domains (active and archived). As non–super-admin returns only assigned **active** domains (archived domains excluded).
4. Ingest for an archived domain continues to be rejected (existing `domain_check` behavior; no change required in this slice).

---

## Tests and validation

1. **Integration**: Use existing domain fixtures; create domain as super-admin; archive it → 200, status archived; list as another user (non–super-admin) → archived domain not in list; restore as super-admin → 200, status active. Archive as admin → 403. Archive same domain again → 400 or 409. Restore non-existent id → 404.
2. **Run**: `pytest tests/` passes.

---

## Dependencies

- Existing: `domains` table with `status`, `archived_at`, `archived_by_user_id`; `domain_check` in ingest rejects archived; `list_domains` and domain policy.
- No new migrations.
