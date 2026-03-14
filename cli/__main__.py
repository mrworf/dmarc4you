"""Entrypoint for python -m cli."""

import os
import sys
from pathlib import Path

USAGE = """\
Usage:
  python -m cli reset-admin-password [config.yaml]
  python -m cli ingest [--api-key KEY] [--url URL] FILE [FILE ...]

Commands:
  reset-admin-password   Reset bootstrap admin password (break-glass)
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
