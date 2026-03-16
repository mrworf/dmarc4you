# Frontend UX Polish Plan

- add overlay-local error rendering to shared slideover and confirm dialog components
- convert remaining non-destructive overlay actions to real form submission so Enter works consistently
- replace the last browser `window.confirm` in dashboard detail with the shared confirm dialog
- redesign search into a results-first layout with a compact toolbar, advanced-filters drawer, removable applied-filter chips, and cell-level quick-filter actions
- update Playwright coverage for modal-local errors, Enter-to-submit behavior, and the new search flow
