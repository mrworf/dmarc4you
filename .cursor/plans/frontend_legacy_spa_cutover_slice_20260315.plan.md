# Frontend Legacy SPA Cutover Slice Plan

## Scope

Implement slice 22 from `docs/FRONTEND_MIGRATION_SLICES.md` as a frontend-only cutover-readiness change.

## Files to change

- `frontend-next/e2e/auth.ts`
- `frontend-next/e2e/role-matrix.spec.ts`
- `frontend-next/scripts/check-cutover-routes.mjs`
- `frontend-next/package.json`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`
- `README.md`

## Approach

1. Reuse the existing Playwright harness and add seeded role helpers for admin, manager, and viewer coverage.
2. Add a small route-presence check so cutover prerequisites can be validated without booting the app.
3. Document the cutover sequence as a reverse-proxy switch with explicit rollback boundaries, keeping FastAPI as the backend authority.
