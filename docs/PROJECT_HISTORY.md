# Project History

This document keeps implementation-history and migration-oriented references that are useful for maintainers but not necessary in the main `README.md`.

## Frontend migration references

The repository completed the frontend move from the retired backend-served SPA to the current Next.js UI. Historical migration notes remain in:

- [Frontend Migration](docs/FRONTEND_MIGRATION.md)
- [Frontend Migration Slices](docs/FRONTEND_MIGRATION_SLICES.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)

## Seeded browser regression notes

The seeded browser harness and frontend cutover notes remain documented in:

- [Getting Started](docs/GETTING_STARTED.md#seeded-e2e-browser-environment)
- [Frontend Migration](docs/FRONTEND_MIGRATION.md)

## Why this file exists

The top-level `README.md` is now focused on users and operators:

- what the application does
- how to install and run it
- where to find operational documentation

Longer implementation history and migration-specific material lives here or in the linked docs above.
