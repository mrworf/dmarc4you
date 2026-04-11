"""Smoke checks for IMAP collector compose wiring."""

from pathlib import Path

import yaml


def test_base_compose_healthchecks_use_in_container_probe_scripts() -> None:
    compose = yaml.safe_load(Path("compose.yaml").read_text())

    api_service = compose["services"]["api"]
    web_service = compose["services"]["web"]

    assert api_service["healthcheck"]["test"] == ["CMD", "/app/scripts/healthchecks/backend_ready.py"]
    assert web_service["healthcheck"]["test"] == ["CMD", "/app/scripts/healthchecks/frontend_ready.mjs"]
    assert "-c" not in api_service["healthcheck"]["test"]
    assert "-e" not in web_service["healthcheck"]["test"]


def test_base_compose_contains_imap_profile_service() -> None:
    compose = yaml.safe_load(Path("compose.yaml").read_text())

    assert "imap" in compose["services"]
    service = compose["services"]["imap"]
    assert service["profiles"] == ["imap"]
    assert service["command"] == ["python", "-m", "cli", "imap-watch"]
    assert "/app/state" in str(service["volumes"])


def test_standalone_compose_contains_only_imap_service() -> None:
    compose = yaml.safe_load(Path("compose.imap.yaml").read_text())

    assert set(compose["services"]) == {"imap"}
    service = compose["services"]["imap"]
    assert service["command"] == ["python", "-m", "cli", "imap-watch"]
    assert "depends_on" not in service
