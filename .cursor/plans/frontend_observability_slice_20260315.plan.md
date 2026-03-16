# Frontend Observability Slice Plan

## Scope

Implement slice 21 from `docs/FRONTEND_MIGRATION_SLICES.md` as a frontend-only change.

## Files to change

- `frontend-next/lib/api/client.ts`
- `frontend-next/app/api/ready/route.ts`
- `frontend-next/.env.example`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Approach

1. Add request-correlation headers to frontend API calls and log failed interactions with enough metadata to match backend logs.
2. Add a minimal frontend readiness endpoint that reports frontend mode and points operators to FastAPI readiness for backend truth.
3. Document how to use frontend readiness plus backend readiness when web and worker responsibilities are split operationally.
