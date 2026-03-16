# Plan: Frontend migration users admin slice

## Slice

Implement the next approved slice from `docs/FRONTEND_MIGRATION_SLICES.md`:

- `13. Users admin slice`

## Scope

- frontend-only work in `frontend-next/`
- keep FastAPI `/api/v1/users` and `/api/v1/domains` endpoints authoritative
- migrate list, create, edit, reset-password, and domain assignment UX
- preserve admin/super-admin route guards and backend RBAC

## Files to change

- `frontend-next/lib/api/types.ts`
- `frontend-next/components/users-content.tsx`
- `frontend-next/app/users/page.tsx`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Validation

- run focused `frontend-next` build validation
- report results honestly, including anything not manually verified
