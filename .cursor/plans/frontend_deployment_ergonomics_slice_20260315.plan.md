## Slice

20. Deployment ergonomics slice

## Scope

- frontend-only deployment/documentation work for `frontend-next`
- document local split-origin workflow clearly
- document recommended same-origin production reverse proxy
- call out cookie, CSRF, and CORS expectations for both modes

## Files expected to change

- `frontend-next/.env.example`
- `docs/FRONTEND_MIGRATION.md`
- `README.md`
- `docs/FRONTEND_MIGRATION_SLICES.md`

## Implementation notes

- keep FastAPI as the source of truth for auth, cookies, CSRF, and CORS
- provide copyable env examples rather than changing runtime defaults
- include one small reverse-proxy example instead of introducing deployment tooling

## Validation

- `npm run build`

## Risks

- these docs improve operator clarity, but they do not replace environment-specific proxy or TLS testing
