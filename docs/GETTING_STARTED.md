# Getting Started

This guide covers installation, configuration, first login, and understanding user roles.

## Prerequisites

- Python 3.12 or later
- pip (Python package manager)
- Node.js 22 or later

## Installation

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd dmarc4you
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # or: .venv\Scripts\activate  # Windows
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a configuration file:

   ```bash
   cp config.example.yaml config.yaml
   ```

5. Edit `config.yaml` (see [Configuration](#configuration) below).

6. Install frontend dependencies:

   ```bash
   cd frontend-next
   npm install
   cd ..
   ```

7. Start the backend API:

   ```bash
   python -m backend.main
   ```

   The backend runs on `http://127.0.0.1:8000` by default.

8. Start the frontend in another terminal:

   ```bash
   cd frontend-next
   npm run dev
   ```

   The frontend runs on `http://127.0.0.1:3000` by default.

## Configuration

Configuration is loaded from `config.yaml` (or the path in `DMARC_CONFIG` env var). All options can be overridden with environment variables.

| Option | Env Variable | Default | Description |
|--------|--------------|---------|-------------|
| `database.path` | `DMARC_DATABASE_PATH` | `data/dmarc.db` | SQLite database file path |
| `log.level` | `DMARC_LOG_LEVEL` | `INFO` | Log level: `VERBOSE`, `INFO`, `WARN`, `ERROR` |
| `auth.session_secret` | `DMARC_SESSION_SECRET` | `change-me-in-production` | Secret for signing session cookies |
| `auth.session_cookie_name` | `DMARC_SESSION_COOKIE` | `dmarc_session` | Session cookie name |
| `auth.session_max_age_days` | `DMARC_SESSION_MAX_AGE_DAYS` | `7` | Session lifetime in days |
| `archive.storage_path` | `DMARC_ARCHIVE_STORAGE_PATH` | `null` | Path for raw artifact archival (optional) |
| `dns.nameservers` | `DMARC_DNS_NAMESERVERS` | empty | Optional PTR resolver override list |
| `dns.timeout_seconds` | `DMARC_DNS_TIMEOUT_SECONDS` | `1.0` | Reverse DNS timeout in seconds |
| `geoip.provider` | `DMARC_GEOIP_PROVIDER` | `none` | Offline GeoIP provider |
| `geoip.database_path` | `DMARC_GEOIP_DATABASE_PATH` | `null` | Local MMDB path for GeoIP |

### Production Configuration

For production deployments:

1. **Change `session_secret`** to a secure random value:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **Set up the database path** to a persistent location with proper backups.

3. **Enable artifact archival** by setting `archive.storage_path` if you want to retain raw report files.

4. **Configure GeoIP** only if you want country enrichment. See [GeoIP Setup](GEOIP_SETUP.md).

## First Login

On first startup, the application creates a bootstrap admin account:

- **Username:** `admin`
- **Password:** Printed to stderr (console) on first boot only

Example startup output:

```
Bootstrap admin password (save it; shown once): Kj8mNp2xQr4vL6wY
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Save this password immediately.** It is not stored and cannot be retrieved.

### Logging In

1. Open `http://127.0.0.1:3000` in your browser.
2. Enter username `admin` and the bootstrap password.
3. You are now logged in as a super-admin.

### Password Recovery

If the admin password is lost, use the break-glass CLI command (requires local access to config and database):

```bash
python -m cli reset-admin-password
# or with explicit config path:
python -m cli reset-admin-password /path/to/config.yaml
```

This resets the `admin` user's password and prints the new password to stdout.

## User Roles

The application has four roles with hierarchical permissions:

| Role | Description |
|------|-------------|
| **super-admin** | Full system access. Can manage all domains, users, and settings. |
| **admin** | Domain-scoped administrator. Can manage users and dashboards within assigned domains. |
| **manager** | Can create and share dashboards. Cannot perform admin tasks. |
| **viewer** | Read-only access to assigned dashboards. |

### Role Permissions

| Capability | super-admin | admin | manager | viewer |
|------------|:-----------:|:-----:|:-------:|:------:|
| View all domains (including archived) | Y | | | |
| Add/archive/restore/delete domains | Y | | | |
| Configure domain retention | Y | | | |
| Create users (any role) | Y | | | |
| Create users (up to admin) | Y | Y | | |
| Manage user domain assignments | Y | own domains | | |
| Reset user passwords | Y | subordinates | | |
| Delete users | Y | subordinates | | |
| Create API keys | Y | Y | | |
| View audit log | Y | | | |
| Create dashboards | Y | Y | Y | |
| Edit/delete own dashboards | Y | Y | Y | |
| Share dashboards | Y | Y | Y | |
| Transfer dashboard ownership | Y | Y | | |
| View assigned dashboards | Y | Y | Y | Y |
| Use search and filters | Y | Y | Y | Y |
| Submit reports (UI) | Y | Y | Y | |

### Domain Visibility

- **super-admin** sees all domains, including archived ones.
- **Other roles** see only domains explicitly assigned to them, and only if active (not archived).
- Dashboard access requires access to **all** domains in the dashboard's scope.

## Initial Setup Checklist

After first login as the bootstrap admin:

1. **Add domains** — Navigate to Domains and add your monitored domains (e.g., `example.com`).

2. **Create API keys** — Navigate to API Keys and create a key for report ingestion:
   - Assign the key to one or more domains
   - Grant the `reports:ingest` scope
   - Use Edit later if you need to change nickname, description, or scopes
   - Save the key secret (shown once)

3. **Create users** — Navigate to Users to create accounts for your team:
   - Choose appropriate roles
   - Optionally fill in full name and email
   - Assign domains as needed
   - Share the generated password with each user

4. **Configure report submission** — Set up your mail servers or scripts to send DMARC reports. See [Submitting Reports](SUBMITTING_REPORTS.md).

5. **Create dashboards** — Navigate to Dashboards to create views for monitoring your DMARC data.

## Application URLs

| Path | Description |
|------|-------------|
| `/` | Redirect to the signed-in landing route |
| `/login` | Login page |
| `/domains` | Domain management |
| `/dashboards` | Dashboard list |
| `/search` | Search aggregate/forensic reports |
| `/upload` | Upload reports via browser |
| `/ingest-jobs` | View ingest job history |
| `/users` | User management (admin+) |
| `/apikeys` | API key management (admin+) |
| `/audit` | Audit log (super-admin only) |

## Next Steps

- [Submitting Reports](SUBMITTING_REPORTS.md) — Learn how to send DMARC reports via API, CLI, or UI
- [API v1 Specification](API_V1.md) — Full API reference
- [Security and Audit](SECURITY_AND_AUDIT.md) — Security model and audit requirements

## Seeded E2E Browser Environment

Use this path when you want to run the `frontend-next` Playwright suite against a real seeded FastAPI backend instead of manually preparing data.

Required tools:

- Python 3.12+
- Node.js 22+
- project dependencies installed from `requirements.txt`
- frontend dependencies installed in `frontend-next`
- Playwright Chromium installed with `cd frontend-next && npx playwright install chromium`

Seed/reset commands:

```bash
# create or reseed the deterministic browser-test environment
python -m cli seed-e2e config.e2e.yaml

# remove the seeded database, archive data, and env summary files
python -m cli seed-e2e config.e2e.yaml --cleanup
```

The seed command writes:

- `.tmp/e2e/e2e.env` with the browser-harness environment variables
- `.tmp/e2e/seed-summary.json` with IDs, URLs, credentials, and API key details for debugging

Seeded credentials:

| Role | Username | Password |
|------|----------|----------|
| super-admin | `admin` | `seed-super-admin-pass` |
| admin | `e2e-admin` | `seed-admin-pass` |
| manager | `e2e-manager` | `seed-manager-pass` |
| viewer | `e2e-viewer` | `seed-viewer-pass` |

Seeded environment URLs:

- Frontend: `http://127.0.0.1:3001`
- API: `http://127.0.0.1:8001`

One-command local browser run:

```bash
cd frontend-next
npm run test:e2e:seeded
```

That command:

1. reseeds the SQLite database and archive storage using `config.e2e.yaml`
2. starts FastAPI and Next.js locally on dedicated test ports (`127.0.0.1:8001` and `127.0.0.1:3001`)
3. runs the full Playwright suite against the live services
4. cleans up the seeded environment afterward

If the run fails, inspect:

- `.tmp/e2e/backend.log`
- `.tmp/e2e/frontend.log`
- `.tmp/e2e/seed-summary.json`
- `frontend-next/playwright-report/`
- `frontend-next/test-results/`
