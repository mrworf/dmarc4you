"""Tests for reverse DNS fallback behavior."""

import socket

from backend.ingest import dns_resolver


def test_resolve_ip_cached_falls_back_to_socket_when_dns_lookup_fails(monkeypatch) -> None:
    dns_resolver.resolve_ip_cached.cache_clear()

    class BrokenResolver:
        def __init__(self, *args, **kwargs):
            self.nameservers = []
            self.timeout = 0.0
            self.lifetime = 0.0

        def resolve(self, *args, **kwargs):
            raise RuntimeError("dnspython lookup failed")

    fake_dns = type(
        "FakeDns",
        (),
        {
            "resolver": type("ResolverModule", (), {"Resolver": BrokenResolver}),
            "reversename": type("ReverseNameModule", (), {"from_address": staticmethod(lambda value: f"{value}.in-addr.arpa")}),
        },
    )

    monkeypatch.setattr(dns_resolver, "dns", fake_dns)
    monkeypatch.setattr(socket, "gethostbyaddr", lambda value: ("mout.perfora.net", [], [value]))

    hostname, domain = dns_resolver.resolve_ip_cached("74.208.4.196", tuple(), 1.0)

    assert hostname == "mout.perfora.net"
    assert domain == "perfora.net"
