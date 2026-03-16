"""Minimal config schema for bootstrap and frontend split-origin deployment."""

from dataclasses import dataclass
from typing import Literal

LogLevel = Literal["VERBOSE", "INFO", "WARN", "ERROR"]
SameSitePolicy = Literal["lax", "strict", "none"]


@dataclass(frozen=True)
class Config:
    """Application config. Required fields for bootstrap + auth slice."""

    database_path: str
    log_level: LogLevel
    session_secret: str
    session_cookie_name: str
    session_max_age_days: int
    csrf_cookie_name: str = "dmarc_csrf"
    session_cookie_secure: bool = False
    session_cookie_same_site: SameSitePolicy = "lax"
    csrf_cookie_same_site: SameSitePolicy = "strict"
    frontend_public_origin: str | None = None
    api_public_url: str | None = None
    cors_allowed_origins: tuple[str, ...] = ()
    archive_storage_path: str | None = None
