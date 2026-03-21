"""Seed and clean a deterministic E2E environment for the frontend browser harness."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.auth.bootstrap import BOOTSTRAP_USERNAME, ensure_bootstrap_admin
from backend.auth.password import hash_password
from backend.config import load_config
from backend.config.schema import Config
from backend.jobs.runner import run_one_job
from backend.services import api_key_service, dashboard_service, domain_service, ingest_service, user_service
from backend.storage.sqlite import get_connection, run_migrations

DEFAULT_ENV_FILE = Path(".tmp/e2e/e2e.env")
DEFAULT_SUMMARY_FILE = Path(".tmp/e2e/seed-summary.json")

DEFAULT_E2E_FRONTEND_URL = "http://127.0.0.1:3001"
DEFAULT_E2E_API_URL = "http://127.0.0.1:8001"

SUPERADMIN_PASSWORD = "seed-super-admin-pass"
ADMIN_USERNAME = "e2e-admin"
ADMIN_PASSWORD = "seed-admin-pass"
MANAGER_USERNAME = "e2e-manager"
MANAGER_PASSWORD = "seed-manager-pass"
VIEWER_USERNAME = "e2e-viewer"
VIEWER_PASSWORD = "seed-viewer-pass"

PRIMARY_DOMAIN_NAME = "example.com"
SECONDARY_DOMAIN_NAME = "mail.example.net"
SEARCH_QUERY = "google"
SEARCH_FROM = "2025-01-01"
SEARCH_TO = "2025-12-31"


def _remove_file(path: Path) -> None:
    path.unlink(missing_ok=True)


def _remove_sqlite_files(database_path: Path) -> None:
    for suffix in ("", "-shm", "-wal"):
        _remove_file(Path(f"{database_path}{suffix}"))


def _reset_storage(config: Config, env_file: Path | None = None, summary_file: Path | None = None) -> None:
    database_path = Path(config.database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_sqlite_files(database_path)

    if config.archive_storage_path:
        archive_path = Path(config.archive_storage_path)
        if archive_path.exists():
            shutil.rmtree(archive_path)

    if env_file:
        _remove_file(env_file)
    if summary_file:
        _remove_file(summary_file)


def _set_password(database_path: str, username: str, password: str) -> str:
    conn = get_connection(database_path)
    try:
        cur = conn.execute("SELECT id FROM users WHERE username = ? AND disabled_at IS NULL", (username,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"User not found while setting password: {username}")
        user_id = row[0]
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
        conn.commit()
        return user_id
    finally:
        conn.close()


def _get_user(config: Config, username: str) -> dict[str, Any]:
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, username, role, full_name, email, created_at, created_by_user_id FROM users WHERE username = ? AND disabled_at IS NULL",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Expected seeded user not found: {username}")
        return {
            "id": row[0],
            "username": row[1],
            "role": row[2],
            "full_name": row[3],
            "email": row[4],
            "created_at": row[5],
            "created_by_user_id": row[6],
        }
    finally:
        conn.close()


def _get_domain_id(config: Config, name: str) -> str:
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id FROM domains WHERE name = ?", (name,))
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"Expected seeded domain not found: {name}")
        return row[0]
    finally:
        conn.close()


def _generate_aggregate_xml() -> str:
    records = []
    for index in range(12):
        disposition = "none" if index % 3 != 1 else "reject"
        dkim = "pass" if index % 2 == 0 else "fail"
        spf = "pass" if index % 4 != 3 else "fail"
        source_ip = f"192.0.2.{index + 10}"
        count = index + 1
        records.append(
            f"""
  <record>
    <row>
      <source_ip>{source_ip}</source_ip>
      <count>{count}</count>
      <policy_evaluated>
        <disposition>{disposition}</disposition>
        <dkim>{dkim}</dkim>
        <spf>{spf}</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>{PRIMARY_DOMAIN_NAME}</header_from>
      <envelope_from>alerts@google.example</envelope_from>
      <envelope_to>dmarc@{PRIMARY_DOMAIN_NAME}</envelope_to>
    </identifiers>
  </record>"""
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Google Workspace</org_name>
    <report_id>seed-aggregate-20250101</report_id>
    <date_range>
      <begin>1735689600</begin>
      <end>1735776000</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>{PRIMARY_DOMAIN_NAME}</domain>
  </policy_published>
  {''.join(records)}
</feedback>
"""


