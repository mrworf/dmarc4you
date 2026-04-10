# DMARCWatch

[![dependency-audit](https://github.com/mrworf/dmarc4you/actions/workflows/dependency-audit.yml/badge.svg)](https://github.com/mrworf/dmarc4you/actions/workflows/dependency-audit.yml)
[![frontend-seeded-e2e](https://github.com/mrworf/dmarc4you/actions/workflows/frontend-seeded-e2e.yml/badge.svg)](https://github.com/mrworf/dmarc4you/actions/workflows/frontend-seeded-e2e.yml)
[![docker-publish](https://github.com/mrworf/dmarc4you/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/mrworf/dmarc4you/actions/workflows/docker-publish.yml)
[![ghcr-backend](https://img.shields.io/badge/GHCR-backend%20image-2ea44f?logo=docker&logoColor=white)](https://github.com/mrworf/dmarc4you/pkgs/container/dmarc4you-backend)
[![ghcr-frontend](https://img.shields.io/badge/GHCR-frontend%20image-2ea44f?logo=docker&logoColor=white)](https://github.com/mrworf/dmarc4you/pkgs/container/dmarc4you-frontend)

DMARCWatch is a self-hosted DMARC analysis platform with a FastAPI backend, a Next.js frontend, SQLite storage in v1, asynchronous ingest jobs, domain-scoped RBAC, and audit logging.

> ℹ️ **NOTE** 
>
> This project is entirely created using AI as an experiement. Take it for what you want, as usual, no disclaimers or warranty provided. But seems to work pretty good.

## Core capabilities

- Ingest DMARC aggregate and forensic reports from API, CLI, browser upload, XML files, ZIP/GZIP payloads, and MIME email messages.
- Normalize report data for dashboard views, aggregate exploration, and forensic search.
- Enforce strict domain scoping for users, dashboards, and API keys.
- Support optional reverse DNS and offline GeoIP enrichment during ingest.
- Manage domain archive, restore, retention, and purge workflows.

## Quick start

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

Edit `config.yaml` and set a real `auth.session_secret` before using the service outside local development.

Start the backend:

```bash
python -m backend.main
```

Start the frontend in another terminal:

```bash
cd frontend
npm run dev
```

The backend listens on `http://127.0.0.1:8000` by default and the frontend on `http://127.0.0.1:3000`. On first startup, the bootstrap `admin` password is printed once to the backend console and must be changed after the first sign-in.

For contributor and test tooling, also install:

```bash
pip install -r requirements-dev.txt
```

## Docker quick start

Prebuilt images are published to GitHub Container Registry:

- `ghcr.io/mrworf/dmarc4you-backend`
- `ghcr.io/mrworf/dmarc4you-frontend`
- `ghcr.io/mrworf/dmarc4you-imap`

To run the stack with Docker Compose:

```bash
cp compose.env.example compose.env
docker compose --env-file compose.env up -d
```

The base stack publishes:

- frontend on `http://127.0.0.1:3000`
- backend API on `http://127.0.0.1:8000`

Important notes:

- Set a real `DMARC_SESSION_SECRET` in `compose.env` before exposing the stack outside local development.
- The frontend image reads `NEXT_PUBLIC_API_BASE_URL` at runtime so the same GHCR image can be reused across environments.
- SQLite data persists in the `dmarc_data` volume. Optional raw artifact archival persists in the `dmarc_archive` volume.
- If you prefer bind mounts, `compose.yaml` includes commented examples for `./data:/app/data` and `./archive:/app/archive`.
- Optional offline GeoIP databases can be mounted from `./data/geoip` into `/app/geoip`.
- The optional IMAP collector joins the stack with `docker compose --env-file compose.env --profile imap up -d`; it uploads unread RFC822 messages from a mailbox through the existing ingest API.
- To run the collector on a different host from DMARCWatch, use `docker compose --env-file compose.env -f compose.imap.yaml up -d` and point `DMARC_IMAP_API_URL` at the remote API.
- For HTTPS or a friendlier public entrypoint, start the optional Caddy layer with `docker compose --env-file compose.env -f compose.yaml -f compose.override.proxy.yaml up -d` and set `DMARC_FRONTEND_HOST` / `DMARC_API_HOST` in `compose.env`.

## Verification

Before opening a PR, run the dependency audit gate locally:

```bash
bash scripts/check_dependency_audits.sh
```

This checks frontend production dependencies with `npm audit` and backend Python dependencies with `pip-audit`, matching the CI security workflow.
The Python audit targets runtime dependencies from `requirements.txt`; test-only packages live in `requirements-dev.txt`.

## Configuration highlights

```yaml
database:
  path: data/dmarc.db

auth:
  session_secret: change-me-in-production

archive:
  storage_path: null

dns:
  nameservers: []
  timeout_seconds: 5.0

geoip:
  provider: none
  database_path: null
```

Notes:

- `DMARC_*` environment variables can override YAML config values.
- Container deployments can use `compose.env` without a `config.yaml` file.
- Store local GeoIP MMDB files under `data/`, for example `data/dbip-country-lite.mmdb`.
- `archive.storage_path` is optional. Leave it unset to disable raw artifact archival.

## CLI

```bash
python -m cli ingest --api-key YOUR_KEY report.xml report.xml.gz report.zip report.eml
python -m cli imap-watch --api-key YOUR_KEY --api-url http://localhost:8000 --host imap.example.com --username reports@example.com --password secret
python -m cli reset-admin-password [config.yaml]
python -m cli seed-e2e [config.e2e.yaml] [--cleanup]
```

## Documentation

- [Getting Started](docs/GETTING_STARTED.md)
- [Submitting Reports](docs/SUBMITTING_REPORTS.md)
- [API v1](docs/API_V1.md)
- [GeoIP Setup](docs/GEOIP_SETUP.md)
- [Domain Lifecycle](docs/DOMAIN_LIFECYCLE.md)
- [Security and Audit](docs/SECURITY_AND_AUDIT.md)
