# Architecture

## Top-level architecture

```text
CLI / Web UI / External API client
            │
            ▼
      REST API layer (/api/v1)
            │
            ├── session auth
            ├── API key auth
            ├── request validation
            └── job submission
            │
            ▼
      Background job runner (in-process)
            │
            ├── ingest pipeline
            ├── archive storage adapter
            ├── domain/policy checks
            ├── dedupe
            └── persistence
            │
            ▼
        Service layer
            │
            ├── user/domain services
            ├── dashboard services
            ├── API key services
            ├── search services
            ├── audit services
            └── archival/retention services
            │
            ▼
      Storage interfaces
            │
            ├── SQLite adapter (v1)
            └── future DB adapters
```

## Architectural principles

1. **Thin edges, strong core.** API handlers, CLI entrypoints, and job workers should call services and policies rather than holding business rules.
2. **Interface-first persistence.** Business logic should depend on repository/storage interfaces, not directly on SQLite SQL helpers.
3. **Policy isolation.** RBAC, domain scoping, dashboard ownership, and archive-state checks belong in explicit policy modules/services.
4. **Resumable jobs.** Job state and per-report progress must be persisted so restart recovery is deterministic.
5. **Backend-enforced security.** Frontend visibility is advisory only; the backend is the source of truth for access control.

## Main components

### Backend API layer

Responsibilities:

- serve `/api/v1/...`
- authenticate sessions and API keys
- validate request shapes
- submit ingest jobs
- expose query/search/dashboard/admin endpoints

### Background job runner

Responsibilities:

- pick queued jobs
- transition job states
- persist report-by-report outcomes
- resume safe work after restart

The runner is in-process in v1 but must be separable later.

### Ingest pipeline

Pipeline stages:

1. content classification
2. decompression
3. MIME/email attachment extraction if needed
4. report type detection
5. XML parsing and normalization
6. domain/config/archive authorization checks
7. dedupe
8. archival storage (if enabled)
9. persistence
10. audit/logging

### Search/query layer

Responsibilities:

- structured queries over normalized data
- free-text search over curated indexed fields
- dashboard widget query execution
- pagination, sorting, include/exclude filters

### Dashboard subsystem

Responsibilities:

- dashboard CRUD
- ownership and sharing
- domain scope validation
- YAML import/export with domain remapping
- widget/query definitions

### Domain lifecycle subsystem

Responsibilities:

- archive/restore/delete
- dormant dashboard behavior
- restore prior assignments and key bindings
- retention schedule management
- pause/unpause logic with reason tracking

## Abstraction boundaries

### Auth abstraction

- local auth provider in v1
- future OIDC/LDAP/SSO provider later

### Storage abstraction

- repository interfaces for users, domains, dashboards, jobs, reports, keys, audit
- SQLite implementation in v1

### Archive storage abstraction

- local filesystem implementation in v1
- future S3/object store adapters later

### Job abstraction

- in-process scheduler/runner in v1
- future external worker/process later

## Failure handling

- Per-report failure must not fail an entire batch unless no report can be accepted.
- Domain authorization failures must be tracked at report granularity.
- External callers must not receive more detail than the product spec allows.
- Internal logs and audit records must preserve detailed reasons.

## Startup behavior

On startup:

1. load config
2. initialize logging
3. run migrations
4. perform bootstrap user creation if no users exist
5. recover unfinished jobs from persistence
6. resume eligible jobs safely
7. start API server and retention scheduler
