from backend.config.schema import Config
from backend.ingest import geoip


class _FakeReader:
    def get(self, ip_text: str):
        assert ip_text == "192.0.2.10"
        return {
            "country": {
                "iso_code": "US",
                "names": {"en": "United States"},
            }
        }


def test_build_geoip_provider_defaults_to_null() -> None:
    config = Config(
        database_path=":memory:",
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )
    provider = geoip.build_geoip_provider(config)
    result = provider.lookup_country("192.0.2.10")
    assert result.country_code is None
    assert result.provider is None


def test_mmdb_provider_reads_country(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "GeoIP.mmdb"
    database_path.write_bytes(b"stub")

    class _FakeModule:
        @staticmethod
        def open_database(path: str):
            assert path == str(database_path)
            return _FakeReader()

    monkeypatch.setattr(geoip, "maxminddb", _FakeModule())
    config = Config(
        database_path=":memory:",
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
        geoip_provider="dbip-lite-country",
        geoip_database_path=str(database_path),
    )

    provider = geoip.build_geoip_provider(config)
    result = provider.lookup_country("192.0.2.10")

    assert result.country_code == "US"
    assert result.country_name == "United States"
    assert result.provider == "dbip-lite-country"
