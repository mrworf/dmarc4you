"""Dedupe: (report_id, domain) already in aggregate_reports or forensic_reports."""

from backend.config.schema import Config
from backend.storage.sqlite import get_connection


def is_duplicate(config: Config, report_id: str, domain: str) -> bool:
    """Return True if (report_id, domain) already exists in aggregate_reports."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT 1 FROM aggregate_reports WHERE report_id = ? AND domain = ?",
            (report_id, domain),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def is_forensic_duplicate(config: Config, report_id: str, domain: str) -> bool:
    """Return True if (report_id, domain) already exists in forensic_reports."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT 1 FROM forensic_reports WHERE report_id = ? AND domain = ?",
            (report_id, domain),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()
