# Plan: Frontend migration API keys admin slice

## Slice

Implement the next approved slice from `docs/FRONTEND_MIGRATION_SLICES.md`:

- `14. API keys admin slice`

## Scope

- frontend-only work in `frontend-next/`
- keep FastAPI `/api/v1/apikeys` and `/api/v1/domains` endpoints authoritative
- migrate list, create, edit, and delete API key UX
- preserve copy-once secret display behavior after create

## Files to change

- `frontend-next/lib/api/types.ts`
- `frontend-next/components/apikeys-content.tsx`
- `frontend-next/app/apikeys/page.tsx`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Validation

- run focused `frontend-next` build validation
- report results honestly, including anything not manually verified
