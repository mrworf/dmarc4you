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

Commands:
  reset-admin-password   Reset bootstrap admin password (break-glass)
  seed-e2e              Seed or clean the deterministic frontend E2E environment
  ingest                 Submit DMARC report files via API key

Ingest options:
  --api-key KEY   API key (or set DMARC4YOU_API_KEY env var)
  --url URL       API base URL (default: http://localhost:8000, or DMARC4YOU_URL)
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

    print(USAGE, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
