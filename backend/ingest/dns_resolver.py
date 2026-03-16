"""Best-effort reverse DNS helpers for ingest enrichment."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import socket
from functools import lru_cache

_DNS_TIMEOUT_SECONDS = 1.0
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _lookup_host(ip_text: str) -> str | None:
    hostname, _aliases, _addresses = socket.gethostbyaddr(ip_text)
    hostname = (hostname or "").strip().rstrip(".").lower()
    return hostname or None


@lru_cache(maxsize=2048)
def resolve_ip(ip_text: str | None) -> tuple[str | None, str | None]:
    """Resolve an IP to (hostname, hostname_domain); failures return (None, None)."""
    value = (ip_text or "").strip()
    if not value:
        return (None, None)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return (None, None)

    future = _EXECUTOR.submit(_lookup_host, value)
    try:
        hostname = future.result(timeout=_DNS_TIMEOUT_SECONDS)
    except (OSError, socket.herror, socket.gaierror, concurrent.futures.TimeoutError):
        future.cancel()
        return (None, None)

    return (hostname, hostname_to_domain(hostname))


def hostname_to_domain(hostname: str | None) -> str | None:
    """Collapse a hostname to a best-effort domain-like grouping key."""
    value = (hostname or "").strip().rstrip(".").lower()
    if not value:
        return None
    labels = [label for label in value.split(".") if label]
    if len(labels) >= 2:
        return ".".join(labels[-2:])
    return value
