# Frontend Migration

## Summary

The repository now carries two frontend entrypoints:

- `frontend/` — the legacy backend-served SPA
- `frontend-next/` — the new Next.js migration workspace

The migration is intentionally **frontend-only**. FastAPI remains the source of truth for:

- session authentication
- CSRF enforcement
- RBAC and domain scoping
- ingest jobs and archival behavior
- `/api/v1` business endpoints

## What this slice adds

- typed API response schemas for the first UI-facing endpoints (`auth`, `domains`, `health`)
- standardized API error envelopes with `error.code` and `error.message`
- split-origin deployment config:
  - frontend public origin
  - API public URL
  - CORS allowlist
  - cookie `Secure` and `SameSite` policies
- a standalone Next.js app shell with:
  - centralized API client
  - session bootstrap via `/api/v1/auth/me`
  - CSRF-aware mutations
  - route guards by role
  - URL query-state helpers

## Local development

### Legacy SPA

```bash
python -m backend.main
```

This continues to serve `frontend/` at `http://localhost:8000`.

### Next.js migration workspace

```bash
cd frontend-next
npm install
npm run dev
```

Recommended local env values:

```bash
export DMARC_FRONTEND_PUBLIC_ORIGIN=http://localhost:3000
export DMARC_CORS_ALLOWED_ORIGINS=http://localhost:3000
```

If the frontend talks to FastAPI directly from another origin, the backend must allow that origin and cookies must remain compatible with the chosen deployment model.

## Deployment guidance

Recommended production shape:

- serve Next.js and FastAPI behind the same public origin via a reverse proxy
- keep cookie auth and CSRF on the FastAPI side
- let the frontend call `/api/v1/...` without cross-origin browser complexity

Split-origin deployment is supported, but requires explicit:

- CORS allowlisting
- cookie policy review
- HTTPS with `session_cookie_secure: true`

## Deployment Modes

### Local split-origin development

Use this mode when `frontend-next` runs on its own dev server and FastAPI runs separately.

Frontend example:

```bash
cd frontend-next
cp .env.example .env.local
```

`frontend-next/.env.example` defaults to:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_CSRF_COOKIE_NAME=dmarc_csrf
```

Backend example:

```bash
export DMARC_FRONTEND_PUBLIC_ORIGIN=http://127.0.0.1:3000
export DMARC_CORS_ALLOWED_ORIGINS=http://127.0.0.1:3000
export DMARC_API_PUBLIC_URL=http://127.0.0.1:8000
export DMARC_SESSION_COOKIE_SECURE=false
export DMARC_SESSION_COOKIE_SAME_SITE=lax
export DMARC_CSRF_COOKIE_SAME_SITE=strict
```

Notes:

- the browser talks directly to FastAPI from `http://127.0.0.1:3000`
- FastAPI must explicitly allow the frontend origin in CORS
- session auth still lives entirely on the FastAPI side
- CSRF still uses the FastAPI cookie plus `X-CSRF-Token` header pattern

### Recommended same-origin production shape

Use a reverse proxy so the browser sees one public origin for both Next.js and FastAPI.

High-level shape:

- `/` and other frontend routes -> `frontend-next`
- `/api/v1/` -> FastAPI
- one HTTPS origin for browser traffic

Minimal nginx example:

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

Recommended production config:

```bash
export DMARC_SESSION_COOKIE_SECURE=true
export DMARC_SESSION_COOKIE_SAME_SITE=lax
export DMARC_CSRF_COOKIE_SAME_SITE=strict
```

In this shape:

- `NEXT_PUBLIC_API_BASE_URL` can stay unset so the frontend uses same-origin `/api/v1/...`
- CORS is typically unnecessary because the browser is no longer crossing origins
- FastAPI remains the authority for cookies, CSRF enforcement, and RBAC

### Cookie, CSRF, and CORS checklist

Split-origin:

- set `DMARC_CORS_ALLOWED_ORIGINS` to the exact frontend origin
- keep `session_cookie_secure=false` for plain local HTTP only
- keep the frontend sending credentials and CSRF headers to FastAPI

Same-origin production:

- terminate HTTPS at the reverse proxy
- set `DMARC_SESSION_COOKIE_SECURE=true`
- avoid broad CORS allowlists unless you intentionally expose the API cross-origin
- keep cookie and CSRF behavior on FastAPI; do not reimplement auth in Next.js

