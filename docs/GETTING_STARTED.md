# Getting Started

This guide covers local installation, core configuration, first login, and the initial admin setup flow.

## Prerequisites

- Python 3.12+
- Node.js 22+
- `pip`

## Install locally

```bash
git clone <repository-url>
cd dmarc4you

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml

cd frontend
npm install
cd ..
```

For contributor and test tooling, install the dev requirements too:

```bash
pip install -r requirements-dev.txt
```

Start the backend:

```bash
python -m backend.main
```

Start the frontend in another terminal:

```bash
cd frontend
npm run dev
```

Default local URLs:

- Frontend: `http://127.0.0.1:3000`
- Backend API: `http://127.0.0.1:8000`

## Run with Docker Compose

Prebuilt images are published to GitHub Container Registry:

- `ghcr.io/mrworf/dmarc4you-backend`
- `ghcr.io/mrworf/dmarc4you-frontend`

Start from the repository root:

```bash
cp compose.env.example compose.env
docker compose --env-file compose.env up -d
```

Default Docker URLs:

- Frontend: `http://127.0.0.1:3000`
- Backend API: `http://127.0.0.1:8000`

The compose stack uses:

- `dmarc_data` volume for SQLite at `/app/data/dmarc.db`
- `dmarc_archive` volume for optional artifact archival at `/app/archive`
- `./data/geoip` bind mount for optional MMDB files at `/app/geoip`
- commented bind-mount examples in `compose.yaml` if you prefer `./data` and `./archive` on the host

Before exposing the stack beyond local testing:

- set `DMARC_SESSION_SECRET` in `compose.env`
- set `DMARC_FRONTEND_PUBLIC_ORIGIN`, `DMARC_CORS_ALLOWED_ORIGINS`, and `DMARC_API_PUBLIC_URL` to public URLs
- set `DMARC_SESSION_COOKIE_SECURE=true` when running behind HTTPS

If you want a bundled reverse proxy for local HTTPS or a cleaner public edge, use:

```bash
docker compose --env-file compose.env -f compose.yaml -f compose.override.proxy.yaml up -d
```

Then set:

- `DMARC_FRONTEND_HOST` for the frontend host Caddy should serve
- `DMARC_API_HOST` for the API host Caddy should serve

## Configuration

Config is loaded from `config.yaml` unless `DMARC_CONFIG` points somewhere else. `DMARC_*` environment variables override YAML values.

For container deployments, `compose.env` is usually enough and `config.yaml` can be omitted.

| Option | Env var | Default | Notes |
| --- | --- | --- | --- |
| `database.path` | `DMARC_DATABASE_PATH` | `data/dmarc.db` | SQLite file path |
| `log.level` | `DMARC_LOG_LEVEL` | `INFO` | `VERBOSE`, `INFO`, `WARN`, `ERROR` |
| `server.host` | `DMARC_SERVER_HOST` | `0.0.0.0` | Backend bind host |
| `server.port` | `DMARC_SERVER_PORT` | `8000` | Backend bind port |
| `auth.session_secret` | `DMARC_SESSION_SECRET` | `change-me-in-production` | Must be changed outside dev |
| `auth.session_cookie_name` | `DMARC_SESSION_COOKIE` | `dmarc_session` | Session cookie name |
| `auth.session_max_age_days` | `DMARC_SESSION_MAX_AGE_DAYS` | `7` | Session lifetime |
| `auth.session_cookie_secure` | `DMARC_SESSION_COOKIE_SECURE` | `false` | Set true behind HTTPS |
| `auth.session_cookie_same_site` | `DMARC_SESSION_COOKIE_SAME_SITE` | `lax` | Browser session cookie policy |
| `auth.csrf_cookie_same_site` | `DMARC_CSRF_COOKIE_SAME_SITE` | `strict` | Browser CSRF cookie policy |
| `frontend.public_origin` | `DMARC_FRONTEND_PUBLIC_ORIGIN` | `null` | Set when frontend is served separately |
| `api.public_url` | `DMARC_API_PUBLIC_URL` | `null` | Public backend URL for split-origin setups |
| `cors.allowed_origins` | `DMARC_CORS_ALLOWED_ORIGINS` | empty | Optional split-origin browser allowlist |
| `archive.storage_path` | `DMARC_ARCHIVE_STORAGE_PATH` | `null` | Optional raw artifact storage path |
| `dns.nameservers` | `DMARC_DNS_NAMESERVERS` | empty | Optional PTR resolver override list |
| `dns.timeout_seconds` | `DMARC_DNS_TIMEOUT_SECONDS` | `5.0` | Reverse DNS timeout |
| `dns.monitor_default_interval_seconds` | `DMARC_DNS_MONITOR_DEFAULT_INTERVAL_SECONDS` | `300` | DNS monitoring fallback interval |
| `geoip.provider` | `DMARC_GEOIP_PROVIDER` | `none` | `none`, `dbip-lite-country`, `maxmind-geolite2-country` |
| `geoip.database_path` | `DMARC_GEOIP_DATABASE_PATH` | `null` | Local MMDB file, typically under `data/` |

Recommended local GeoIP path examples:

- `data/dbip-country-lite.mmdb`
- `data/GeoLite2-Country.mmdb`

## First login

On first startup the backend creates a bootstrap `super-admin` account:

- Username: `admin`
- Password: printed once to the backend console
- First sign-in: requires choosing a new password before the app unlocks

Open the frontend, log in as `admin`, and change the printed password immediately.

If you lose the password, reset it locally:

```bash
python -m cli reset-admin-password
python -m cli reset-admin-password /path/to/config.yaml
```

Any generated password, including this break-glass reset, is temporary and must be changed at the next sign-in.

## Roles and access

| Role | Main capabilities |
| --- | --- |
| `super-admin` | Access all domains, add/archive/restore/delete domains, manage retention, create any user, manage admin domain assignments, view audit log |
| `admin` | Manage users up to `admin` within allowed scope, manage dashboards, create API keys |
| `manager` | Create dashboards, edit owned dashboards, share dashboards where allowed |
| `viewer` | Read-only dashboard and search access |

Access rules that matter operationally:

- `super-admin` always has access to all domains.
- Archived domains are visible only to `super-admin`.
- Dashboard access requires access to every domain attached to the dashboard.
- API keys are domain-bound and scope-bound, not user-bound.

## Initial admin checklist

1. Add your monitored domains in the UI.
2. Create at least one API key with the `reports:ingest` scope.
3. Create any additional users and assign domains as needed.
4. Configure report submission using the API, CLI, or browser upload flow.
5. Create dashboards for the teams that need access.

## Useful URLs

| Path | Purpose |
| --- | --- |
| `/login` | Sign in |
| `/domains` | Domain management |
| `/dashboards` | Dashboard list |
| `/search` | Aggregate and forensic search |
| `/upload` | Browser upload |
| `/ingest-jobs` | Ingest job history |
| `/users` | User management |
| `/apikeys` | API key management |
| `/audit` | Audit log |

## Seeded E2E environment

For local browser verification against seeded data:

```bash
bash scripts/run_seeded_e2e.sh
```

Prerequisites:

- backend Python dependencies installed
- backend dev/test Python dependencies installed
- frontend dependencies installed in `frontend`
- Playwright Chromium installed with `cd frontend && npx playwright install chromium`

Useful outputs:

- `.tmp/e2e/backend.log`
- `.tmp/e2e/frontend.log`
- `.tmp/e2e/seed-summary.json`
- `frontend/playwright-report/`
- `frontend/test-results/`
