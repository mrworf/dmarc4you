## Slice

18. Contract verification slice

## Scope

- frontend-only contract verification for migrated `frontend-next` routes
- validate the FastAPI OpenAPI contract used by the frontend without changing backend behavior
- focus on `auth`, `domains`, `dashboards`, `search`, `users`, `apikeys`, `audit`, and `upload`

## Files expected to change

- `frontend-next/package.json`
- `frontend-next/scripts/check-api-contracts.mjs`
- `frontend-next/scripts/export_openapi_contracts.py`
- `docs/FRONTEND_MIGRATION.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Implementation notes

- use the repo `.venv` and FastAPI OpenAPI output to keep the backend as the source of truth
- validate request/response schema refs and generic response placeholders for frontend-dependent endpoints
- keep the runner self-contained and avoid relying on a live backend process

## Validation

- `npm run contracts:check`
- `npm run build`

## Risks

- the contract runner depends on the local project Python environment being installed
