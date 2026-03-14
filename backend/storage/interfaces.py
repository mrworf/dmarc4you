"""Minimal storage interfaces for bootstrap: migrations and connection."""

from typing import Protocol


class MigrationRunner(Protocol):
    """Runs migrations against a database."""

    def run_migrations(self, database_path: str) -> None:
        """Apply all pending migrations. Idempotent."""
        ...


class ConnectionFactory(Protocol):
    """Provides a database connection (e.g. for bootstrap or queries)."""

    def get_connection(self, database_path: str):
        """Return a connection object (e.g. sqlite3.Connection)."""
        ...
