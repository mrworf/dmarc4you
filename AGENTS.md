# AGENTS.md

This repository builds a **single-organization, self-hosted DMARC analysis platform** with a Python backend, a Next.js frontend, SQLite in v1, versioned REST API endpoints, background-job-based ingestion, and strong RBAC/domain scoping.

## How to work in this repo

1. **Read before editing.** For any non-trivial task, read `README.md`, the relevant operator-facing guide in `docs/`, and this file before changing code.
2. **Plan first for multi-file work.** Prefer a small written plan before coding. Save plans under `.cursor/plans/` when they represent a real implementation step.
3. **Build thin vertical slices.** Prefer end-to-end increments that include schema, backend service, API, tests, and minimal UI where applicable.
4. **Do not invent policy.** If a requirement is ambiguous, preserve existing behavior and add a short TODO note instead of silently changing security or RBAC rules.
5. **Keep transport thin.** HTTP handlers, CLI entrypoints, and background job runners should call services; business rules belong in services/policies, not controllers.
6. **Preserve abstractions.** SQLite, archive storage, authentication, and job execution must stay behind interfaces so later backends are possible.
7. **Treat access control as a first-class invariant.** Domain scoping, ownership checks, API key scope checks, archive-state checks, and audit logging are not optional.
8. **Keep docs in sync.** If a change alters API shapes, domain lifecycle behavior, security assumptions, or repo structure, update the matching `docs/*.md` file in the same change.
9. **Prefer explicit tests.** New behavior should come with targeted tests, especially for ingest parsing, domain authorization, RBAC, archival, retention, and dashboard ownership transitions.
10. **Avoid unnecessary dependencies.** Default to the Python standard library and small well-justified libraries. Do not add frameworks or build tools without a concrete reason.

## Core product invariants

- This is **single-org only** in v1.
- `super-admin` always has access to **all** domains.
- Only `super-admin` can add domains, archive/restore/delete domains, change an admin's domain assignments, or create another `super-admin`.
- Admins can create users up to role `admin`, but cannot grant `super-admin` and cannot demote another admin.
- Managers and viewers can be assigned subsets of domains; dashboard access always requires access to **all** dashboard domains.
- API keys are **not tied to users**. They belong to one or more domains and have endpoint scopes.
- Archived domains are non-ingestable and non-visible to non-super-admins.
- Ingest is asynchronous via background jobs and must resume safely after restart.
- Dashboard YAML import/export is portable; import always uses domain remapping.

## Preferred repo layout

```text
backend/
  api/
  auth/
  jobs/
  ingest/
  archive/
  services/
  policies/
  storage/
frontend/
cli/
shared/
tests/
docs/
.cursor/
```

## Validation expectations

Before declaring work done, run the smallest relevant verification set and state what was run. Typical checks include:

- unit tests for touched services/policies/parsers
- API tests for touched endpoints
- UI smoke checks for touched views/routes
- lint/type checks if configured
- migration checks for schema changes

If a required validation step cannot be run, say so clearly and explain why.

## Editing guidance

- Make the smallest coherent change set.
- Keep function and module names boring and descriptive.
- Prefer typed Python and explicit DTOs/schemas for API edges.
- Prefer deterministic ownership/retention logic over implicit behavior.
- Do not leak sensitive reasons to external API callers when the product spec says to keep that detail in backend logs only.

## Cursor Cloud specific instructions

If running in a cloud/remote agent environment:

- read this file and only the relevant docs for the current slice; avoid pulling the whole repo into context at once
- favor reproducible commands and deterministic tests
- do not assume local secrets or local archive paths exist unless explicitly configured
- document any environment assumptions in the plan before implementation