def _generate_forensic_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <feedback_type>auth-failure</feedback_type>
  <report_metadata>
    <org_name>Google Workspace</org_name>
    <report_id>seed-forensic-20250102</report_id>
  </report_metadata>
  <policy_published>
    <domain>{PRIMARY_DOMAIN_NAME}</domain>
  </policy_published>
  <auth_failure>
    <source_ip>198.51.100.44</source_ip>
    <arrival_date>2025-01-02T12:00:00Z</arrival_date>
    <header_from>spoofed@{PRIMARY_DOMAIN_NAME}</header_from>
    <envelope_from>bounce@google.example</envelope_from>
    <envelope_to>dmarc@{PRIMARY_DOMAIN_NAME}</envelope_to>
    <spf_result>fail</spf_result>
    <dkim_result>fail</dkim_result>
    <dmarc_result>fail</dmarc_result>
    <failure_type>spf</failure_type>
  </auth_failure>
</feedback>
"""


def _seed_reports(config: Config, actor_user_id: str) -> str:
    envelope = {
        "source": "seed",
        "reports": [
            {"content_type": "application/xml", "content": _generate_aggregate_xml()},
            {"content_type": "application/xml", "content": _generate_forensic_xml()},
        ],
    }
    job_id = ingest_service.create_ingest_job(config, envelope, "user", actor_user_id=actor_user_id)
    while run_one_job(config):
        pass
    return job_id


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f'{key}="{value}"' for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_summary_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_users(config: Config, super_admin: dict[str, Any]) -> dict[str, dict[str, Any]]:
    created_users: dict[str, dict[str, Any]] = {}
    user_specs = [
        ("admin", ADMIN_USERNAME, "admin", ADMIN_PASSWORD),
        ("manager", MANAGER_USERNAME, "manager", MANAGER_PASSWORD),
        ("viewer", VIEWER_USERNAME, "viewer", VIEWER_PASSWORD),
    ]

    for key, username, role, password in user_specs:
        status, result = user_service.create_user(
            config,
            super_admin,
            username=username,
            role=role,
            full_name=username.replace("-", " ").title(),
            email=f"{username}@example.com",
        )
        if status != "ok" or not result:
            raise RuntimeError(f"Failed to seed user {username}: {status}")
        _set_password(config.database_path, username, password)
        created_users[key] = _get_user(config, username)

    return created_users


def seed_e2e_environment(
    config_path: str | Path | None = None,
    *,
    env_file: str | Path | None = None,
    summary_file: str | Path | None = None,
    cleanup: bool = False,
) -> dict[str, Any] | None:
    """Seed or clean the deterministic frontend E2E environment."""
    config = load_config(config_path)
    frontend_url = config.frontend_public_origin or DEFAULT_E2E_FRONTEND_URL
    api_url = config.api_public_url or DEFAULT_E2E_API_URL
    env_path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    summary_path = Path(summary_file) if summary_file is not None else DEFAULT_SUMMARY_FILE

    if cleanup:
        _reset_storage(config, env_path, summary_path)
        return None

    _reset_storage(config, env_path, summary_path)
    run_migrations(config.database_path)
    ensure_bootstrap_admin(config.database_path)

    super_admin_id = _set_password(config.database_path, BOOTSTRAP_USERNAME, SUPERADMIN_PASSWORD)
    super_admin = _get_user(config, BOOTSTRAP_USERNAME)
    super_admin["id"] = super_admin_id

    primary_status, _ = domain_service.create_domain(config, PRIMARY_DOMAIN_NAME, super_admin_id, "super-admin")
    if primary_status != "ok":
        raise RuntimeError(f"Failed to seed primary domain: {primary_status}")
    secondary_status, _ = domain_service.create_domain(config, SECONDARY_DOMAIN_NAME, super_admin_id, "super-admin")
    if secondary_status != "ok":
        raise RuntimeError(f"Failed to seed secondary domain: {secondary_status}")

    primary_domain_id = _get_domain_id(config, PRIMARY_DOMAIN_NAME)
    secondary_domain_id = _get_domain_id(config, SECONDARY_DOMAIN_NAME)

    seeded_users = _seed_users(config, super_admin)

    for actor_key in ("admin", "manager", "viewer"):
        status, _ = user_service.assign_domains(config, super_admin, seeded_users[actor_key]["id"], [primary_domain_id])
        if status != "ok":
            raise RuntimeError(f"Failed to assign seeded domain to {actor_key}: {status}")

    dashboard_status, dashboard = dashboard_service.create_dashboard(
        config,
        name="Seeded Operations",
        description="Seeded dashboard for Next.js browser validation.",
        domain_ids=[primary_domain_id],
        visible_columns=[],
        owner_user_id=super_admin_id,
        current_user=super_admin,
    )
    if dashboard_status != "ok" or not dashboard:
        raise RuntimeError(f"Failed to seed dashboard: {dashboard_status}")

    share_manager_status, _ = dashboard_service.share_dashboard(
        config,
        dashboard_id=dashboard["id"],
        target_user_id=seeded_users["manager"]["id"],
        access_level="manager",
        current_user=super_admin,
    )
    if share_manager_status != "ok":
        raise RuntimeError(f"Failed to share dashboard with manager: {share_manager_status}")

    share_viewer_status, _ = dashboard_service.share_dashboard(
        config,
        dashboard_id=dashboard["id"],
        target_user_id=seeded_users["viewer"]["id"],
        access_level="viewer",
        current_user=super_admin,
    )
    if share_viewer_status != "ok":
        raise RuntimeError(f"Failed to share dashboard with viewer: {share_viewer_status}")

    api_key_id, raw_secret, api_key_error = api_key_service.create_api_key(
        config,
        nickname="seed-ingest",
        description="Seeded ingest key for browser and manual checks.",
        domain_ids=[primary_domain_id],
        scopes=[api_key_service.SCOPE_REPORTS_INGEST],
        created_by_user_id=seeded_users["admin"]["id"],
        current_user=seeded_users["admin"],
    )
    if api_key_error or not api_key_id or not raw_secret:
        raise RuntimeError(f"Failed to seed API key: {api_key_error or 'unknown'}")

    ingest_job_id = _seed_reports(config, super_admin_id)

    env_values = {
        "DMARC_E2E_SUPERADMIN_USERNAME": BOOTSTRAP_USERNAME,
        "DMARC_E2E_SUPERADMIN_PASSWORD": SUPERADMIN_PASSWORD,
        "DMARC_E2E_ADMIN_USERNAME": ADMIN_USERNAME,
        "DMARC_E2E_ADMIN_PASSWORD": ADMIN_PASSWORD,
        "DMARC_E2E_MANAGER_USERNAME": MANAGER_USERNAME,
        "DMARC_E2E_MANAGER_PASSWORD": MANAGER_PASSWORD,
        "DMARC_E2E_VIEWER_USERNAME": VIEWER_USERNAME,
        "DMARC_E2E_VIEWER_PASSWORD": VIEWER_PASSWORD,
        "DMARC_E2E_DASHBOARD_ID": dashboard["id"],
        "DMARC_E2E_SEARCH_DOMAIN": PRIMARY_DOMAIN_NAME,
        "DMARC_E2E_SEARCH_QUERY": SEARCH_QUERY,
        "DMARC_E2E_SEARCH_FROM": SEARCH_FROM,
        "DMARC_E2E_SEARCH_TO": SEARCH_TO,
        "DMARC_E2E_BASE_URL": frontend_url,
        "DMARC_E2E_API_BASE_URL": api_url,
        "NEXT_PUBLIC_API_BASE_URL": api_url,
        "NEXT_PUBLIC_CSRF_COOKIE_NAME": config.csrf_cookie_name,
        "NEXT_PUBLIC_REQUEST_ID_HEADER_NAME": "X-Request-ID",
    }
    _write_env_file(env_path, env_values)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(Path(config_path).resolve()) if config_path else None,
        "database_path": config.database_path,
        "archive_storage_path": config.archive_storage_path,
        "frontend_url": frontend_url,
        "api_url": api_url,
        "domain_names": [PRIMARY_DOMAIN_NAME, SECONDARY_DOMAIN_NAME],
        "dashboard_id": dashboard["id"],
        "ingest_job_id": ingest_job_id,
        "api_key_id": api_key_id,
        "api_key_secret": raw_secret,
        "env_file": str(env_path),
        "credentials": {
            "super_admin": {"username": BOOTSTRAP_USERNAME, "password": SUPERADMIN_PASSWORD},
            "admin": {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            "manager": {"username": MANAGER_USERNAME, "password": MANAGER_PASSWORD},
            "viewer": {"username": VIEWER_USERNAME, "password": VIEWER_PASSWORD},
        },
    }
    _write_summary_file(summary_path, summary)
    return summary
