"""Best-effort reverse DNS helpers for ingest enrichment."""

from __future__ import annotations

import ipaddress
import socket
from functools import lru_cache

from backend.config.schema import Config

try:
    import dns.exception
    import dns.resolver
    import dns.reversename
except ImportError:  # pragma: no cover - optional dependency during local development
    dns = None  # type: ignore[assignment]


def _normalize_hostname(hostname: str | None) -> str | None:
    value = (hostname or "").strip().rstrip(".").lower()
    return value or None


def _resolve_with_socket(ip_text: str) -> str | None:
    try:
        host, _aliases, _addresses = socket.gethostbyaddr(ip_text)
    except (socket.herror, socket.gaierror, OSError):
        return None
    return _normalize_hostname(host)


@lru_cache(maxsize=4096)
def resolve_ip_cached(
    ip_text: str | None,
    nameservers: tuple[str, ...],
    timeout_seconds: float,
) -> tuple[str | None, str | None]:
    value = (ip_text or "").strip()
    if not value:
        return (None, None)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return (None, None)
    try:
        hostname = None
        if dns is not None:
            resolver = dns.resolver.Resolver(configure=not bool(nameservers))
            if nameservers:
                resolver.nameservers = list(nameservers)
            resolver.timeout = timeout_seconds
            resolver.lifetime = timeout_seconds
            reverse_name = dns.reversename.from_address(value)
            answers = resolver.resolve(reverse_name, "PTR")
            hostname = _normalize_hostname(str(answers[0])) if answers else None
    except Exception:
        hostname = None
    if not hostname:
        hostname = _resolve_with_socket(value)
    return (hostname, hostname_to_domain(hostname))


def resolve_ip(config: Config, ip_text: str | None) -> tuple[str | None, str | None]:
    """Resolve an IP to (hostname, hostname_domain); failures return (None, None)."""
    return resolve_ip_cached(ip_text, config.dns_nameservers, config.dns_timeout_seconds)


def hostname_to_domain(hostname: str | None) -> str | None:
    """Collapse a hostname to a best-effort domain-like grouping key."""
    value = _normalize_hostname(hostname)
    if not value:
        return None
    labels = [label for label in value.split(".") if label]
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return value
