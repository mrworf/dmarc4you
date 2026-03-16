# Frontend Migration Wrap-Up Plan

## Goal

Close the remaining migration-hardening work by making the browser harness runnable against a deterministic seeded FastAPI backend locally and in CI.

## Scope

- add a dedicated E2E seed command and config path
- add one-command local seeded browser execution
- make Playwright use deterministic seeded credentials/data by default
- add CI seeded-browser coverage with artifacts on failure
- rewrite the migration docs around the seeded path instead of manual env preparation

## Files

- `cli/e2e_seed.py`
- `cli/__main__.py`
- `config.e2e.yaml`
- `scripts/run_seeded_e2e.sh`
- `frontend-next/package.json`
- `frontend-next/e2e/auth.ts`
- `.gitignore`
- `README.md`
- `docs/GETTING_STARTED.md`
- `docs/FRONTEND_MIGRATION.md`
- `.github/workflows/frontend-seeded-e2e.yml`
