## Slice

16. Frontend test harness foundation slice

## Scope

- frontend-only work in `frontend-next/`
- add minimal browser-level tooling for already migrated routes
- preserve FastAPI auth, session, and CSRF behavior as the source of truth
- keep coverage narrow and reusable for later slices

## Files expected to change

- `frontend-next/package.json`
- `frontend-next/playwright.config.ts`
- `frontend-next/e2e/auth.ts`
- `frontend-next/e2e/smoke.spec.ts`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`
- `docs/REPO_STRUCTURE.md`

## Implementation notes

- add Playwright scripts without changing backend behavior
- use seeded super-admin credentials from environment variables
- cover route guard, login, domains, dashboards landing, dashboard detail, and audit smoke paths
- document local execution requirements and the existing-frontend override

## Validation

- `npm run test:e2e:list`
- `npm run build`

## Risks

- full browser execution still depends on a running FastAPI backend, installed browser binaries, and seeded test data
