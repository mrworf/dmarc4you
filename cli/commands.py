"""CLI commands: reset-admin-password (break-glass), ingest (submit reports via API key)."""

import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Union

from backend.config import load_config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import BOOTSTRAP_USERNAME
from backend.auth.password import hash_password, generate_random_password


GZIP_MAGIC = b"\x1f\x8b"


def detect_content_type(path: Path, content: bytes) -> str:
    """Detect content type from file extension and magic bytes."""
    suffix = path.suffix.lower()
    if suffix == ".gz" or content[:2] == GZIP_MAGIC:
        return "application/gzip"
    if suffix == ".xml":
        return "application/xml"
    text_start = content[:512].lstrip()
    if text_start.startswith(b"<?xml") or text_start.startswith(b"<feedback"):
        return "application/xml"
    if b"Content-Type:" in content[:1024] or b"MIME-Version:" in content[:1024]:
        return "message/rfc822"
    return "application/octet-stream"


def ingest_files(
    api_key: str,
    base_url: str,
    paths: list[Path],
) -> bool:
    """
    Submit report files to the ingest API using API key auth.
    Returns True if all files succeeded, False if any failed.
    """
    if not paths:
        print("No files specified.", file=sys.stderr)
        return False

    url = base_url.rstrip("/") + "/api/v1/reports/ingest"
    all_ok = True

    for path in paths:
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            all_ok = False
            continue

        try:
            content = path.read_bytes()
        except OSError as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)
            all_ok = False
            continue

        content_type = detect_content_type(path, content)
        encoded = base64.b64encode(content).decode("ascii")

        payload = {
            "source": "cli",
            "reports": [
                {
                    "content_type": content_type,
                    "content_encoding": "",
                    "content_transfer_encoding": "base64",
                    "content": encoded,
                }
            ],
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                job_id = data.get("job_id", "unknown")
                print(f"{path.name}: submitted (job_id={job_id})")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            print(f"{path.name}: failed ({e.code} {e.reason}) {body}", file=sys.stderr)
            all_ok = False
        except urllib.error.URLError as e:
            print(f"{path.name}: connection error ({e.reason})", file=sys.stderr)
            all_ok = False
        except Exception as e:
            print(f"{path.name}: error ({e})", file=sys.stderr)
            all_ok = False

    return all_ok


def reset_admin_password(config_path: Optional[Union[str, Path]] = None) -> Optional[str]:
    """
    Reset the bootstrap admin user's password. Run migrations, find user with username 'admin',
    set new random password, print to stdout. Returns new password on success, None if admin not found.
    """
    config = load_config(config_path)
    run_migrations(config.database_path)
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id FROM users WHERE username = ? AND disabled_at IS NULL",
            (BOOTSTRAP_USERNAME,),
        )
        row = cur.fetchone()
        if not row:
            print("Admin user not found.", file=sys.stderr)
            return None
        password = generate_random_password()
        password_hash = hash_password(password)
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?",
            (password_hash, BOOTSTRAP_USERNAME),
        )
        conn.commit()
        print(password)
        return password
    finally:
        conn.close()
