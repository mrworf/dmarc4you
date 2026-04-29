"""Tests for container readiness probe scripts."""

from __future__ import annotations

from pathlib import Path


def test_backend_ready_script_uses_runtime_server_port(monkeypatch) -> None:
    monkeypatch.setenv("DMARC_SERVER_PORT", "8111")
    script = Path("scripts/healthchecks/backend_ready.py").read_text(encoding="utf-8")

    assert 'os.environ.get("DMARC_SERVER_PORT", "8000")' in script
    assert 'http://127.0.0.1:{port}/api/v1/health/ready' in script


def test_frontend_ready_script_uses_runtime_port() -> None:
    script = Path("scripts/healthchecks/frontend_ready.mjs").read_text(encoding="utf-8")

    assert 'process.env.PORT ?? "3000"' in script
    assert "http://127.0.0.1:${port}/api/ready" in script
