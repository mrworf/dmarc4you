"""API key service: create_api_key, list_api_keys, update_api_key, delete_api_key."""

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection
from backend.services.domain_service import list_domains
from backend.policies.api_key_policy import (
    can_create_api_key,
    can_list_api_keys,
    can_update_api_key,
    can_delete_api_key,
    ROLE_SUPER_ADMIN,
)
from backend.auth.password import hash_password, verify_password

API_KEY_ID_PREFIX = "key_"
SCOPE_REPORTS_INGEST = "reports:ingest"
SCOPE_DOMAINS_MONITOR = "domains:monitor"
API_KEY_SECRET_PREFIX = "dmarc_"


def _normalize_scopes(scopes: list[str]) -> list[str]:
    normalized = sorted({(scope or "").strip() for scope in (scopes or []) if (scope or "").strip()})
    return normalized


def create_api_key(
    config: Config,
    nickname: str,
    description: str,
    domain_ids: list[str],
    scopes: list[str],
    created_by_user_id: str,
    current_user: dict[str, Any],
) -> tuple[str, str | None, str | None]:
    """Create API key. Returns (key_id, raw_secret, None) or (None, None, 'forbidden'|'invalid')."""
    if not can_create_api_key(current_user.get("role") or ""):
        return None, None, "forbidden"
    nickname = (nickname or "").strip()
    if not nickname:
        return None, None, "invalid"
    scopes = _normalize_scopes(scopes)
    if not domain_ids or not scopes:
        return None, None, "invalid"
    allowed_domains = list_domains(config, current_user)
    allowed_ids = {d["id"] for d in allowed_domains}
    if not all(did in allowed_ids for did in domain_ids):
        return None, None, "forbidden"
    raw_secret = API_KEY_SECRET_PREFIX + secrets.token_hex(32)
    key_hash = hash_password(raw_secret)
    key_id = f"{API_KEY_ID_PREFIX}{uuid.uuid4().hex[:14]}"
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """INSERT INTO api_keys (id, nickname, description, key_hash, enabled, created_by_user_id, created_at, expires_at, last_used_at, last_used_ip, last_used_user_agent)
               VALUES (?, ?, ?, ?, 1, ?, ?, NULL, NULL, NULL, NULL)""",
            (key_id, nickname, description or "", key_hash, created_by_user_id, created_at),
        )
        for domain_id in domain_ids:
            conn.execute(
                "INSERT INTO api_key_domains (api_key_id, domain_id) VALUES (?, ?)",
                (key_id, domain_id),
            )
        for scope in scopes:
            conn.execute(
                "INSERT INTO api_key_scopes (api_key_id, scope) VALUES (?, ?)",
                (key_id, scope),
            )
        conn.commit()
        return key_id, raw_secret, None
    finally:
        conn.close()


