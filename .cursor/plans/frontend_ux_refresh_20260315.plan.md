# Frontend UX Refresh Plan

## Scope

Implement the approved `frontend-next` UX refresh without changing backend behavior or API contracts.

## Files to change

- shared shell and styling in `frontend-next/app/globals.css` and `frontend-next/components/app-shell.tsx`
- shared overlays/dialogs in `frontend-next/components/`
- primary admin surfaces in `frontend-next/app/` and `frontend-next/components/`
- route coverage in `frontend-next/e2e/`
- migration notes in `docs/FRONTEND_MIGRATION.md`

## Approach

1. Replace migration/debug framing with task-focused copy and a stable shell.
2. Move major create/edit/import flows into shared slideovers and destructive actions into confirm dialogs.
3. Restore missing domain lifecycle parity in `frontend-next`.
4. Update browser selectors and add domain lifecycle coverage so the refreshed workflows stay protected.
