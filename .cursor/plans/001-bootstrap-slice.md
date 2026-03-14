# Plan: Bootstrap slice (Phase 1 — first vertical slice)

## Goal

Implement the smallest end-to-end vertical slice that establishes the skeleton: config, logging, SQLite + migrations, bootstrap super-admin creation on first run, and a versioned health endpoint. No auth flows or domain CRUD yet.

## Why this slice

- Repo currently has only docs and `.cursor` assets; no backend/frontend/tests code.
- Bootstrap is slice 1 in `docs/IMPLEMENTATION_PLAN.md` and is required before Auth and Domain slices.
- Delivers: runnable app, DB init, one API route, bootstrap admin, test harness.

## Scope (in)

- Repo directories: `backend/`, `frontend/`, `cli/`, `shared/`, `tests/`, `scripts/` (as per REPO_STRUCTURE).
- Config: load YAML (or env); minimal schema (e.g. `database.path`, `log.level`).
- Logging: bootstrap with user-facing levels (e.g. VERBOSE|INFO|WARN|ERROR).
- SQLite: connection helper, migrations scaffold, first migration (e.g. `users` table only for bootstrap).
- Bootstrap admin: on first run (no users), create super-admin `admin` with random password; print password once to console.
- API: `/api/v1/health` returns success (e.g. 200 + minimal JSON).
- Tests: harness (pytest), one integration test for health, one for bootstrap (first run creates admin; second run does not).

## Scope (out)

- Login/logout/session (Auth slice).
- Domain create/list or any domain UI (Domain slice).
- Docker/build (can be a follow-up; bootstrap only needs “app starts”).
- Full user or role management APIs.

---

## Files to create or edit

### Create

| Path | Purpose |
|------|--------|
| `backend/app.py` | ASGI app; mount `/api/v1`, register health route. |
| `backend/main.py` | Entry: load config, init logging, run migrations, run bootstrap admin, start server. |
| `backend/config/__init__.py` | Config loader (YAML or env); expose settings object. |
| `backend/config/schema.py` | Minimal schema (e.g. database path, log level). |
| `backend/storage/interfaces.py` | Minimal migration/connection interfaces. |
| `backend/storage/sqlite/__init__.py` | SQLite connection and migration runner. |
| `backend/storage/sqlite/migrations/001_users.sql` | Create `users` table (id, username, password_hash, role, created_at, created_by_user_id, last_login_at, disabled_at). |
| `backend/auth/bootstrap.py` | Ensure one super-admin exists; if DB has no users, create `admin` with random password and log/print it once. |
| `backend/auth/password.py` | Hash and verify passwords (Argon2id preferred per SECURITY_AND_AUDIT; bcrypt acceptable). |
| `backend/api/v1/__init__.py` | v1 router. |
| `backend/api/v1/handlers/health.py` | GET `/health` handler. |
| `backend/logging_config.py` | Configure logging (levels VERBOSE/INFO/WARN/ERROR). |
| `config.example.yaml` | Example config (database path, log level). |
| `requirements.txt` | Minimal deps: e.g. FastAPI/Starlette, uvicorn, PyYAML, argon2-cffi or bcrypt. |
| `tests/conftest.py` | Pytest fixtures: test client, temp DB, config. |
| `tests/integration/test_health.py` | GET `/api/v1/health` returns 200 and expected body. |
| `tests/integration/test_bootstrap.py` | First run creates admin; second run does not create duplicate; password is hashed. |

### Edit

| Path | Change |
|------|--------|
| `docs/IMPLEMENTATION_PLAN.md` | Mark bootstrap slice done (optional short note). |

---

## Acceptance criteria

1. **App starts** — `python -m backend.main` (or equivalent) starts the HTTP server without error.
2. **Config** — App reads config from YAML or env; missing required fields fail fast with a clear message.
3. **Logging** — Log level can be set (e.g. INFO); logs appear on stdout.
4. **Migrations** — On startup, migrations run and create `users` table (and any dependency); re-run is idempotent.
5. **Bootstrap admin** — When there are no users, one super-admin user is created with username `admin` and a random password; the password is printed once to the console (or logged at startup).
6. **No duplicate bootstrap** — If at least one user exists, bootstrap does not create another admin or overwrite.
7. **Health** — `GET /api/v1/health` returns 200 and a minimal success payload (e.g. `{"status": "ok"}` or similar).
8. **Tests** — `pytest tests/` runs; health and bootstrap tests pass.

---

## Tests and validation

1. **Unit / integration**
   - `tests/integration/test_health.py`: call `GET /api/v1/health`, assert status 200 and body indicates success.
   - `tests/integration/test_bootstrap.py`: start with empty DB → bootstrap runs → one user `admin` with role super-admin, password hashed; run bootstrap again → still one user; no plaintext password stored.
2. **Manual**
   - Start app with empty DB; confirm password printed once.
   - Start app again (DB already has admin); confirm no second password and no duplicate user.
   - `GET /api/v1/health` in browser or curl returns 200.
3. **Lint/format**
   - If the project adopts ruff/black/mypy, run them on new files (can be added in same or next slice).

---

## Risks and mitigations

- **Over-building storage** — Keep interfaces minimal (e.g. “run migrations”, “get connection”); avoid generic repository pattern until Domain slice.
- **Auth surface** — Bootstrap only creates the user and hashes password; no login/session in this slice.
- **Password visibility** — Product requires password printed once to console on first boot; document in OPERATION or README that this is one-time and should be changed via future break-glass CLI.

---

## Dependencies

- Python 3.10+.
- `SECURITY_AND_AUDIT.md`: password hashing Argon2id (or bcrypt); usernames `^[A-Za-z0-9_-]+$` (only relevant when we add login).
- `DATA_MODEL.md`: users table fields for first migration.
