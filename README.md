# DMARC Analyzer

A self-hosted DMARC analysis platform for ingesting, storing, and reviewing DMARC aggregate and forensic reports.

## What It Does

- Ingest DMARC reports asynchronously
- Normalize aggregate and forensic data for search and dashboards
- Enforce domain-scoped RBAC and API-key-based ingest
- Support reverse DNS and optional offline GeoIP enrichment
- Provide dashboards, search, upload, audit, and domain lifecycle controls

## Quick Start

```bash
git clone <repository-url>
cd dmarc4you

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.yaml config.yaml
# Edit config.yaml and set a real auth.session_secret

python -m backend.main
```

On first startup, the bootstrap admin password is printed to stderr. Save it immediately.

Open `http://localhost:8000` and log in as `admin`.

## Supported Ingest Formats

- XML DMARC reports
- Gzip-compressed XML (`.gz`, `.gzip`)
- ZIP archives containing supported report payloads
- MIME/RFC822 email messages with report attachments

## Core Features

- Asynchronous ingest jobs with per-report outcomes
- Aggregate and forensic report search
- Shared dashboards with domain scoping
- API key management for automated ingest
- Domain archive, restore, retention, and purge
- Audit trail for security-sensitive actions

## User Roles

| Role | Description |
|------|-------------|
| `super-admin` | Full access to all domains and system settings |
| `admin` | Manage users and dashboards within assigned domains |
| `manager` | Create and share dashboards |
| `viewer` | Read-only access to assigned dashboards |

See [Getting Started](docs/GETTING_STARTED.md) for detailed permissions and first-login guidance.

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
database:
  path: data/dmarc.db

log:
  level: INFO

auth:
  session_secret: change-me-in-production
  session_max_age_days: 7

archive:
  storage_path: null

dns:
  nameservers: []
  timeout_seconds: 1.0

geoip:
  provider: none
  database_path: null
```

Notes:

- `dns.nameservers` is optional. If unset, the host default resolver is used for reverse DNS.
- `geoip.provider` supports `none`, `dbip-lite-country`, and `maxmind-geolite2-country`.
- GeoIP requires a local MMDB file. See [GeoIP Setup](docs/GEOIP_SETUP.md).

All options can be overridden with `DMARC_*` environment variables.

## CLI

```bash
# Submit reports
python -m cli ingest --api-key YOUR_KEY report.xml report.xml.gz report.zip report.eml

# Break-glass admin reset
python -m cli reset-admin-password [config.yaml]
```

See [Submitting Reports](docs/SUBMITTING_REPORTS.md) for API, CLI, and browser-upload examples.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Installation, configuration, bootstrap login, and role overview |
| [Submitting Reports](docs/SUBMITTING_REPORTS.md) | API, CLI, and browser upload flows |
| [API v1](docs/API_V1.md) | REST API reference |
| [GeoIP Setup](docs/GEOIP_SETUP.md) | How to obtain and configure the MMDB database |
| [Architecture](docs/ARCHITECTURE.md) | System design overview |
| [Data Model](docs/DATA_MODEL.md) | Database and normalized ingest model |
| [Security and Audit](docs/SECURITY_AND_AUDIT.md) | Auth, RBAC, and audit behavior |
| [Domain Lifecycle](docs/DOMAIN_LIFECYCLE.md) | Archive, restore, retention, and purge |
| [Frontend and Dashboards](docs/FRONTEND_AND_DASHBOARDS.md) | UI and dashboard behavior |
| [Project History](docs/PROJECT_HISTORY.md) | Migration and implementation-history references |
