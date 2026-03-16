"""Offline GeoIP helpers for country-level enrichment."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
from pathlib import Path

from backend.config.schema import Config

try:
    import maxminddb
except ImportError:  # pragma: no cover - optional dependency during local development
    maxminddb = None


@dataclass(frozen=True)
class GeoIpResult:
    country_code: str | None
    country_name: str | None
    provider: str | None


class GeoIpProvider:
    provider_name = "none"

    def lookup_country(self, ip_text: str | None) -> GeoIpResult:
        return GeoIpResult(country_code=None, country_name=None, provider=None)


class NullGeoIpProvider(GeoIpProvider):
    provider_name = "none"


class MmdbGeoIpProvider(GeoIpProvider):
    provider_name = "mmdb"

    def __init__(self, database_path: str | None, provider_name: str) -> None:
        self.database_path = database_path
        self.provider_name = provider_name
        self._reader = None

    def _get_reader(self):
        if self._reader is not None:
            return self._reader
        if not self.database_path or maxminddb is None:
            return None
        path = Path(self.database_path)
        if not path.exists():
            return None
        self._reader = maxminddb.open_database(str(path))
        return self._reader

    def lookup_country(self, ip_text: str | None) -> GeoIpResult:
        value = (ip_text or "").strip()
        if not value:
            return GeoIpResult(None, None, None)
        try:
            ipaddress.ip_address(value)
        except ValueError:
            return GeoIpResult(None, None, None)
        reader = self._get_reader()
        if reader is None:
            return GeoIpResult(None, None, None)
        try:
            record = reader.get(value) or {}
        except Exception:
            return GeoIpResult(None, None, None)
        country = record.get("country") or {}
        iso_code = country.get("iso_code")
        names = country.get("names") or {}
        country_name = names.get("en") or country.get("name")
        return GeoIpResult(
            country_code=str(iso_code) if iso_code else None,
            country_name=str(country_name) if country_name else None,
            provider=self.provider_name if (iso_code or country_name) else None,
        )


class DbIpLiteCountryProvider(MmdbGeoIpProvider):
    def __init__(self, database_path: str | None) -> None:
        super().__init__(database_path, "dbip-lite-country")


class MaxMindGeoLite2CountryProvider(MmdbGeoIpProvider):
    def __init__(self, database_path: str | None) -> None:
        super().__init__(database_path, "maxmind-geolite2-country")


def build_geoip_provider(config: Config) -> GeoIpProvider:
    if config.geoip_provider == "dbip-lite-country":
        return DbIpLiteCountryProvider(config.geoip_database_path)
    if config.geoip_provider == "maxmind-geolite2-country":
        return MaxMindGeoLite2CountryProvider(config.geoip_database_path)
    return NullGeoIpProvider()