def update_api_key(
    config: Config,
    key_id: str,
    nickname: str,
    description: str,
    scopes: list[str],
    current_user: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Update API key metadata and scopes; domain bindings remain unchanged."""
    nickname = (nickname or "").strip()
    scopes = _normalize_scopes(scopes)
    if not nickname or not scopes:
        return None, "invalid"

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT created_by_user_id FROM api_keys WHERE id = ?",
            (key_id,),
        )
        row = cur.fetchone()
        if not row:
            return None, "not_found"
        created_by_user_id = row[0]
        if not can_update_api_key(
            current_user.get("role") or "",
            created_by_user_id,
            current_user.get("id") or "",
        ):
            return None, "forbidden"

        conn.execute(
            "UPDATE api_keys SET nickname = ?, description = ? WHERE id = ?",
            (nickname, description or "", key_id),
        )
        conn.execute("DELETE FROM api_key_scopes WHERE api_key_id = ?", (key_id,))
        for scope in scopes:
            conn.execute(
                "INSERT INTO api_key_scopes (api_key_id, scope) VALUES (?, ?)",
                (key_id, scope),
            )
        conn.commit()

        keys, _err = list_api_keys(config, {"id": current_user.get("id"), "role": ROLE_SUPER_ADMIN})
        for key in keys:
            if key["id"] == key_id:
                return key, None
        return None, "not_found"
    finally:
        conn.close()


def list_api_keys(config: Config, current_user: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    """List API keys (no raw secret). Super-admin sees all; others see keys they created. Returns (list, None) or ([], 'forbidden')."""
    if not can_list_api_keys(current_user.get("role") or ""):
        return [], "forbidden"
    conn = get_connection(config.database_path)
    try:
        user_id = current_user.get("id") or ""
        if current_user.get("role") == ROLE_SUPER_ADMIN:
            cur = conn.execute(
                "SELECT id, nickname, description, created_by_user_id, created_at FROM api_keys ORDER BY created_at DESC"
            )
        else:
            cur = conn.execute(
                "SELECT id, nickname, description, created_by_user_id, created_at FROM api_keys WHERE created_by_user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        rows = cur.fetchall()
        out = []
        for row in rows:
            key_id, nickname, description, created_by_user_id, created_at = row
            cur2 = conn.execute(
                "SELECT domain_id FROM api_key_domains WHERE api_key_id = ? ORDER BY domain_id",
                (key_id,),
            )
            domain_ids = [r[0] for r in cur2.fetchall()]
            cur3 = conn.execute(
                "SELECT scope FROM api_key_scopes WHERE api_key_id = ? ORDER BY scope",
                (key_id,),
            )
            scopes = [r[0] for r in cur3.fetchall()]
            domain_names = []
            for did in domain_ids:
                c = conn.execute("SELECT name FROM domains WHERE id = ?", (did,))
                r = c.fetchone()
                domain_names.append(r[0] if r else did)
            out.append({
                "id": key_id,
                "nickname": nickname,
                "description": description or "",
                "domain_ids": domain_ids,
                "domain_names": domain_names,
                "scopes": scopes,
                "created_at": created_at,
            })
        return out, None
    finally:
        conn.close()


def validate_api_key_for_ingest(config: Config, raw_token: str) -> tuple[str, list[str]] | None:
    """Validate Bearer token for ingest: key must be enabled and have scope reports:ingest. Returns (key_id, domain_ids) or None."""
    if not (raw_token or raw_token.strip()):
        return None
    raw_token = raw_token.strip()
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, key_hash FROM api_keys WHERE enabled = 1"
        )
        for row in cur.fetchall():
            key_id, key_hash = row
            if not verify_password(raw_token, key_hash):
                continue
            cur2 = conn.execute(
                "SELECT scope FROM api_key_scopes WHERE api_key_id = ?",
                (key_id,),
            )
            scopes = [r[0] for r in cur2.fetchall()]
            if SCOPE_REPORTS_INGEST not in scopes:
                return None
            cur3 = conn.execute(
                "SELECT domain_id FROM api_key_domains WHERE api_key_id = ? ORDER BY domain_id",
                (key_id,),
            )
            domain_ids = [r[0] for r in cur3.fetchall()]
            return (key_id, domain_ids)
        return None
    finally:
        conn.close()


def validate_api_key_for_scope(config: Config, raw_token: str, required_scope: str) -> tuple[str, list[str]] | None:
    """Validate Bearer token for a specific scope. Returns (key_id, domain_ids) or None."""
    if not (raw_token or raw_token.strip()):
        return None
    raw_token = raw_token.strip()
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute("SELECT id, key_hash FROM api_keys WHERE enabled = 1")
        for key_id, key_hash in cur.fetchall():
            if not verify_password(raw_token, key_hash):
                continue
            scopes = [r[0] for r in conn.execute("SELECT scope FROM api_key_scopes WHERE api_key_id = ?", (key_id,)).fetchall()]
            if required_scope not in scopes:
                return None
            domain_ids = [r[0] for r in conn.execute("SELECT domain_id FROM api_key_domains WHERE api_key_id = ? ORDER BY domain_id", (key_id,)).fetchall()]
            return (key_id, domain_ids)
        return None
    finally:
        conn.close()


def delete_api_key(
    config: Config,
    key_id: str,
    current_user: dict[str, Any],
) -> str:
    """Delete (revoke) API key. Returns 'ok', 'forbidden', or 'not_found'."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT created_by_user_id FROM api_keys WHERE id = ?",
            (key_id,),
        )
        row = cur.fetchone()
        if not row:
            return "not_found"
        created_by = row[0]
        if not can_delete_api_key(
            current_user.get("role") or "",
            created_by,
            current_user.get("id") or "",
        ):
            return "forbidden"
        conn.execute("DELETE FROM api_key_scopes WHERE api_key_id = ?", (key_id,))
        conn.execute("DELETE FROM api_key_domains WHERE api_key_id = ?", (key_id,))
        conn.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        conn.commit()
        return "ok"
    finally:
        conn.close()
