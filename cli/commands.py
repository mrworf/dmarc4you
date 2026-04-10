"""CLI commands: reset-admin-password (break-glass), ingest (submit reports via API key)."""

import sys
from pathlib import Path
from typing import Optional, Union

from backend.config import load_config
from backend.storage.sqlite import run_migrations, get_connection
from backend.auth.bootstrap import BOOTSTRAP_USERNAME
from datetime import datetime, timezone

from backend.auth.password import hash_password, generate_random_password
from backend.auth.session import invalidate_user_sessions
from backend.ingest.compression import GZIP_MAGIC, ZIP_MAGIC
from cli.ingest_api import IngestApiClient, IngestApiError


def detect_content_type(path: Path, content: bytes) -> str:
    """Detect content type from file extension and magic bytes."""
    suffix = path.suffix.lower()
    if suffix == ".gz" or content[:2] == GZIP_MAGIC:
        return "application/gzip"
    if suffix == ".zip" or content[:4] == ZIP_MAGIC:
        return "application/zip"
    if suffix == ".xml":
        return "application/xml"
    text_start = content[:512].lstrip()
    if text_start.startswith(b"<?xml") or text_start.startswith(b"<feedback"):
        return "application/xml"
    if b"Content-Type:" in content[:1024] or b"MIME-Version:" in content[:1024]:
        return "message/rfc822"
    return "application/octet-stream"


def detect_content_encoding(path: Path, content: bytes) -> str:
    """Detect content encoding for API ingest payloads."""
    suffix = path.suffix.lower()
    if suffix == ".gz" or content[:2] == GZIP_MAGIC:
        return "gzip"
    if suffix == ".zip" or content[:4] == ZIP_MAGIC:
        return "zip"
    return ""


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

    client = IngestApiClient(api_key=api_key, base_url=base_url)
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
        content_encoding = detect_content_encoding(path, content)
        try:
            job_id = client.submit_report_bytes(
                source="cli",
                content=content,
                content_type=content_type,
                content_encoding=content_encoding,
            )
            print(f"{path.name}: submitted (job_id={job_id})")
        except IngestApiError as exc:
            print(f"{path.name}: failed ({exc})", file=sys.stderr)
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
        user_id = row[0]
        password = generate_random_password()
        password_hash = hash_password(password)
        conn.execute(
            """UPDATE users
               SET password_hash = ?, must_change_password = 1, password_changed_at = ?
               WHERE username = ?""",
            (password_hash, datetime.now(timezone.utc).isoformat(), BOOTSTRAP_USERNAME),
        )
        conn.commit()
        invalidate_user_sessions(config.database_path, user_id)
        print(password)
        return password
    finally:
        conn.close()
