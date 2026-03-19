"""Config loader and schema."""

from pathlib import Path
import os

from backend.config.schema import Config, GeoIpProvider, LogLevel

_LOG_LEVELS: set[str] = {"VERBOSE", "INFO", "WARN", "ERROR"}
_SAME_SITE_POLICIES: set[str] = {"lax", "strict", "none"}
_GEOIP_PROVIDERS: set[str] = {"none", "dbip-lite-country", "maxmind-geolite2-country"}
_DEFAULT_DB = "data/dmarc.db"


def _parse_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_origins(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return tuple(part for part in parts if part)
    if isinstance(value, (list, tuple)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return ()


def _parse_float(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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
    session_cookie_secure = _parse_bool(
        auth.get("session_cookie_secure") or os.environ.get("DMARC_SESSION_COOKIE_SECURE"),
        False,
    )
    session_cookie_same_site = str(
        auth.get("session_cookie_same_site") or os.environ.get("DMARC_SESSION_COOKIE_SAME_SITE") or "lax"
    ).lower()
    csrf_cookie_same_site = str(
        auth.get("csrf_cookie_same_site") or os.environ.get("DMARC_CSRF_COOKIE_SAME_SITE") or "strict"
    ).lower()
    if session_cookie_same_site not in _SAME_SITE_POLICIES:
        raise ValueError(
            f"Invalid session_cookie_same_site: {session_cookie_same_site}. "
            f"Must be one of {sorted(_SAME_SITE_POLICIES)}"
        )
    if csrf_cookie_same_site not in _SAME_SITE_POLICIES:
        raise ValueError(
            f"Invalid csrf_cookie_same_site: {csrf_cookie_same_site}. "
            f"Must be one of {sorted(_SAME_SITE_POLICIES)}"
        )

    frontend_public_origin = (
        data.get("frontend", {}).get("public_origin")
        or os.environ.get("DMARC_FRONTEND_PUBLIC_ORIGIN")
        or None
    )
    api_public_url = data.get("api", {}).get("public_url") or os.environ.get("DMARC_API_PUBLIC_URL") or None
    cors_allowed_origins = _parse_origins(
        data.get("cors", {}).get("allowed_origins") or os.environ.get("DMARC_CORS_ALLOWED_ORIGINS")
    )
    if frontend_public_origin and frontend_public_origin not in cors_allowed_origins:
        cors_allowed_origins = cors_allowed_origins + (frontend_public_origin,)

    archive_storage_path = data.get("archive", {}).get("storage_path") or os.environ.get("DMARC_ARCHIVE_STORAGE_PATH") or None
    dns_nameservers = _parse_origins(
        data.get("dns", {}).get("nameservers") or os.environ.get("DMARC_DNS_NAMESERVERS")
    )
    dns_timeout_seconds = _parse_float(
        data.get("dns", {}).get("timeout_seconds") or os.environ.get("DMARC_DNS_TIMEOUT_SECONDS"),
        5.0,
    )
    dns_monitor_default_interval_seconds = _parse_int(
        data.get("dns", {}).get("monitor_default_interval_seconds")
        or os.environ.get("DMARC_DNS_MONITOR_DEFAULT_INTERVAL_SECONDS"),
        300,
    )
    dns_monitor_default_interval_seconds = min(max(60, dns_monitor_default_interval_seconds), 3600)
    geoip_provider_raw = (
        data.get("geoip", {}).get("provider")
        or os.environ.get("DMARC_GEOIP_PROVIDER")
        or "none"
    )
    geoip_provider = str(geoip_provider_raw).strip().lower()
    if geoip_provider not in _GEOIP_PROVIDERS:
        raise ValueError(
            f"Invalid geoip.provider: {geoip_provider_raw}. Must be one of {sorted(_GEOIP_PROVIDERS)}"
        )
    geoip_database_path = (
        data.get("geoip", {}).get("database_path")
        or os.environ.get("DMARC_GEOIP_DATABASE_PATH")
        or None
    )

    return Config(
        database_path=str(database_path),
        log_level=log_level,  # type: ignore[arg-type]
        session_secret=str(session_secret),
        session_cookie_name=str(session_cookie_name),
        session_max_age_days=session_max_age_days,
        session_cookie_secure=session_cookie_secure,
        session_cookie_same_site=session_cookie_same_site,  # type: ignore[arg-type]
        csrf_cookie_same_site=csrf_cookie_same_site,  # type: ignore[arg-type]
        frontend_public_origin=str(frontend_public_origin) if frontend_public_origin else None,
        api_public_url=str(api_public_url) if api_public_url else None,
        cors_allowed_origins=cors_allowed_origins,
        archive_storage_path=archive_storage_path,
        dns_nameservers=dns_nameservers,
        dns_timeout_seconds=dns_timeout_seconds,
        dns_monitor_default_interval_seconds=dns_monitor_default_interval_seconds,
        geoip_provider=geoip_provider,  # type: ignore[arg-type]
        geoip_database_path=str(geoip_database_path) if geoip_database_path else None,
    )
