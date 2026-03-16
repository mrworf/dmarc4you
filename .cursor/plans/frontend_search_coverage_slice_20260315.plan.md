## Slice

17. Search route slice coverage slice

## Scope

- frontend-only follow-up to the Playwright harness foundation
- extend browser-level coverage for the migrated `/search` route only
- verify query-param restoration, report-type switching, and pagination URL state
- keep FastAPI endpoints and existing route behavior unchanged

## Files expected to change

- `frontend-next/e2e/search.spec.ts`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Implementation notes

- reuse the existing seeded super-admin login helper
- keep tests browser-level and route-focused instead of adding backend fixtures in this slice
- allow pagination coverage to skip when local seeded data does not produce multiple pages

## Validation

- `npm run test:e2e:list`
- `npm run build`

## Risks

- full browser execution still depends on seeded report data and installed Playwright browser binaries
