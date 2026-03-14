# Plan: bootstrap the DMARC Analyzer repository

## Goal

Create the minimal repo skeleton and foundations required to begin building vertical slices safely.

## Deliverables

- root repo structure (`backend/`, `frontend/`, `cli/`, `shared/`, `tests/`, `docs/`, `.cursor/`)
- config loader and YAML schema stub
- logging bootstrap with `VERBOSE|INFO|WARN|ERROR` user-facing settings
- SQLite connection bootstrap + migrations scaffold
- bootstrap `admin` super-admin creation on first run
- empty versioned API app with `/api/v1/health`
- starter test harness

## Files likely involved

- `backend/app.py`
- `backend/config/*`
- `backend/storage/interfaces.py`
- `backend/storage/sqlite/*`
- `backend/auth/*`
- `tests/*`
- `docker/Dockerfile`
- `docker/docker-compose.example.yml`

## Risks

- over-designing storage abstractions too early
- mixing auth bootstrap with full user-management logic
- choosing a frontend build path before it is needed

## Acceptance criteria

- app starts
- migrations run
- bootstrap `admin` user is created when DB is empty
- generated password prints once to console
- `/api/v1/health` returns success
- tests can run in CI/local env
