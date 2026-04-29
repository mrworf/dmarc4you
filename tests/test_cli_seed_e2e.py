"""Tests for the seeded E2E environment helper."""

from pathlib import Path

import yaml

from cli.e2e_seed import seed_e2e_environment


def test_seed_e2e_environment_writes_dedicated_harness_ports(tmp_path: Path) -> None:
    database_path = tmp_path / "seeded-e2e.db"
    archive_path = tmp_path / "archive"
    config_path = tmp_path / "config.e2e.yaml"
    env_path = tmp_path / "e2e.env"
    summary_path = tmp_path / "seed-summary.json"

    config_path.write_text(
        yaml.safe_dump(
            {
                "database": {"path": str(database_path)},
                "log": {"level": "INFO"},
                "server": {"host": "127.0.0.1", "port": 8001},
                "auth": {"session_secret": "seeded-e2e-not-for-production"},
                "frontend": {"public_origin": "http://127.0.0.1:3001"},
                "api": {"public_url": "http://127.0.0.1:8001"},
                "cors": {"allowed_origins": ["http://127.0.0.1:3001"]},
                "archive": {"storage_path": str(archive_path)},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = seed_e2e_environment(config_path, env_file=env_path, summary_file=summary_path)

    assert summary is not None
    assert summary["frontend_url"] == "http://127.0.0.1:3001"
    assert summary["api_url"] == "http://127.0.0.1:8001"

    env_text = env_path.read_text(encoding="utf-8")
    assert 'DMARC_E2E_BASE_URL="http://127.0.0.1:3001"' in env_text
    assert 'DMARC_E2E_API_BASE_URL="http://127.0.0.1:8001"' in env_text
    assert 'NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8001"' in env_text


def test_seed_e2e_environment_uses_configured_non_default_urls(tmp_path: Path) -> None:
    database_path = tmp_path / "seeded-e2e.db"
    archive_path = tmp_path / "archive"
    config_path = tmp_path / "config.e2e.yaml"
    env_path = tmp_path / "e2e.env"

    config_path.write_text(
        yaml.safe_dump(
            {
                "database": {"path": str(database_path)},
                "log": {"level": "INFO"},
                "server": {"host": "127.0.0.1", "port": 8111},
                "auth": {"session_secret": "seeded-e2e-not-for-production"},
                "frontend": {"public_origin": "http://127.0.0.1:3111"},
                "api": {"public_url": "http://127.0.0.1:8111"},
                "cors": {"allowed_origins": ["http://127.0.0.1:3111"]},
                "archive": {"storage_path": str(archive_path)},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    summary = seed_e2e_environment(config_path, env_file=env_path)

    assert summary is not None
    assert summary["frontend_url"] == "http://127.0.0.1:3111"
    assert summary["api_url"] == "http://127.0.0.1:8111"

    env_text = env_path.read_text(encoding="utf-8")
    assert 'DMARC_E2E_BASE_URL="http://127.0.0.1:3111"' in env_text
    assert 'DMARC_E2E_API_BASE_URL="http://127.0.0.1:8111"' in env_text
    assert 'NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8111"' in env_text
