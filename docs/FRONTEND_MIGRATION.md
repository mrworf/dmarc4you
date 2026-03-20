# Frontend Migration

## Status

The migration is complete.

- `frontend-next/` is the only supported web frontend.
- the backend-served legacy SPA has been retired and removed
- FastAPI remains the source of truth for auth, CSRF, RBAC, domain scoping, ingest behavior, and `/api/v1` business endpoints

This document remains as a historical summary plus a reference for how the current frontend is deployed.

## Final architecture

- Next.js serves the user-facing web UI
- FastAPI serves `/api/v1/...` and backend health endpoints
- the recommended production shape is one public origin behind a reverse proxy:
  - `/` and frontend routes -> Next.js
  - `/api/v1/` -> FastAPI

## Local development

Backend:

```bash
python -m backend.main
```

Frontend:

```bash
cd frontend-next
npm install
npm run dev
```

Recommended split-origin local environment:

```bash
export DMARC_FRONTEND_PUBLIC_ORIGIN=http://127.0.0.1:3000
export DMARC_CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000
export DMARC_API_PUBLIC_URL=http://127.0.0.1:8000
export DMARC_SESSION_COOKIE_SECURE=false
export DMARC_SESSION_COOKIE_SAME_SITE=lax
export DMARC_CSRF_COOKIE_SAME_SITE=strict
```

By default the browser UI runs on `http://127.0.0.1:3000` and calls FastAPI on `http://127.0.0.1:8000`.

## Deployment guidance

Recommended production shape:

- terminate HTTPS at a reverse proxy
- route frontend traffic to Next.js
- route `/api/v1/` to FastAPI
- keep cookie auth and CSRF enforcement on the FastAPI side

Example nginx shape:

```nginx
server {
    listen 443 ssl http2;
    server_name dmarc.example.com;

    location /api/v1/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Recommended production cookie settings:

```bash
export DMARC_SESSION_COOKIE_SECURE=true
export DMARC_SESSION_COOKIE_SAME_SITE=lax
export DMARC_CSRF_COOKIE_SAME_SITE=strict
```

## Observability and readiness

- `frontend-next/app/api/ready/route.ts` provides the frontend readiness endpoint at `GET /api/ready`
- FastAPI health and readiness remain authoritative for backend status
- request ID propagation should stay enabled across the reverse proxy so frontend-side failures can be matched with backend logs

## Historical notes

The migration delivered:

- typed frontend-facing API contracts
- shared API client, auth bootstrap, and route guards
- query-param-based state for search and dashboard views
- browser-level smoke and seeded end-to-end coverage
- cutover validation for the required Next.js routes

The old backend-served SPA is no longer part of the supported deployment model.

## Retained migration tooling

The repository still keeps the validation and browser-regression tooling that made the cutover safe.

Core commands:

```bash
# reseed the dedicated SQLite/archive environment
python -m cli seed-e2e config.e2e.yaml

# inspect the discovered browser matrix quickly
cd frontend-next
npm run test:e2e:list

# run the full seeded browser suite locally
npm run test:e2e:seeded

# verify the required frontend routes still exist
npm run cutover:routes

# verify the frontend-consumed OpenAPI contract
npm run contracts:check
```

The seeded environment still provides:

- deterministic frontend and backend URLs
- seeded super-admin, admin, manager, and viewer accounts
- reproducible aggregate and forensic data for browser checks
- `.tmp/e2e/e2e.env` and `.tmp/e2e/seed-summary.json` for debugging

These checks now exist as regression protection for the production frontend rather than as migration scaffolding for a future cutover.