## Observability and Readiness

The Next.js workspace now adds a small amount of frontend-owned observability without moving operational authority away from FastAPI.

Frontend/API request correlation:

- `frontend-next/lib/api/client.ts` sends a per-request correlation header on every frontend API call
- the default header name is `X-Request-ID`
- you can override the header name with `NEXT_PUBLIC_REQUEST_ID_HEADER_NAME` if an existing proxy or backend convention requires a different name
- failed browser-side API calls log the request method, route path, frontend request ID, HTTP status, and any echoed backend request ID to the console

Frontend readiness surface:

- `GET /api/ready` is a frontend readiness endpoint owned by `frontend-next`
- it reports whether the frontend is configured for same-origin or split-origin API calls
- it exposes the configured backend target and points operators to FastAPI's backend readiness path: `/api/v1/health/ready`
- it is intentionally minimal and does not attempt to replace backend health or worker health checks

Recommended operational interpretation:

- use `/api/ready` to confirm that the web frontend is up and knows where it expects to find FastAPI
- use FastAPI health/readiness endpoints as the source of truth for backend API availability
- keep worker/job observability on the backend side because ingest jobs, retries, and resume-after-restart behavior remain backend responsibilities

For separate web/backend deployment, a practical minimum is:

- monitor the Next.js process with `/api/ready`
- monitor FastAPI with `/api/v1/health/ready`
- retain request ID propagation across the reverse proxy so frontend error reports can be matched with backend logs
- treat web and worker/process supervision as separate concerns even when they are deployed from the same repository

## Rollout approach

1. Keep the legacy SPA live while migrating route-by-route into `frontend-next/`.
2. Move reusable data/query/form patterns into shared frontend libraries before migrating many screens.
3. Finalize the core frontend testing approach as soon as the shared app shell, auth bootstrap, route guards, and query-state patterns are stable enough to test without immediate churn.
4. Add a frontend test harness slice immediately after that approach is finalized, rather than waiting until late migration hardening.
5. Split frontend quality work into at least two explicit slices:
   - an early **test harness foundation** slice for browser-level tooling, local/CI execution, seeded auth helpers, and narrow smoke coverage for login, domains, dashboards landing, dashboard detail, and route guards
   - a later **critical flows expansion** slice for broader end-to-end coverage across migrated search, dashboard management, upload, and admin routes
6. Preserve existing `/api/v1` shapes whenever possible; prefer additive schema tightening over endpoint redesign.
7. Remove the backend-served legacy SPA only after the Next.js routes cover all required flows and the critical migrated flows are covered by the frontend harness.

## Frontend quality plan

The migration should not rely on late-stage manual verification alone. Once the shared frontend approach is considered stable, the project should implement frontend test harness work as a near-term priority.

Recommended sequencing:

1. stabilize the shared route/data/auth approach in `frontend-next/`
2. land the harness foundation slice immediately after that stabilization point
3. require migrated routes to add or extend smoke coverage as the route surface grows
4. expand the harness again before legacy cutover so critical role-based flows are exercised end to end

Recommended harness scope:

- browser-level tests against the real Next.js app
- reusable login/session helpers that respect FastAPI auth and CSRF behavior
- smoke coverage for route guards and the most-used migrated screens
- URL-state restoration checks for search- and dashboard-style routes
- CI-friendly commands and documentation so the harness is runnable before cutover pressure sets in

## UX Refresh

The Next.js workspace now shifts from migration-oriented scaffolding toward a production-style admin UX.

Key frontend patterns now in use:

- a stable operations shell with a fixed desktop sidebar and mobile nav drawer
- slideover panels for create, edit, import, and assignment workflows
- confirm dialogs for destructive actions
- focused copy-once dialogs for one-time passwords and API secrets
- simpler page copy that explains the task at hand instead of internal migration or backend implementation details

The refresh keeps FastAPI as the authority for auth, RBAC, domain lifecycle, retention, and all mutation behavior. The frontend changes are intentionally presentation- and workflow-oriented only.

## Test Harness Foundation

The migration workspace now includes a minimal Playwright harness in `frontend-next/e2e/` for narrow browser-level smoke coverage of already-migrated routes.

Local prerequisites:

