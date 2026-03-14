"""Minimal config schema for bootstrap."""

from dataclasses import dataclass
from typing import Literal

LogLevel = Literal["VERBOSE", "INFO", "WARN", "ERROR"]


@dataclass(frozen=True)
class Config:
    """Application config. Required fields for bootstrap + auth slice."""

    database_path: str
    log_level: LogLevel
    session_secret: str
    session_cookie_name: str
    session_max_age_days: int
    csrf_cookie_name: str = "dmarc_csrf"
    archive_storage_path: str | None = None
