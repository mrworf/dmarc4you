"""Config loader and schema."""

from pathlib import Path
import os

from backend.config.schema import Config, LogLevel

_LOG_LEVELS: set[str] = {"VERBOSE", "INFO", "WARN", "ERROR"}
_DEFAULT_DB = "data/dmarc.db"


def _resolve_config_path(config_path: str | Path | None) -> Path | None:
    if config_path is not None:
        return Path(config_path)
    env_path = os.environ.get("DMARC_CONFIG")
    if env_path:
        return Path(env_path)
    return Path("config.yaml")


def load_config(config_path: str | Path | None = None) -> Config:
    """Load config from YAML file or env. Fail fast on missing required fields."""
    path = _resolve_config_path(config_path)
    if path and path.exists():
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {}

    database_path = data.get("database", {}).get("path") or os.environ.get("DMARC_DATABASE_PATH") or _DEFAULT_DB
    log_level_raw = (data.get("log", {}) or {}).get("level") or os.environ.get("DMARC_LOG_LEVEL") or "INFO"
    log_level = log_level_raw.upper()
    if log_level not in _LOG_LEVELS:
        raise ValueError(f"Invalid log_level: {log_level_raw}. Must be one of {sorted(_LOG_LEVELS)}")

    auth = data.get("auth") or data.get("session") or {}
    session_secret = auth.get("session_secret") or os.environ.get("DMARC_SESSION_SECRET") or "change-me-in-production"
    session_cookie_name = auth.get("session_cookie_name") or os.environ.get("DMARC_SESSION_COOKIE") or "dmarc_session"
    session_max_age_days = int(auth.get("session_max_age_days") or os.environ.get("DMARC_SESSION_MAX_AGE_DAYS") or 7)

    archive_storage_path = data.get("archive", {}).get("storage_path") or os.environ.get("DMARC_ARCHIVE_STORAGE_PATH") or None

    return Config(
        database_path=str(database_path),
        log_level=log_level,  # type: ignore[arg-type]
        session_secret=str(session_secret),
        session_cookie_name=str(session_cookie_name),
        session_max_age_days=session_max_age_days,
        archive_storage_path=archive_storage_path,
    )
