# Plan: Domain delete when archived (Phase 5 — backend only)

## Goal

Implement **DELETE /api/v1/domains/{domain_id}**: permanent removal of an archived domain and its related data. Super-admin only. Domain must be archived; active domains cannot be deleted. Backend only (no UI). Completes the archive/restore/delete flow from Phase 5.

## Why this slice

- Slices 1–8 are done; archive and restore exist. API_V1 and DOMAIN_LIFECYCLE specify delete only when archived. Small, backend-only increment.
- Delete purges: domain row, user_domain_assignments, dashboard_domain_scope, and normalized report data (aggregate_reports) for that domain. No archive storage yet, so no artifact cleanup in this slice.

## Scope (in)

- **Policy**: Reuse super-admin check (only super-admin may delete); add “domain must be archived” in service.
- **Domain service**: `delete_domain(config, domain_id, actor_role)` → (`ok` | `forbidden` | `not_found` | `not_archived`, None). Load domain; if not super-admin → forbidden; if domain missing → not_found; if status != archived → not_archived. Then in one transaction (or ordered deletes): delete from user_domain_assignments WHERE domain_id = ?; delete from dashboard_domain_scope WHERE domain_id = ?; delete from aggregate_reports WHERE domain = ? (use domain name from row); delete from domains WHERE id = ?.
- **Handler**: `DELETE /api/v1/domains/{domain_id}`. Session required; super-admin only. 204 No Content on success; 403/404/400 (not archived) as appropriate.
- **Docs**: Update API_V1.md: DELETE .../domains/{id} implemented; only when archived; super-admin only; 204 on success.
- **Tests**: Delete archived domain as super-admin → 204; domain and related data gone. Delete active domain → 400. Delete as non–super-admin → 403. Delete non-existent → 404.

## Scope (out)

- Archive storage / artifact cleanup (no artifact backend in v1 yet).
- Retention scheduler or auto-delete.
- UI confirmation or soft delete.
- Restore of assignments (delete is permanent; no snapshot).

---

## Files to create or edit

### Backend

| Path | Action |
|------|--------|
| `backend/policies/domain_policy.py` | Add `can_delete_domain(user)` (super-admin only). Optional: keep single “super-admin only” pattern; delete policy can just call same role check. |
| `backend/services/domain_service.py` | Add `delete_domain(config, domain_id, actor_role)`; enforce archived; delete assignments, dashboard_scope, aggregate_reports by domain name, then domain row. |
| `backend/api/v1/handlers/domains.py` | Add `DELETE /{domain_id}`; call delete_domain; return 204 or 403/404/400. |

### Docs

| Path | Action |
|------|--------|
| `docs/API_V1.md` | Document DELETE /api/v1/domains/{domain_id}: super-admin only; domain must be archived; 204 on success; 400 if not archived; 403/404 as applicable. |

### Tests

| Path | Action |
|------|--------|
| `tests/integration/test_domains.py` | Add: delete archived domain as super-admin (204, domain and related rows removed); delete active domain (400); delete as non–super-admin (403); delete non-existent (404). |

---

## Acceptance criteria

1. **DELETE /api/v1/domains/{domain_id}** as super-admin, domain archived: 204 No Content; domain row and its user_domain_assignments, dashboard_domain_scope rows, and aggregate_reports rows for that domain name are removed.
2. **DELETE** as super-admin, domain active: 400 with message that domain must be archived (or equivalent).
3. **DELETE** as non–super-admin: 403.
4. **DELETE** with non-existent domain_id: 404.
5. After successful delete, GET /domains (as super-admin) does not list the domain; list_domains and other reads no longer see it.

---

## Tests and validation

1. **Integration**: Create domain, archive it, DELETE as super-admin → 204. Verify domain row gone; optionally verify assignments and aggregate_reports for that domain removed. Delete active domain → 400. As admin user, DELETE archived domain → 403. DELETE non-existent id → 404.
2. **Run**: `pytest tests/` passes.

---

## Data purge order

To avoid FK issues: SQLite may allow NULL or no FKs on some tables. Safe order: (1) user_domain_assignments, (2) dashboard_domain_scope, (3) aggregate_reports WHERE domain = name, (4) domains. ingest_job_items and ingest_jobs are left as-is (historical jobs; domain_detected is denormalized text).
