Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/API_V1.md`, `docs/DATA_MODEL.md`, and `docs/SECURITY_AND_AUDIT.md`.

Then implement the backend slice requested in the current chat while following these rules:

- keep handlers thin and move domain logic into services/policies
- preserve storage/auth/archive abstractions
- add focused tests for the new behavior
- update matching docs if API shapes or invariants change
- finish by summarizing files changed and validations run

Use any extra text after this command as the target backend slice or feature name.
