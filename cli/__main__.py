"""Entrypoint for python -m cli."""

import json
import os
import sys
from pathlib import Path

USAGE = """\
Usage:
  python -m cli reset-admin-password [config.yaml]
  python -m cli seed-e2e [config.yaml] [--cleanup] [--env-file PATH] [--summary-file PATH]
  python -m cli ingest [--api-key KEY] [--url URL] FILE [FILE ...]
  python -m cli imap-watch [options]

Commands:
  reset-admin-password   Reset bootstrap admin password (break-glass)
  seed-e2e              Seed or clean the deterministic frontend E2E environment
  ingest                 Submit DMARC report files via API key
  imap-watch             Watch an IMAP inbox and upload DMARC report emails

Ingest options:
  --api-key KEY   API key (or set DMARC4YOU_API_KEY env var)
  --url URL       API base URL (default: http://localhost:8000, or DMARC4YOU_URL)

IMAP watch options:
  --api-url URL                  DMARCWatch API URL (or DMARC_IMAP_API_URL)
  --api-key KEY                  Ingest API key (or DMARC_IMAP_API_KEY)
  --host HOST                    IMAP host (or DMARC_IMAP_HOST)
  --port PORT                    IMAP port (default: 993 or DMARC_IMAP_PORT)
  --username USER                IMAP username (or DMARC_IMAP_USERNAME)
  --password PASS                IMAP password (or DMARC_IMAP_PASSWORD)
  --mailbox NAME                 Mailbox name (default: INBOX or DMARC_IMAP_MAILBOX)
  --poll-seconds N               Poll interval seconds (default: 60 or DMARC_IMAP_POLL_SECONDS)
  --restart-on-start             Clear local state and mark mailbox unread on startup
  --delete-after-days N          -1 disables deletes, 0 deletes after upload, N uses IMAP internal date
  --state-path PATH              Local SQLite state path (or DMARC_IMAP_STATE_PATH)
  --connect-timeout-seconds N    IMAP connect timeout (or DMARC_IMAP_CONNECT_TIMEOUT_SECONDS)
  --job-timeout-seconds N        Ingest job wait timeout (or DMARC_IMAP_JOB_TIMEOUT_SECONDS)
"""


def parse_ingest_args(argv: list[str]) -> tuple[str | None, str, list[Path]]:
    """Parse ingest subcommand args. Returns (api_key, url, paths)."""
    api_key = os.environ.get("DMARC4YOU_API_KEY")
    url = os.environ.get("DMARC4YOU_URL", "http://localhost:8000")
    paths: list[Path] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--api-key" and i + 1 < len(argv):
            api_key = argv[i + 1]
            i += 2
        elif arg.startswith("--api-key="):
            api_key = arg.split("=", 1)[1]
            i += 1
        elif arg == "--url" and i + 1 < len(argv):
            url = argv[i + 1]
            i += 2
        elif arg.startswith("--url="):
            url = arg.split("=", 1)[1]
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)
        else:
            paths.append(Path(arg))
            i += 1

    return api_key, url, paths


