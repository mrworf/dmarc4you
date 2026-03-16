# DMARC Analyzer

A self-hosted DMARC analysis platform for ingesting, storing, and visualizing DMARC aggregate and forensic reports.

## Quick Start

```bash
# Clone and set up
git clone <repository-url>
cd dmarc4you
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp config.example.yaml config.yaml
# Edit config.yaml — at minimum, change auth.session_secret for production

# Run
python -m backend.main
```

On first startup, the bootstrap admin password is printed to stderr — **save it immediately**.

Open `http://localhost:8000` and log in with username `admin`.

For the split-origin Next.js migration workspace, see [Frontend Migration](docs/FRONTEND_MIGRATION.md) for `.env.local`, CORS, cookie, CSRF, reverse-proxy guidance, and the final legacy-SPA cutover checklist.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | Installation, configuration, first login, user roles |
| [Submitting Reports](docs/SUBMITTING_REPORTS.md) | Send DMARC reports via API, CLI, or browser upload |
| [API v1 Specification](docs/API_V1.md) | REST API reference |
| [Product Specification](docs/PRODUCT.md) | Product requirements and feature scope |
| [Architecture](docs/ARCHITECTURE.md) | System design and component overview |
| [Security and Audit](docs/SECURITY_AND_AUDIT.md) | Authentication, RBAC, and audit logging |
| [Data Model](docs/DATA_MODEL.md) | Database schema and relationships |
| [Domain Lifecycle](docs/DOMAIN_LIFECYCLE.md) | Archive, restore, retention, and purge |
| [Frontend and Dashboards](docs/FRONTEND_AND_DASHBOARDS.md) | SPA and dashboard specifications |
| [Frontend Migration](docs/FRONTEND_MIGRATION.md) | Next.js frontend foundation, deployment, rollout notes, and seeded browser verification |
| [Frontend Migration Slices](docs/FRONTEND_MIGRATION_SLICES.md) | Slice-by-slice plan for the Next.js migration and related scaling work |

## Features

- **Ingest** — Accept DMARC aggregate and forensic reports via API, CLI, or web upload
- **Search** — Query reports with filters, date ranges, and full-text search
- **Dashboards** — Create shareable dashboards with drill-down and bookmarkable URLs
- **RBAC** — Role-based access control with domain scoping
- **API Keys** — Domain-bound keys for automated ingest
- **Archival** — Archive domains with configurable retention and restore capability
- **Audit** — Comprehensive audit trail for security-sensitive actions

## User Roles

| Role | Description |
|------|-------------|
| **super-admin** | Full access to all domains and system settings |
| **admin** | Manage users and dashboards within assigned domains |
| **manager** | Create and share dashboards |
| **viewer** | Read-only access to assigned dashboards |

See [Getting Started](docs/GETTING_STARTED.md) for detailed role permissions.

## CLI Commands

```bash
# Submit DMARC reports
python -m cli ingest --api-key KEY report.xml [report2.xml.gz ...]

# Reset admin password (break-glass recovery)
python -m cli reset-admin-password [config.yaml]

# Seed the deterministic frontend E2E environment
python -m cli seed-e2e [config.e2e.yaml]

# Full seeded frontend browser regression run
cd frontend-next
npm run test:e2e:seeded
```

See [Submitting Reports](docs/SUBMITTING_REPORTS.md) for CLI details.

For the Next.js migration wrap-up, the primary regression path is now the seeded browser harness. See [Frontend Migration](docs/FRONTEND_MIGRATION.md) and [Getting Started](docs/GETTING_STARTED.md#seeded-e2e-browser-environment) for the seeded credentials, reset command, logs, and CI expectations.

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize:

```yaml
database:
  path: data/dmarc.db

log:
  level: INFO  # VERBOSE | INFO | WARN | ERROR

auth:
  session_secret: change-me-in-production  # Required for production
  session_max_age_days: 7

archive:
  storage_path: null  # Optional: path for raw artifact storage

frontend:
  public_origin: null  # Optional: http://localhost:3000 for split-origin dev

api:
  public_url: null  # Optional: backend public URL for separate frontend deployments

cors:
  allowed_origins: []  # Optional: browser origins allowed to call the API
```

All options can be overridden with `DMARC_*` environment variables.

---

## Cursor Workspace Notes

This repository includes Cursor-specific configuration for AI-assisted development:

- `AGENTS.md` — Agent instructions for Cursor and AGENTS.md-aware tools
- `.cursor/rules/*.mdc` — Project rules for code style and architecture
- `.cursor/commands/*.md` — Reusable slash commands
- `.cursor/plans/` — Implementation plans

### Recommended Cursor workflow

1. Keep `AGENTS.md` at the root
2. Start with `/plan-next-slice` before large features
3. Implement as thin vertical slices
4. Read relevant `docs/*.md` before making changes
