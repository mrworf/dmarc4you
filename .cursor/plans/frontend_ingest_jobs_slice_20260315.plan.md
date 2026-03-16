# Plan: Frontend migration ingest jobs slice

## Slice

Implement the next approved slice from `docs/FRONTEND_MIGRATION_SLICES.md`:

- `12. Ingest jobs slice`

## Scope

- frontend-only work in `frontend-next/`
- use the existing FastAPI `GET /api/v1/ingest-jobs` and `GET /api/v1/ingest-jobs/{job_id}` endpoints
- preserve backend ownership and visibility rules
- keep the detail route aligned with the upload success link

## Files to change

- `frontend-next/lib/api/types.ts`
- `frontend-next/components/ingest-job-detail-content.tsx`
- `frontend-next/components/ingest-jobs-content.tsx`
- `frontend-next/app/ingest-jobs/page.tsx`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Validation

- run the focused Next.js validation commands for the touched app
- report results honestly, including any pre-existing failures
