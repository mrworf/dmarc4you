## Slice

19. Frontend critical flows expansion slice

## Scope

- frontend-only Playwright coverage expansion
- add a narrow set of high-value happy paths for migrated dashboard, upload, and admin routes
- preserve FastAPI auth, CSRF, and RBAC as the source of truth

## Files expected to change

- `frontend-next/e2e/critical-flows.spec.ts`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Implementation notes

- reuse the existing seeded super-admin login helper
- cover create-dashboard, dashboard detail URL-state, upload submission, user creation, and API key creation
- keep the slice browser-level and avoid adding new backend fixtures here

## Validation

- `npm run test:e2e:list`
- `npm run build`

## Risks

- full execution still depends on a live FastAPI backend plus seeded super-admin access and at least one visible domain