def parse_seed_e2e_args(argv: list[str]) -> tuple[Path | None, bool, Path | None, Path | None]:
    """Parse seed-e2e args. Returns (config_path, cleanup, env_file, summary_file)."""
    cleanup = False
    env_file: Path | None = None
    summary_file: Path | None = None
    config_path: Path | None = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--cleanup":
            cleanup = True
            i += 1
        elif arg == "--env-file" and i + 1 < len(argv):
            env_file = Path(argv[i + 1])
            i += 2
        elif arg.startswith("--env-file="):
            env_file = Path(arg.split("=", 1)[1])
            i += 1
        elif arg == "--summary-file" and i + 1 < len(argv):
            summary_file = Path(argv[i + 1])
            i += 2
        elif arg.startswith("--summary-file="):
            summary_file = Path(arg.split("=", 1)[1])
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)
        elif config_path is None:
            config_path = Path(arg)
            i += 1
        else:
            print(f"Unexpected argument: {arg}", file=sys.stderr)
            sys.exit(1)

    return config_path, cleanup, env_file, summary_file


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def parse_imap_watch_args(argv: list[str]):  # type: ignore[no-untyped-def]
    """Parse imap-watch args and return an ImapWatchConfig."""
    from cli.imap_watch import ImapWatchConfig

    values: dict[str, object] = {
        "api_url": os.environ.get("DMARC_IMAP_API_URL", "http://localhost:8000"),
        "api_key": os.environ.get("DMARC_IMAP_API_KEY"),
        "host": os.environ.get("DMARC_IMAP_HOST"),
        "port": int(os.environ.get("DMARC_IMAP_PORT", "993")),
        "username": os.environ.get("DMARC_IMAP_USERNAME"),
        "password": os.environ.get("DMARC_IMAP_PASSWORD"),
        "mailbox": os.environ.get("DMARC_IMAP_MAILBOX", "INBOX"),
        "poll_seconds": int(os.environ.get("DMARC_IMAP_POLL_SECONDS", "60")),
        "restart_on_start": _parse_bool(os.environ.get("DMARC_IMAP_RESTART_ON_START"), False),
        "delete_after_days": int(os.environ.get("DMARC_IMAP_DELETE_AFTER_DAYS", "-1")),
        "state_path": os.environ.get("DMARC_IMAP_STATE_PATH", "data/imap-watch-state.db"),
        "connect_timeout_seconds": float(os.environ.get("DMARC_IMAP_CONNECT_TIMEOUT_SECONDS", "30")),
        "job_timeout_seconds": float(os.environ.get("DMARC_IMAP_JOB_TIMEOUT_SECONDS", "300")),
    }

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--restart-on-start":
            values["restart_on_start"] = True
            i += 1
        elif arg == "--api-url" and i + 1 < len(argv):
            values["api_url"] = argv[i + 1]
            i += 2
        elif arg.startswith("--api-url="):
            values["api_url"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--api-key" and i + 1 < len(argv):
            values["api_key"] = argv[i + 1]
            i += 2
        elif arg.startswith("--api-key="):
            values["api_key"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--host" and i + 1 < len(argv):
            values["host"] = argv[i + 1]
            i += 2
        elif arg.startswith("--host="):
            values["host"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--port" and i + 1 < len(argv):
            values["port"] = int(argv[i + 1])
            i += 2
        elif arg.startswith("--port="):
            values["port"] = int(arg.split("=", 1)[1])
            i += 1
        elif arg == "--username" and i + 1 < len(argv):
            values["username"] = argv[i + 1]
            i += 2
        elif arg.startswith("--username="):
            values["username"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--password" and i + 1 < len(argv):
            values["password"] = argv[i + 1]
            i += 2
        elif arg.startswith("--password="):
            values["password"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--mailbox" and i + 1 < len(argv):
            values["mailbox"] = argv[i + 1]
            i += 2
        elif arg.startswith("--mailbox="):
            values["mailbox"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--poll-seconds" and i + 1 < len(argv):
            values["poll_seconds"] = int(argv[i + 1])
            i += 2
        elif arg.startswith("--poll-seconds="):
            values["poll_seconds"] = int(arg.split("=", 1)[1])
            i += 1
        elif arg == "--delete-after-days" and i + 1 < len(argv):
            values["delete_after_days"] = int(argv[i + 1])
            i += 2
        elif arg.startswith("--delete-after-days="):
            values["delete_after_days"] = int(arg.split("=", 1)[1])
            i += 1
        elif arg == "--state-path" and i + 1 < len(argv):
            values["state_path"] = argv[i + 1]
            i += 2
        elif arg.startswith("--state-path="):
            values["state_path"] = arg.split("=", 1)[1]
            i += 1
        elif arg == "--connect-timeout-seconds" and i + 1 < len(argv):
            values["connect_timeout_seconds"] = float(argv[i + 1])
            i += 2
        elif arg.startswith("--connect-timeout-seconds="):
            values["connect_timeout_seconds"] = float(arg.split("=", 1)[1])
            i += 1
        elif arg == "--job-timeout-seconds" and i + 1 < len(argv):
            values["job_timeout_seconds"] = float(argv[i + 1])
            i += 2
        elif arg.startswith("--job-timeout-seconds="):
            values["job_timeout_seconds"] = float(arg.split("=", 1)[1])
            i += 1
        else:
            print(f"Unknown option: {arg}", file=sys.stderr)
            sys.exit(1)

    missing = [name for name in ("api_key", "host", "username", "password") if not values.get(name)]
    if missing:
        print(f"Error: missing required imap-watch settings: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)
    return ImapWatchConfig(
        api_url=str(values["api_url"]),
        api_key=str(values["api_key"]),
        host=str(values["host"]),
        port=int(values["port"]),
        username=str(values["username"]),
        password=str(values["password"]),
        mailbox=str(values["mailbox"]),
        poll_seconds=int(values["poll_seconds"]),
        restart_on_start=bool(values["restart_on_start"]),
        delete_after_days=int(values["delete_after_days"]),
        state_path=str(values["state_path"]),
        connect_timeout_seconds=float(values["connect_timeout_seconds"]),
        job_timeout_seconds=float(values["job_timeout_seconds"]),
    )


def main() -> None:
    argv = sys.argv[1:]

    if not argv:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    cmd = argv[0]

    if cmd == "reset-admin-password":
        from cli.commands import reset_admin_password

        config_path = Path(argv[1]) if len(argv) > 1 else None
        result = reset_admin_password(config_path)
        sys.exit(0 if result is not None else 1)

    if cmd == "seed-e2e":
        from cli.e2e_seed import seed_e2e_environment

        config_path, cleanup, env_file, summary_file = parse_seed_e2e_args(argv[1:])
        result = seed_e2e_environment(
            config_path,
            cleanup=cleanup,
            env_file=env_file,
            summary_file=summary_file,
        )
        if cleanup:
            print("Seeded E2E environment removed.")
            sys.exit(0)
        assert result is not None
        print(json.dumps(result, indent=2, sort_keys=True))
        sys.exit(0)

    if cmd == "ingest":
        from cli.commands import ingest_files

        api_key, url, paths = parse_ingest_args(argv[1:])
        if not api_key:
            print("Error: --api-key required or set DMARC4YOU_API_KEY", file=sys.stderr)
            sys.exit(1)
        if not paths:
            print("Error: at least one file path required", file=sys.stderr)
            sys.exit(1)
        success = ingest_files(api_key, url, paths)
        sys.exit(0 if success else 1)

    if cmd == "imap-watch":
        from cli.imap_watch import run_imap_watch

        config = parse_imap_watch_args(argv[1:])
        run_imap_watch(config)
        sys.exit(0)

    print(USAGE, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
