"""Tests for backend.main startup wiring."""

from __future__ import annotations

from backend.config.schema import Config
import backend.main as backend_main


def _config(**overrides) -> Config:
    return Config(
        database_path="data/test.db",
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="dmarc_session",
        session_max_age_days=7,
        **overrides,
    )


def test_main_passes_configured_host_and_port_to_uvicorn(monkeypatch) -> None:
    config = _config(server_host="127.0.0.1", server_port=8123)
    uvicorn_calls: list[dict[str, object]] = []

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.started = False

        def start(self) -> None:
            self.started = True

    monkeypatch.setattr(backend_main, "load_config", lambda: config)
    monkeypatch.setattr(backend_main, "configure_logging", lambda level: None)
    monkeypatch.setattr(backend_main, "run_migrations", lambda database_path: None)
    monkeypatch.setattr(backend_main, "ensure_bootstrap_admin", lambda database_path: None)
    monkeypatch.setattr(backend_main.threading, "Thread", FakeThread)
    monkeypatch.setattr(
        backend_main.uvicorn,
        "run",
        lambda app, host, port, log_level: uvicorn_calls.append(
            {"app": app, "host": host, "port": port, "log_level": log_level}
        ),
    )

    backend_main.main()

    assert uvicorn_calls == [
        {
            "app": backend_main.app,
            "host": "127.0.0.1",
            "port": 8123,
            "log_level": "info",
        }
    ]


def test_main_prints_bootstrap_password_when_created(monkeypatch, capsys) -> None:
    config = _config()

    class FakeThread:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def start(self) -> None:
            pass

    monkeypatch.setattr(backend_main, "load_config", lambda: config)
    monkeypatch.setattr(backend_main, "configure_logging", lambda level: None)
    monkeypatch.setattr(backend_main, "run_migrations", lambda database_path: None)
    monkeypatch.setattr(backend_main, "ensure_bootstrap_admin", lambda database_path: "seed-pass")
    monkeypatch.setattr(backend_main.threading, "Thread", FakeThread)
    monkeypatch.setattr(backend_main.uvicorn, "run", lambda *args, **kwargs: None)

    backend_main.main()

    captured = capsys.readouterr()
    assert "seed-pass" in captured.err
