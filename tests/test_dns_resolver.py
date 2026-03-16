from types import SimpleNamespace

from backend.config.schema import Config
from backend.ingest import dns_resolver


class _FakeAnswer:
    def __str__(self) -> str:
        return "Mail.EXAMPLE.net."


class _FakeResolver:
    def __init__(self, configure: bool = True) -> None:
        self.configure = configure
        self.nameservers = []
        self.timeout = 0.0
        self.lifetime = 0.0

    def resolve(self, reverse_name: str, record_type: str):
        assert reverse_name == "rev:192.0.2.1"
        assert record_type == "PTR"
        return [_FakeAnswer()]


def test_resolve_ip_uses_custom_nameserver_configuration(monkeypatch) -> None:
    dns_resolver.resolve_ip_cached.cache_clear()
    fake_dns = SimpleNamespace(
        resolver=SimpleNamespace(Resolver=_FakeResolver),
        reversename=SimpleNamespace(from_address=lambda value: f"rev:{value}"),
    )
    monkeypatch.setattr(dns_resolver, "dns", fake_dns)
    config = Config(
        database_path=":memory:",
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
        dns_nameservers=("1.1.1.1",),
        dns_timeout_seconds=2.5,
    )

    hostname, grouped = dns_resolver.resolve_ip(config, "192.0.2.1")

    assert hostname == "mail.example.net"
    assert grouped == "example.net"


def test_resolve_ip_failure_is_non_blocking(monkeypatch) -> None:
    dns_resolver.resolve_ip_cached.cache_clear()

    class _RaisingResolver(_FakeResolver):
        def resolve(self, reverse_name: str, record_type: str):
            raise RuntimeError("boom")

    fake_dns = SimpleNamespace(
        resolver=SimpleNamespace(Resolver=_RaisingResolver),
        reversename=SimpleNamespace(from_address=lambda value: f"rev:{value}"),
    )
    monkeypatch.setattr(dns_resolver, "dns", fake_dns)
    config = Config(
        database_path=":memory:",
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )

    assert dns_resolver.resolve_ip(config, "192.0.2.1") == (None, None)
