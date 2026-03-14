Perform a targeted security and invariants review for the current diff or requested feature.

Checklist:

1. Read `AGENTS.md` and `docs/SECURITY_AND_AUDIT.md`.
2. Check RBAC and domain scoping.
3. Check archived-domain behavior.
4. Check API key scope/domain enforcement.
5. Check whether sensitive internal reasons are leaked to external callers.
6. Check audit/log coverage for the new behavior.
7. Report findings grouped as:
   - must fix
   - should fix
   - looks good

Do not make code changes unless explicitly asked.
