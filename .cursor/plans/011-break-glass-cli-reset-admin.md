# Plan: Break-glass CLI — reset admin password (Phase 6)

## Goal

Implement a **local admin CLI** command that resets the bootstrap `admin` user’s password and prints the new password to stdout. Satisfies PRODUCT: “Break-glass recovery must be available locally via an admin CLI command.” No API, no new tables; uses existing config, storage, and password hashing.

## Why this slice

- Phase 6 calls for “break-glass local admin CLI”. Slices 1–10 are done. This is a small, self-contained slice: one CLI command, config + DB + auth helpers only.
- Enables recovery when the admin password is lost; must be run with access to the server and config/DB (local only).

## Scope (in)

- **CLI package**: Add `cli/` at repo root (or under `backend/` if preferred; AGENTS layout shows `cli/` at root). Entrypoint runnable as `python -m cli reset-admin-password` (or `python -m backend.cli` with subcommand). Command behavior:
  1. Load config via existing `load_config()` (uses `config.yaml` or `DMARC_CONFIG` or env).
  2. Run migrations on `config.database_path`.
  3. Find user with `username = 'admin'` (use same constant as bootstrap: `BOOTSTRAP_USERNAME`). If none, exit with non-zero and message “Admin user not found.”
  4. Generate new password (`generate_random_password`), hash it (`hash_password`), update `users SET password_hash = ? WHERE username = 'admin'`, commit.
  5. Print the new password to stdout (and optionally “Password reset for admin.”) so the operator can use it to log in.
- **Docs**: Short note in README or `docs/` (e.g. “Local recovery: run `python -m cli reset-admin-password` with config/DB available; prints new admin password.”). Mention that this is for break-glass only and requires local access.
- **Tests**: One test: temp DB, bootstrap admin (or insert admin user), run CLI command (subprocess or invoke programmatically), verify new password works (e.g. login via auth_service or API). Optionally verify old password no longer works.

## Scope (out)

- Other CLI commands (e.g. create-user, list-users).
- Interactive prompts; config path as CLI arg is optional (can rely on env/config file only in this slice).
- Changing username or creating admin if missing (only reset existing admin).

---

## Files to create or edit

### New

| Path | Action |
|------|--------|
| `cli/__init__.py` | Empty or minimal package. |
| `cli/__main__.py` | Parse argv for subcommand; dispatch to `reset_admin_password`. |
| `cli/commands.py` (or `cli/reset_admin.py`) | `reset_admin_password()`: load config, run migrations, find admin user, update password, print. Reuse `backend.config.load_config`, `backend.storage.sqlite.run_migrations`, `get_connection`, `backend.auth.password.hash_password`, `generate_random_password`, `backend.auth.bootstrap.BOOTSTRAP_USERNAME`. |

### Edit

| Path | Action |
|------|--------|
| `README.md` or `docs/` | Add “Break-glass recovery” section: run `python -m cli reset-admin-password` (with config/DB in place); prints new admin password. |

### Tests

| Path | Action |
|------|--------|
| `tests/` (e.g. `tests/test_cli_reset_admin.py` or under `tests/integration/`) | Test: temp DB, ensure admin exists (bootstrap or insert), run reset-admin-password (subprocess or direct call), verify login with new password succeeds (e.g. auth_service or POST /auth/login). |

---

## Acceptance criteria

1. Running `python -m cli reset-admin-password` (with valid config and DB containing admin user) prints a new password to stdout and the admin user’s stored password_hash is updated.
2. Logging in via the API with username `admin` and the printed password succeeds; old password fails.
3. If no user with username `admin` exists, the command exits with non-zero and a clear message; no password is printed.
4. Config is loaded via existing mechanism (config file or `DMARC_CONFIG` / env); no hardcoded DB path.

---

## Tests and validation

1. **Test**: Temp DB, bootstrap admin, capture stdout from reset-admin-password, parse new password, call auth login (or auth_service) with new password → success; with old password → failure. No admin user → exit non-zero.
2. **Manual**: Run CLI against a real config/DB, log in via UI or curl with new password.
3. **Run**: `pytest tests/` passes.

---

## Implementation notes

- Reuse `BOOTSTRAP_USERNAME` from `backend.auth.bootstrap` to avoid divergence. Use `backend.storage.sqlite.get_connection(config.database_path)` (or the same pattern as elsewhere: `get_connection` may take path from config).
- Print only the password (or one line like “New password: <password>”) so it can be scripted; avoid extra noise.
- Consider logging to stderr only so stdout is just the password for piping; optional in this slice.
