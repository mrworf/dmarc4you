# Plan: Frontend migration audit slice

## Slice

Implement the next approved slice from `docs/FRONTEND_MIGRATION_SLICES.md`:

- `15. Audit slice`

## Scope

- frontend-only work in `frontend-next/`
- keep FastAPI `/api/v1/audit` authoritative
- migrate audit table and filter form
- preserve super-admin-only route guard
- persist filters and pagination in query params

## Files to change

- `frontend-next/lib/api/types.ts`
- `frontend-next/components/audit-content.tsx`
- `frontend-next/app/audit/page.tsx`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Validation

- run focused `frontend-next` build validation
- report results honestly, including anything not manually verified
