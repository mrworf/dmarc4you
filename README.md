# DMARCWatch

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

The backend listens on `http://127.0.0.1:8000` by default and the frontend on `http://127.0.0.1:3000`. On first startup, the bootstrap `admin` password is printed once to the backend console.

## Verification

Before opening a PR, run the dependency audit gate locally:

```bash
bash scripts/check_dependency_audits.sh
```

This checks frontend production dependencies with `npm audit` and backend Python dependencies with `pip-audit`, matching the CI security workflow.

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
- Store local GeoIP MMDB files under `data/`, for example `data/dbip-country-lite.mmdb`.
- `archive.storage_path` is optional. Leave it unset to disable raw artifact archival.

## CLI

```bash
python -m cli ingest --api-key YOUR_KEY report.xml report.xml.gz report.zip report.eml
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
