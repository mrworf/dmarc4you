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
    assert api_service["ports"] == ["${DMARC_API_PORT:-8000}:${DMARC_SERVER_PORT:-8000}"]
    assert web_service["ports"] == ["${DMARC_WEB_PORT:-3000}:${DMARC_WEB_INTERNAL_PORT:-3000}"]
    assert api_service["environment"]["DMARC_SERVER_PORT"] == "${DMARC_SERVER_PORT:-8000}"
    assert web_service["environment"]["PORT"] == "${DMARC_WEB_INTERNAL_PORT:-3000}"


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


def test_compose_env_example_uses_browser_reachable_frontend_api_url() -> None:
    env_text = Path("compose.env.example").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" in env_text
    assert "NEXT_PUBLIC_API_BASE_URL=http://api:8000" not in env_text


def test_local_build_override_builds_runtime_config_sensitive_images() -> None:
    compose = yaml.safe_load(Path("compose.override.localbuild.yaml").read_text())

    assert compose["services"]["api"]["build"]["dockerfile"] == "Dockerfile.backend"
    assert compose["services"]["web"]["build"]["dockerfile"] == "Dockerfile.frontend"
    assert (
        compose["services"]["web"]["build"]["args"]["NEXT_PUBLIC_API_BASE_URL"]
        == "${LOCAL_WEB_BUILD_NEXT_PUBLIC_API_BASE_URL:-http://build-time.invalid:65535}"
    )
