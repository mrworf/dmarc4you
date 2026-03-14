# Repository Structure

## Proposed layout

```text
.
├── AGENTS.md
├── README.md
├── backend/
│   ├── app.py
│   ├── api/
│   │   ├── handlers/
│   │   ├── middleware/
│   │   └── schemas/
│   ├── auth/
│   ├── archive/
│   ├── dashboards/
│   ├── domains/
│   ├── ingest/
│   ├── jobs/
│   ├── policies/
│   ├── search/
│   ├── services/
│   ├── storage/
│   │   ├── interfaces.py
│   │   └── sqlite/
│   └── utils/
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   │   ├── api/
│   │   ├── router/
│   │   ├── state/
│   │   ├── views/
│   │   ├── widgets/
│   │   └── components/
│   └── assets/
├── cli/
│   ├── dmarc_submit.py
│   └── dmarc_admin.py
├── shared/
│   ├── schemas/
│   └── constants/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.example.yml
├── scripts/
└── .cursor/
    ├── rules/
    ├── commands/
    └── plans/
```

## Directory responsibilities

### `backend/api/`
HTTP transport, request/response schemas, middleware, versioned routes. Keep handlers thin.

### `backend/services/`
Application services coordinating repositories, policies, and domain logic.

### `backend/policies/`
Pure or near-pure authorization and business rule checks for roles, dashboard assignment, archive-state gating, and ownership transitions.

### `backend/ingest/`
Content detection, decompression, MIME parsing, XML parsing, normalization, dedupe, and per-report ingest orchestration.

### `backend/jobs/`
Job submission, claim/resume logic, state transitions, checkpointing, and scheduler.

### `backend/storage/`
Interfaces and SQLite implementation. No business rules here.

### `frontend/`
Plain JS SPA code. Keep route-level views separate from reusable widgets/components.

### `cli/`
- `dmarc_submit.py`: API-key-authenticated report submission
- `dmarc_admin.py`: local-only maintenance operations like break-glass recovery

## Naming guidance

- use descriptive module names over short abbreviations
- keep domain-specific code grouped by feature
- avoid a catch-all `utils` unless a helper is genuinely cross-cutting
- prefer one service per cohesive business responsibility instead of a single giant service file
