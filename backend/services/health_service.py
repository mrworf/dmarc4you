"""Health and readiness checks."""

from backend.config.schema import Config
from backend.storage.sqlite import get_connection


def live_status() -> dict[str, str]:
    """Return process liveness details."""
    return {"status": "ok", "service": "api"}


def readiness_status(config: Config) -> dict[str, object]:
    """Return basic readiness checks for DB-backed API serving."""
    checks: list[dict[str, str]] = []
    try:
        conn = get_connection(config.database_path)
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
        checks.append({"name": "database", "status": "ok"})
    except Exception:
        checks.append({"name": "database", "status": "error"})
        return {"status": "error", "service": "api", "checks": checks}
    return {"status": "ok", "service": "api", "checks": checks}
