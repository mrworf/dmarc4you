"""SQLite connection and migration runner."""

import sqlite3
from pathlib import Path

from backend.storage.interfaces import MigrationRunner


def get_connection(database_path: str) -> sqlite3.Connection:
    """Return a connection to the SQLite database. Creates parent dirs if needed."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def run_migrations(database_path: str, migrations_dir: str | Path | None = None) -> None:
    """Run all .sql migration files in order. Idempotent (uses IF NOT EXISTS where applicable)."""
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"
    migrations_dir = Path(migrations_dir)
    if not migrations_dir.is_dir():
        return
    conn = get_connection(database_path)
    try:
        conn.executescript(
            "CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY);"
        )
        for f in sorted(migrations_dir.glob("*.sql")):
            name = f.name
            cur = conn.execute("SELECT 1 FROM _migrations WHERE name = ?", (name,))
            if cur.fetchone():
                continue
            sql = f.read_text()
            conn.executescript(sql)
            conn.execute("INSERT INTO _migrations (name) VALUES (?)", (name,))
        conn.commit()
    finally:
        conn.close()


class SQLiteMigrationRunner:
    """MigrationRunner implementation for SQLite."""

    def run_migrations(self, database_path: str) -> None:
        run_migrations(database_path)