- FastAPI running and reachable by the Next.js app
- a seeded super-admin account for smoke login
- at least one accessible dashboard if you want dashboard-detail smoke coverage without supplying a dashboard ID explicitly

Recommended local env values:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
export DMARC_E2E_SUPERADMIN_USERNAME=admin
export DMARC_E2E_SUPERADMIN_PASSWORD=changeme
# optional if your seed data has a known dashboard id
export DMARC_E2E_DASHBOARD_ID=dash_xxx
```

Recommended commands:

```bash
cd frontend-next
npm install
npx playwright install chromium
npm run test:e2e:list
npm run test:e2e
```

By default the Playwright config starts the Next.js dev server on `http://127.0.0.1:3000`. If you already have the frontend running elsewhere, set:

```bash
export DMARC_E2E_BASE_URL=http://127.0.0.1:3000
export DMARC_E2E_USE_EXISTING_FRONTEND=1
```

## Search Route Coverage

The browser harness now also covers the migrated `/search` route for:

- aggregate filter state round-tripping through the URL
- aggregate/forensic mode switching
- pagination state persisting in the query string

Optional local env values for more deterministic search coverage:

```bash
export DMARC_E2E_SEARCH_DOMAIN=example.com
export DMARC_E2E_SEARCH_QUERY=google
export DMARC_E2E_SEARCH_FROM=2025-01-01
export DMARC_E2E_SEARCH_TO=2025-12-31
```

The pagination test skips automatically when the selected local data set only produces one page of search results.

## Legacy SPA Cutover

The migration workspace now has a small cutover-readiness layer so route parity and role gating can be checked before traffic is switched.

Route coverage:

- `npm run cutover:routes` verifies that the required migrated routes still exist in `frontend-next/app`
- the check covers login, domains, dashboards, search, upload, ingest jobs, users, API keys, audit, and frontend readiness

Role-matrix browser coverage:

- `frontend-next/e2e/role-matrix.spec.ts` extends the Playwright harness with role-aware route checks
- super-admin coverage is required
- admin, manager, and viewer coverage are enabled when seeded credentials are provided

Optional seeded credential env values:

```bash
export DMARC_E2E_ADMIN_USERNAME=admin2
export DMARC_E2E_ADMIN_PASSWORD=changeme
export DMARC_E2E_MANAGER_USERNAME=manager1
export DMARC_E2E_MANAGER_PASSWORD=changeme
export DMARC_E2E_VIEWER_USERNAME=viewer1
export DMARC_E2E_VIEWER_PASSWORD=changeme
```

Recommended cutover sequence:

1. run `npm run cutover:routes`
2. run `npm run test:e2e:list` to confirm the full harness matrix is discovered
3. run `npm run test:e2e` against a seeded environment with at least the super-admin account, and preferably the admin/manager/viewer accounts too
4. switch the reverse proxy so `/` and other user-facing routes point to `frontend-next`
5. keep the backend-served legacy SPA available only as a rollback path until the seeded role matrix passes in the deployment environment

Recommended rollback boundary:

- the reverse proxy switch is the cutover point
- FastAPI remains the source of truth for auth, RBAC, CSRF, and business APIs
- retire the legacy SPA mount only after the Next.js cutover has been stable and the critical role matrix has been re-run in the target environment

## Contract Verification

The migration workspace now includes a frontend-owned contract check that validates the FastAPI OpenAPI contract consumed by migrated routes.

Current coverage focuses on:

- auth login and session bootstrap
- domains and dashboards
- search and forensic report listing
- users, API keys, and audit
- upload/ingest job creation

Recommended command:

```bash
cd frontend-next
npm run contracts:check
```

The contract runner uses the repo `.venv` by default, loads the real FastAPI OpenAPI schema, and verifies the request/response models that `frontend-next` currently depends on. If your Python executable lives elsewhere, set `DMARC_CONTRACT_PYTHON`.

## Critical Flow Expansion

The Playwright harness now also covers a narrow set of critical happy paths across migrated operational routes:

- create dashboard from the dashboards landing route
- dashboard detail filter state restoring from the URL
- upload submission linking to the resulting ingest job
- user creation with one-time password notice
- API key creation with copy-once secret notice

These flows still assume a dedicated E2E environment with a seeded super-admin session and at least one visible active domain.
