"""DNS monitoring for DMARC, SPF, and configured DKIM selectors."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection

try:
    import dns.exception
    import dns.resolver
except ImportError:  # pragma: no cover
    dns = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

ACTION_CHECK_DNS_MONITORING = "check_dns_monitoring"
STATE_QUEUED = "queued"
STATE_PROCESSING = "processing"
ROLE_SUPER_ADMIN = "super-admin"
ROLE_ADMIN = "admin"
SCOPE_DOMAINS_MONITOR = "domains:monitor"
HISTORY_ID_PREFIX = "dmhist_"
MIN_TRIGGER_INTERVAL_SECONDS = 60
DNS_RESULT_OK = "ok"
DNS_RESULT_MISSING = "missing"
DNS_RESULT_ERROR = "error"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _clamp_interval(seconds: int | None, default_seconds: int) -> int:
    value = seconds if seconds is not None and seconds > 0 else default_seconds
    return min(max(60, int(value)), 3600)


def _normalize_selector(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "", (value or "").strip().lower())


def _normalize_selectors(values: list[str]) -> list[str]:
    selectors = sorted({_normalize_selector(value) for value in values if _normalize_selector(value)})
    return selectors


def _format_lookup_error(host: str, error: str | None) -> str | None:
    if not error:
        return None
    if error.startswith(f"{host}:"):
        return error
    return f"{host}: {error}"


def _write_audit_event(
    database_path: str,
    *,
    action_type: str,
    outcome: str,
    actor_user_id: str | None,
    actor_api_key_id: str | None,
    summary: str,
) -> None:
    event_id = f"aud_{uuid.uuid4().hex[:16]}"
    conn = get_connection(database_path)
    try:
        conn.execute(
            """INSERT INTO audit_log
               (id, timestamp, actor_type, actor_user_id, actor_api_key_id, action_type, outcome, source_ip, user_agent, summary, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL)""",
            (
                event_id,
                _now_iso(),
                "api_key" if actor_api_key_id else "user",
                actor_user_id,
                actor_api_key_id,
                action_type,
                outcome,
                summary,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _serialize_latest_job(row: Any) -> dict[str, Any]:
    return {
        "job_id": row[0],
        "domain_id": row[1],
        "domain_name": row[2],
        "action": row[3],
        "actor_user_id": row[4],
        "actor_api_key_id": row[5],
        "submitted_at": row[6],
        "started_at": row[7],
        "completed_at": row[8],
        "state": row[9],
        "reports_scanned": row[10],
        "reports_skipped": row[11],
        "records_updated": row[12],
        "last_error": row[13],
        "summary": row[14],
    }


def _serialize_domain_row(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "name": row[1],
        "status": row[2],
        "created_at": row[3],
        "archived_at": row[4],
        "retention_days": row[5],
        "retention_delete_at": row[6],
        "retention_paused": row[7] if row[7] is not None else 0,
        "retention_remaining_seconds": row[8],
        "monitoring_enabled": row[9] if row[9] is not None else 0,
        "monitoring_last_checked_at": row[10],
        "monitoring_next_check_at": row[11],
        "monitoring_last_change_at": row[12],
        "monitoring_failure_active": row[13] if row[13] is not None else 0,
        "monitoring_last_failure_at": row[14],
        "monitoring_last_failure_summary": row[15],
    }


def fetch_domain_summary(config: Config, *, domain_id: str) -> dict[str, Any] | None:
    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            """SELECT id, name, status, created_at, archived_at, retention_days, retention_delete_at,
                      retention_paused, retention_remaining_seconds, monitoring_enabled, monitoring_last_checked_at,
                      monitoring_next_check_at, monitoring_last_change_at, monitoring_failure_active,
                      monitoring_last_failure_at, monitoring_last_failure_summary
               FROM domains
               WHERE id = ?""",
            (domain_id,),
        ).fetchone()
        if not row:
            return None
        summary = _serialize_domain_row(row)
        latest_job_row = conn.execute(
            """SELECT id, domain_id, domain_name, action, actor_user_id, actor_api_key_id, submitted_at, started_at, completed_at,
                      state, reports_scanned, reports_skipped, records_updated, last_error, summary
               FROM domain_maintenance_jobs
               WHERE domain_id = ?
               ORDER BY submitted_at DESC
               LIMIT 1""",
            (domain_id,),
        ).fetchone()
        if latest_job_row:
            summary["latest_maintenance_job"] = _serialize_latest_job(latest_job_row)
        return summary
    finally:
        conn.close()


def _get_session_domain_access(
    config: Config,
    *,
    actor: dict[str, Any],
    domain_id: str,
    require_admin: bool,
) -> tuple[str, dict[str, Any] | None]:
    role = actor.get("role") or ""
    actor_user_id = actor.get("id") or ""
    domain = fetch_domain_summary(config, domain_id=domain_id)
    if not domain:
        return "not_found", None
    if role == ROLE_SUPER_ADMIN:
        return "ok", domain
    if domain["status"] != "active":
        return "forbidden", None

    conn = get_connection(config.database_path)
    try:
        assigned = conn.execute(
            "SELECT 1 FROM user_domain_assignments WHERE user_id = ? AND domain_id = ?",
            (actor_user_id, domain_id),
        ).fetchone()
    finally:
        conn.close()
    if not assigned:
        return "forbidden", None
    if require_admin and role != ROLE_ADMIN:
        return "forbidden", None
    return "ok", domain


def _get_api_key_domain_access(
    config: Config,
    *,
    actor: dict[str, Any],
    domain_id: str,
) -> tuple[str, dict[str, Any] | None]:
    domain = fetch_domain_summary(config, domain_id=domain_id)
    if not domain:
        return "not_found", None
    if domain["status"] != "active":
        return "forbidden", None
    if domain_id not in set(actor.get("domain_ids") or []):
        return "forbidden", None
    return "ok", domain


def get_visible_domain(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
    require_admin: bool = False,
) -> tuple[str, dict[str, Any] | None]:
    if actor.get("type") == "api_key":
        if require_admin:
            return "forbidden", None
        return _get_api_key_domain_access(config, actor=actor, domain_id=domain_id)
    return _get_session_domain_access(config, actor=actor, domain_id=domain_id, require_admin=require_admin)


def _load_selectors(conn, *, domain_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT selector FROM domain_monitoring_dkim_selectors WHERE domain_id = ? ORDER BY selector",
        (domain_id,),
    ).fetchall()
    return [row[0] for row in rows]


def _load_current_state(conn, *, domain_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT checked_at, observed_state_json, dmarc_record_raw, spf_record_raw, dkim_records_json, ttl_seconds, error_summary
           FROM domain_monitoring_current_state
           WHERE domain_id = ?""",
        (domain_id,),
    ).fetchone()
    if not row:
        return None
    observed_state = json.loads(row[1])
    observed_state["checked_at"] = row[0]
    observed_state["ttl_seconds"] = row[5]
    observed_state["error_summary"] = row[6]
    return observed_state


def _load_history(conn, *, domain_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT id, changed_at, summary, previous_state_json, current_state_json
           FROM domain_monitoring_history
           WHERE domain_id = ?
           ORDER BY changed_at DESC
           LIMIT ?""",
        (domain_id, limit),
    ).fetchall()
    history = []
    for row in rows:
        history.append(
            _serialize_history_entry(
                history_id=row[0],
                changed_at=row[1],
                summary=row[2],
                previous_state=json.loads(row[3]) if row[3] else None,
                current_state=json.loads(row[4]),
            )
        )
    return history


def _snapshot_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "dmarc": state.get("dmarc") or {},
        "spf": state.get("spf") or {},
        "dkim": state.get("dkim") or [],
    }


def _qualifier_rank(value: str | None) -> int:
    ranks = {
        "allow_all": 0,
        "neutral": 1,
        "softfail": 2,
        "fail": 3,
    }
    return ranks.get((value or "").strip().lower(), 1)


def _policy_rank(value: str | None) -> int:
    ranks = {
        "none": 0,
        "quarantine": 1,
        "reject": 2,
    }
    return ranks.get((value or "").strip().lower(), 0)


def _alignment_rank(value: str | None) -> int:
    ranks = {
        "r": 0,
        "s": 1,
    }
    return ranks.get((value or "").strip().lower(), 0)


def _diff_dmarc(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_status = previous.get("status")
    after_status = current.get("status")
    if before_status != after_status and {before_status, after_status} & {DNS_RESULT_MISSING, DNS_RESULT_OK}:
        if after_status == DNS_RESULT_MISSING:
            return [
                {
                    "record_type": "dmarc",
                    "label": "DMARC record missing",
                    "direction": "degraded",
                    "reason": "The DMARC record is no longer published.",
                    "before_value": previous.get("raw_value"),
                    "after_value": "missing",
                    "before_raw": previous.get("raw_value"),
                    "after_raw": None,
                }
            ]
        return [
            {
                "record_type": "dmarc",
                "label": "DMARC record restored",
                "direction": "improved",
                "reason": "The DMARC record is published again.",
                "before_value": "missing",
                "after_value": current.get("raw_value"),
                "before_raw": None,
                "after_raw": current.get("raw_value"),
            }
        ]

    previous_parsed = previous.get("parsed") or {}
    current_parsed = current.get("parsed") or {}

    comparisons = [
        ("p", "DMARC policy", _policy_rank),
        ("sp", "DMARC subdomain policy", _policy_rank),
        ("adkim", "DKIM alignment mode", _alignment_rank),
        ("aspf", "SPF alignment mode", _alignment_rank),
    ]
    for key, label, ranker in comparisons:
        before = previous_parsed.get(key)
        after = current_parsed.get(key)
        if before == after:
            continue
        direction = "improved" if ranker(after) > ranker(before) else "degraded"
        changes.append(
            {
                "record_type": "dmarc",
                "label": label,
                "direction": direction,
                "reason": f"{label} changed from {before or 'unset'} to {after or 'unset'}.",
                "before_value": before,
                "after_value": after,
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )

    before_pct = int(str(previous_parsed.get("pct") or "100") or "100")
    after_pct = int(str(current_parsed.get("pct") or "100") or "100")
    if before_pct != after_pct:
        direction = "improved" if after_pct > before_pct else "degraded"
        changes.append(
            {
                "record_type": "dmarc",
                "label": "DMARC enforcement percentage",
                "direction": direction,
                "reason": f"DMARC pct changed from {before_pct}% to {after_pct}%.",
                "before_value": before_pct,
                "after_value": after_pct,
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )

    if not changes and previous.get("raw_value") != current.get("raw_value"):
        changes.append(
            {
                "record_type": "dmarc",
                "label": "DMARC record",
                "direction": "neutral",
                "reason": "DMARC record text changed without a stronger or weaker classified posture.",
                "before_value": previous.get("raw_value"),
                "after_value": current.get("raw_value"),
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )
    return changes


def _extract_spf_includes(record_state: dict[str, Any]) -> list[str]:
    parsed = record_state.get("parsed") or {}
    includes = parsed.get("includes") or []
    return [str(item) for item in includes]


def _diff_spf(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_status = previous.get("status")
    after_status = current.get("status")
    if before_status != after_status and {before_status, after_status} & {"missing", "ok"}:
        if after_status == DNS_RESULT_MISSING:
            return [
                {
                    "record_type": "spf",
                    "label": "SPF record missing",
                    "direction": "degraded",
                    "reason": "The SPF record is no longer published.",
                    "before_value": previous.get("raw_value"),
                    "after_value": "missing",
                    "before_raw": previous.get("raw_value"),
                    "after_raw": None,
                }
            ]
        return [
            {
                "record_type": "spf",
                "label": "SPF record restored",
                "direction": "improved",
                "reason": "The SPF record is published again.",
                "before_value": "missing",
                "after_value": current.get("raw_value"),
                "before_raw": None,
                "after_raw": current.get("raw_value"),
            }
        ]

    previous_parsed = previous.get("parsed") or {}
    current_parsed = current.get("parsed") or {}
    before_qualifier = previous_parsed.get("qualifier")
    after_qualifier = current_parsed.get("qualifier")
    if before_qualifier != after_qualifier:
        direction = "improved" if _qualifier_rank(after_qualifier) > _qualifier_rank(before_qualifier) else "degraded"
        changes.append(
            {
                "record_type": "spf",
                "label": "SPF terminal policy",
                "direction": direction,
                "reason": f"SPF terminal policy changed from {before_qualifier or 'unset'} to {after_qualifier or 'unset'}.",
                "before_value": before_qualifier,
                "after_value": after_qualifier,
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )

    before_includes = set(_extract_spf_includes(previous))
    after_includes = set(_extract_spf_includes(current))
    if before_includes != after_includes:
        added = sorted(after_includes - before_includes)
        removed = sorted(before_includes - after_includes)
        direction = "degraded" if added and not removed else "improved" if removed and not added else "neutral"
        reason_parts = []
        if added:
            reason_parts.append(f"added sender mechanisms: {', '.join(added)}")
        if removed:
            reason_parts.append(f"removed sender mechanisms: {', '.join(removed)}")
        changes.append(
            {
                "record_type": "spf",
                "label": "Authorized SPF senders",
                "direction": direction,
                "reason": f"SPF sender authorization changed; {'; '.join(reason_parts)}.",
                "before_value": sorted(before_includes),
                "after_value": sorted(after_includes),
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )

    if not changes and previous.get("raw_value") != current.get("raw_value"):
        changes.append(
            {
                "record_type": "spf",
                "label": "SPF record",
                "direction": "neutral",
                "reason": "SPF record text changed without a classified security improvement or degradation.",
                "before_value": previous.get("raw_value"),
                "after_value": current.get("raw_value"),
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )
    return changes


def _index_dkim(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        parsed = record.get("parsed") or {}
        selector = str(parsed.get("selector") or record.get("host") or "")
        if selector:
            indexed[selector] = record
    return indexed


def _diff_dkim(previous_records: list[dict[str, Any]], current_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    previous_index = _index_dkim(previous_records)
    current_index = _index_dkim(current_records)
    selectors = sorted(set(previous_index) | set(current_index))

    for selector in selectors:
        previous = previous_index.get(selector, {})
        current = current_index.get(selector, {})
        before_status = previous.get("status")
        after_status = current.get("status")
        if before_status != after_status and {before_status, after_status} & {DNS_RESULT_MISSING, DNS_RESULT_OK}:
            if after_status == DNS_RESULT_MISSING:
                changes.append(
                    {
                        "record_type": "dkim",
                        "selector": selector,
                        "label": f"DKIM selector {selector} missing",
                        "direction": "degraded",
                        "reason": f"DKIM selector {selector} is no longer published.",
                        "before_value": previous.get("raw_value"),
                        "after_value": "missing",
                        "before_raw": previous.get("raw_value"),
                        "after_raw": None,
                    }
                )
            else:
                changes.append(
                    {
                        "record_type": "dkim",
                        "selector": selector,
                        "label": f"DKIM selector {selector} restored",
                        "direction": "improved",
                        "reason": f"DKIM selector {selector} is published again.",
                        "before_value": "missing",
                        "after_value": current.get("raw_value"),
                        "before_raw": None,
                        "after_raw": current.get("raw_value"),
                    }
                )
            continue
        before_has_key = bool((previous.get("parsed") or {}).get("has_key"))
        after_has_key = bool((current.get("parsed") or {}).get("has_key"))
        if before_has_key == after_has_key and previous.get("raw_value") == current.get("raw_value"):
            continue
        direction = "neutral"
        if after_has_key and not before_has_key:
            direction = "improved"
        elif before_has_key and not after_has_key:
            direction = "degraded"
        reason = f"DKIM selector {selector} changed."
        if direction == "improved":
            reason = f"DKIM selector {selector} gained a usable public key."
        elif direction == "degraded":
            reason = f"DKIM selector {selector} lost a usable public key."
        changes.append(
            {
                "record_type": "dkim",
                "selector": selector,
                "label": f"DKIM selector {selector}",
                "direction": direction,
                "reason": reason,
                "before_value": previous.get("raw_value"),
                "after_value": current.get("raw_value"),
                "before_raw": previous.get("raw_value"),
                "after_raw": current.get("raw_value"),
            }
        )
    return changes


def classify_timeline_change(
    previous_state: dict[str, Any] | None,
    current_state: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    if previous_state is None:
        return (
            "neutral",
            [
                {
                    "record_type": "snapshot",
                    "label": "Initial snapshot",
                    "direction": "neutral",
                    "reason": "This is the first saved DNS monitoring state for the domain.",
                    "before_value": None,
                    "after_value": "initial_snapshot",
                    "before_raw": None,
                    "after_raw": None,
                }
            ],
        )
    previous_snapshot = _snapshot_state(previous_state) or {"dmarc": {}, "spf": {}, "dkim": []}
    current_snapshot = _snapshot_state(current_state) or {"dmarc": {}, "spf": {}, "dkim": []}

    changes = []
    changes.extend(_diff_dmarc(previous_snapshot.get("dmarc") or {}, current_snapshot.get("dmarc") or {}))
    changes.extend(_diff_spf(previous_snapshot.get("spf") or {}, current_snapshot.get("spf") or {}))
    changes.extend(_diff_dkim(previous_snapshot.get("dkim") or [], current_snapshot.get("dkim") or []))

    if any(change["direction"] == "degraded" for change in changes):
        return "degraded", changes
    if any(change["direction"] == "improved" for change in changes):
        return "improved", changes
    return "neutral", changes


def _serialize_history_entry(
    *,
    history_id: str,
    changed_at: str,
    summary: str,
    previous_state: dict[str, Any] | None,
    current_state: dict[str, Any],
) -> dict[str, Any]:
    overall_direction, changes = classify_timeline_change(previous_state, current_state)
    return {
        "id": history_id,
        "changed_at": changed_at,
        "summary": summary,
        "overall_direction": overall_direction,
        "changes": changes,
        "previous_state": previous_state,
        "current_state": current_state,
    }


def get_monitoring_status(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    status, domain = get_visible_domain(config, domain_id=domain_id, actor=actor)
    if status != "ok" or domain is None:
        return status, None

    conn = get_connection(config.database_path)
    try:
        selectors = _load_selectors(conn, domain_id=domain_id)
        current_state = _load_current_state(conn, domain_id=domain_id)
        history = _load_history(conn, domain_id=domain_id, limit=3)
    finally:
        conn.close()

    return "ok", {
        "domain": domain,
        "dkim_selectors": selectors,
        "current_state": current_state,
        "history": history,
    }


def get_monitoring_timeline(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    status, domain = get_visible_domain(config, domain_id=domain_id, actor=actor)
    if status != "ok" or domain is None:
        return status, None

    conn = get_connection(config.database_path)
    try:
        history = _load_history(conn, domain_id=domain_id, limit=200)
    finally:
        conn.close()

    return "ok", {
        "domain": domain,
        "last_checked_at": domain.get("monitoring_last_checked_at"),
        "history": history,
    }


def update_monitoring_settings(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
    enabled: bool,
    dkim_selectors: list[str],
) -> tuple[str, dict[str, Any] | None]:
    status, domain = get_visible_domain(config, domain_id=domain_id, actor=actor, require_admin=True)
    if status != "ok" or domain is None:
        return status, None

    selectors = _normalize_selectors(dkim_selectors)
    next_check_at = _now_iso() if enabled else None
    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """UPDATE domains
               SET monitoring_enabled = ?, monitoring_next_check_at = ?
               WHERE id = ?""",
            (1 if enabled else 0, next_check_at, domain_id),
        )
        conn.execute("DELETE FROM domain_monitoring_dkim_selectors WHERE domain_id = ?", (domain_id,))
        for selector in selectors:
            conn.execute(
                """INSERT INTO domain_monitoring_dkim_selectors (domain_id, selector, added_at)
                   VALUES (?, ?, ?)""",
                (domain_id, selector, _now_iso()),
            )
        conn.commit()
    finally:
        conn.close()

    return get_monitoring_status(config, domain_id=domain_id, actor=actor)


def _has_inflight_monitoring_job(conn, *, domain_id: str) -> bool:
    row = conn.execute(
        """SELECT 1
           FROM domain_maintenance_jobs
           WHERE domain_id = ? AND action = ? AND state IN (?, ?)
           LIMIT 1""",
        (domain_id, ACTION_CHECK_DNS_MONITORING, STATE_QUEUED, STATE_PROCESSING),
    ).fetchone()
    return row is not None


def _interval_is_too_recent(last_triggered_at: str | None) -> bool:
    last_triggered = _parse_iso8601(last_triggered_at)
    if not last_triggered:
        return False
    return (_now() - last_triggered).total_seconds() < MIN_TRIGGER_INTERVAL_SECONDS


def enqueue_monitoring_check(
    config: Config,
    *,
    domain_id: str,
    actor: dict[str, Any],
    source: str,
) -> tuple[str, dict[str, Any] | None]:
    require_admin = actor.get("type") != "api_key"
    status, domain = get_visible_domain(config, domain_id=domain_id, actor=actor, require_admin=require_admin)
    if status != "ok" or domain is None:
        return status, None

    conn = get_connection(config.database_path)
    try:
        row = conn.execute(
            "SELECT monitoring_last_triggered_at FROM domains WHERE id = ?",
            (domain_id,),
        ).fetchone()
        last_triggered_at = row[0] if row else None
        if _interval_is_too_recent(last_triggered_at):
            return "suppressed_recently", {"state": "suppressed_recently"}

        if _has_inflight_monitoring_job(conn, domain_id=domain_id):
            conn.execute(
                "UPDATE domains SET monitoring_last_triggered_at = ? WHERE id = ?",
                (_now_iso(), domain_id),
            )
            conn.commit()
            return "queued", {"state": "queued"}

        job_id = f"dmjob_{uuid.uuid4().hex[:14]}"
        submitted_at = _now_iso()
        conn.execute(
            """INSERT INTO domain_maintenance_jobs
               (id, domain_id, domain_name, action, actor_user_id, actor_api_key_id, submitted_at, state, reports_scanned, reports_skipped, records_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
            (
                job_id,
                domain_id,
                domain["name"],
                ACTION_CHECK_DNS_MONITORING,
                actor.get("id") if actor.get("type") != "api_key" else None,
                actor.get("key_id") if actor.get("type") == "api_key" else None,
                submitted_at,
                STATE_QUEUED,
            ),
        )
        conn.execute(
            "UPDATE domains SET monitoring_last_triggered_at = ? WHERE id = ?",
            (submitted_at, domain_id),
        )
        conn.commit()
    finally:
        conn.close()

    _write_audit_event(
        config.database_path,
        action_type="domain_monitoring_check_enqueued",
        outcome="success",
        actor_user_id=actor.get("id") if actor.get("type") != "api_key" else None,
        actor_api_key_id=actor.get("key_id") if actor.get("type") == "api_key" else None,
        summary=f"Enqueued DNS monitoring check for {domain['name']} via {source}",
    )
    return "queued", {"state": "queued"}


def enqueue_due_monitoring_jobs(config: Config) -> int:
    now_iso = _now_iso()
    conn = get_connection(config.database_path)
    try:
        rows = conn.execute(
            """SELECT id, name
               FROM domains
               WHERE status = 'active'
                 AND monitoring_enabled = 1
                 AND (monitoring_next_check_at IS NULL OR monitoring_next_check_at <= ?)
               ORDER BY COALESCE(monitoring_next_check_at, created_at), id""",
            (now_iso,),
        ).fetchall()
        count = 0
        for domain_id, domain_name in rows:
            if _has_inflight_monitoring_job(conn, domain_id=domain_id):
                continue
            submitted_at = _now_iso()
            conn.execute(
                """INSERT INTO domain_maintenance_jobs
                   (id, domain_id, domain_name, action, actor_user_id, actor_api_key_id, submitted_at, state, reports_scanned, reports_skipped, records_updated)
                   VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, 0, 0, 0)""",
                (
                    f"dmjob_{uuid.uuid4().hex[:14]}",
                    domain_id,
                    domain_name,
                    ACTION_CHECK_DNS_MONITORING,
                    submitted_at,
                    STATE_QUEUED,
                ),
            )
            conn.execute(
                "UPDATE domains SET monitoring_last_triggered_at = ? WHERE id = ?",
                (submitted_at, domain_id),
            )
            count += 1
        conn.commit()
        return count
    finally:
        conn.close()


def _resolve_txt_records(config: Config, host: str) -> tuple[list[str], int | None, str, str | None]:
    if dns is None:
        return [], None, DNS_RESULT_ERROR, "dnspython_not_installed"
    try:
        resolver = dns.resolver.Resolver(configure=not bool(config.dns_nameservers))
        if config.dns_nameservers:
            resolver.nameservers = list(config.dns_nameservers)
        resolver.timeout = config.dns_timeout_seconds
        resolver.lifetime = config.dns_timeout_seconds
        answers = resolver.resolve(host, "TXT")
        records = []
        for answer in answers:
            strings = getattr(answer, "strings", None)
            if strings:
                records.append(b"".join(strings).decode("utf-8", errors="replace"))
            else:
                records.append(str(answer).strip('"'))
        ttl = getattr(getattr(answers, "rrset", None), "ttl", None)
        return records, ttl, DNS_RESULT_OK, None
    except Exception as exc:
        if dns is not None and isinstance(exc, (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer)):
            return [], None, DNS_RESULT_MISSING, None
        return [], None, DNS_RESULT_ERROR, str(exc)


def _first_record_matching_prefix(records: list[str], prefix: str) -> str | None:
    prefix_lower = prefix.lower()
    for record in records:
        if record.strip().lower().startswith(prefix_lower):
            return record.strip()
    return None


def _parse_tag_value_record(record: str | None) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not record:
        return parsed
    for part in record.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        parsed[key.strip().lower()] = value.strip()
    return parsed


def _summarize_dmarc(parsed: dict[str, str]) -> tuple[str, str]:
    policy = parsed.get("p", "none") or "none"
    sub_policy = parsed.get("sp") or policy
    pct = parsed.get("pct", "100") or "100"
    adkim = parsed.get("adkim", "r") or "r"
    aspf = parsed.get("aspf", "r") or "r"
    summary = f"DMARC policy {policy}, subdomain policy {sub_policy}, applied to {pct}% of mail."
    explanation = (
        f"DMARC is configured to {policy} mail that fails alignment checks. "
        f"Subdomains use {sub_policy}. Alignment is DKIM={adkim} and SPF={aspf}. "
        f"Aggregate reports {'are' if parsed.get('rua') else 'are not'} configured."
    )
    return summary, explanation


def _summarize_spf(record: str | None) -> tuple[dict[str, Any], str, str]:
    value = record or ""
    mechanisms = [part for part in value.split() if part and not part.lower().startswith("v=spf1")]
    includes = [part for part in mechanisms if part.startswith(("include:", "ip4:", "ip6:", "a", "mx", "exists:"))]
    qualifier = "neutral"
    if value.strip().endswith("-all"):
        qualifier = "fail"
    elif value.strip().endswith("~all"):
        qualifier = "softfail"
    elif value.strip().endswith("?all"):
        qualifier = "neutral"
    elif value.strip().endswith("+all"):
        qualifier = "allow_all"
    summary = f"SPF ends with {qualifier} and explicitly allows {len(includes)} mechanism(s)."
    explanation = (
        f"SPF lists the systems that may send mail as this domain. "
        f"This record currently allows mail through {', '.join(includes[:5]) or 'no explicit sender mechanisms'} "
        f"and ends with {qualifier} handling for everything else."
    )
    return {"qualifier": qualifier, "includes": includes[:10]}, summary, explanation


def _summarize_dkim(selector: str, record: str | None) -> tuple[dict[str, Any], str, str]:
    parsed = _parse_tag_value_record(record)
    key_type = parsed.get("k", "rsa") or "rsa"
    has_key = bool(parsed.get("p"))
    summary = f"Selector {selector} is {'present' if has_key else 'missing'}."
    explanation = (
        f"DKIM selector {selector} {'publishes' if has_key else 'does not publish'} a DNS public key. "
        f"Key type is {key_type}."
    )
    return {"selector": selector, "key_type": key_type, "has_key": has_key}, summary, explanation


def _build_state_for_domain(config: Config, *, domain_name: str, selectors: list[str]) -> tuple[str, dict[str, Any] | None, int | None, str | None]:
    dmarc_host = f"_dmarc.{domain_name}"
    dmarc_records, dmarc_ttl, dmarc_result, dmarc_error = _resolve_txt_records(config, dmarc_host)
    spf_records, spf_ttl, spf_result_type, spf_error = _resolve_txt_records(config, domain_name)

    errors = []
    if dmarc_result == DNS_RESULT_ERROR and dmarc_error:
        errors.append(_format_lookup_error(dmarc_host, dmarc_error) or dmarc_error)
    if spf_result_type == DNS_RESULT_ERROR and spf_error:
        errors.append(_format_lookup_error(domain_name, spf_error) or spf_error)

    dmarc_record = _first_record_matching_prefix(dmarc_records, "v=dmarc1")
    dmarc_tags = _parse_tag_value_record(dmarc_record)
    dmarc_summary, dmarc_explanation = _summarize_dmarc(dmarc_tags)

    spf_record = _first_record_matching_prefix(spf_records, "v=spf1")
    spf_parsed, spf_summary, spf_explanation = _summarize_spf(spf_record)

    dkim_states = []
    dkim_records_raw = []
    ttl_candidates = [ttl for ttl in (dmarc_ttl, spf_ttl) if ttl]
    for selector in selectors:
        host = f"{selector}._domainkey.{domain_name}"
        records, ttl, result_type, error = _resolve_txt_records(config, host)
        record = _first_record_matching_prefix(records, "v=dkim1")
        parsed, summary, explanation = _summarize_dkim(selector, record)
        ttl_candidates.extend([ttl] if ttl else [])
        if result_type == DNS_RESULT_ERROR and error:
            errors.append(_format_lookup_error(selector, error) or error)
        dkim_record_state = {
            "status": DNS_RESULT_OK if record else (DNS_RESULT_ERROR if result_type == DNS_RESULT_ERROR else DNS_RESULT_MISSING),
            "host": host,
            "raw_value": record,
            "parsed": parsed,
            "summary": summary,
            "explanation": explanation,
            "ttl_seconds": ttl,
        }
        dkim_states.append(dkim_record_state)
        dkim_records_raw.append({"selector": selector, "host": host, "raw_value": record, "ttl_seconds": ttl})

    overall_error = "; ".join(errors) if errors else None
    if overall_error:
        return DNS_RESULT_ERROR, None, None, overall_error
    state = {
        "dmarc": {
            "status": DNS_RESULT_OK if dmarc_record else (DNS_RESULT_ERROR if dmarc_result == DNS_RESULT_ERROR else DNS_RESULT_MISSING),
            "host": dmarc_host,
            "raw_value": dmarc_record,
            "parsed": dmarc_tags,
            "summary": dmarc_summary,
            "explanation": dmarc_explanation,
            "ttl_seconds": dmarc_ttl,
        },
        "spf": {
            "status": DNS_RESULT_OK if spf_record else (DNS_RESULT_ERROR if spf_result_type == DNS_RESULT_ERROR else DNS_RESULT_MISSING),
            "host": domain_name,
            "raw_value": spf_record,
            "parsed": spf_parsed,
            "summary": spf_summary,
            "explanation": spf_explanation,
            "ttl_seconds": spf_ttl,
        },
        "dkim": dkim_states,
    }
    interval = _clamp_interval(min(ttl_candidates) if ttl_candidates else None, config.dns_monitor_default_interval_seconds)
    return DNS_RESULT_OK, state, interval, None


def _history_summary(previous_state: dict[str, Any] | None, current_state: dict[str, Any], error_summary: str | None) -> str:
    if previous_state is None:
        return "Initial DNS monitoring snapshot recorded."
    _overall_direction, changes = classify_timeline_change(previous_state, current_state)
    change_labels = []
    for change in changes:
        label = str(change.get("label") or change.get("record_type") or "DNS change")
        if label not in change_labels:
            change_labels.append(label)
    if error_summary and not changes:
        change_labels.append("Lookup status changed")
    return ", ".join(change_labels) if change_labels else "DNS monitoring snapshot updated."


def _states_equal(previous_state: dict[str, Any] | None, current_state: dict[str, Any]) -> bool:
    if previous_state is None:
        return False
    return json.dumps(_snapshot_state(previous_state), sort_keys=True) == json.dumps(_snapshot_state(current_state), sort_keys=True)


def run_monitoring_job(config: Config, *, job_id: str) -> dict[str, int]:
    conn = get_connection(config.database_path)
    try:
        job_row = conn.execute(
            "SELECT domain_id, domain_name, actor_user_id, actor_api_key_id FROM domain_maintenance_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not job_row:
            raise ValueError("job_not_found")
        domain_row = conn.execute(
            """SELECT monitoring_enabled, status, monitoring_failure_active
               FROM domains
               WHERE id = ?""",
            (job_row[0],),
        ).fetchone()
        selectors = _load_selectors(conn, domain_id=job_row[0])
        previous_state = _load_current_state(conn, domain_id=job_row[0])
    finally:
        conn.close()

    if not domain_row or domain_row[1] != "active" or domain_row[0] != 1:
        return {"reports_scanned": 0, "reports_skipped": 1, "records_updated": 0}

    checked_at = _now_iso()
    result_type, current_state, interval_seconds, error_summary = _build_state_for_domain(
        config,
        domain_name=job_row[1],
        selectors=selectors,
    )
    if interval_seconds is None:
        interval_seconds = _clamp_interval(None, config.dns_monitor_default_interval_seconds)
    next_check_at = (_now().timestamp() + interval_seconds)
    next_check_iso = datetime.fromtimestamp(next_check_at, tz=timezone.utc).isoformat()

    if result_type == DNS_RESULT_ERROR or current_state is None:
        conn = get_connection(config.database_path)
        try:
            previous_failure_active = 1 if domain_row[2] else 0
            conn.execute(
                """UPDATE domains
                   SET monitoring_next_check_at = ?,
                       monitoring_failure_active = 1,
                       monitoring_last_failure_at = ?,
                       monitoring_last_failure_summary = ?
                   WHERE id = ?""",
                (
                    next_check_iso,
                    checked_at,
                    error_summary,
                    job_row[0],
                ),
            )
            conn.commit()
        finally:
            conn.close()

        if not previous_failure_active:
            _write_audit_event(
                config.database_path,
                action_type="domain_monitoring_check_failed",
                outcome="failure",
                actor_user_id=job_row[2],
                actor_api_key_id=job_row[3],
                summary=f"DNS monitoring lookup failed for {job_row[1]}: {error_summary}",
            )
            logger.warning("DNS monitoring lookup failed for %s: %s", job_row[1], error_summary)
        return {
            "reports_scanned": 0,
            "reports_skipped": 1,
            "records_updated": 0,
        }

    changed = not _states_equal(previous_state, current_state)
    summary = _history_summary(previous_state, current_state, error_summary)

    conn = get_connection(config.database_path)
    try:
        conn.execute(
            """INSERT INTO domain_monitoring_current_state
               (domain_id, checked_at, observed_state_json, dmarc_record_raw, spf_record_raw, dkim_records_json, ttl_seconds, error_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(domain_id) DO UPDATE SET
                   checked_at = excluded.checked_at,
                   observed_state_json = excluded.observed_state_json,
                   dmarc_record_raw = excluded.dmarc_record_raw,
                   spf_record_raw = excluded.spf_record_raw,
                   dkim_records_json = excluded.dkim_records_json,
                   ttl_seconds = excluded.ttl_seconds,
                   error_summary = excluded.error_summary""",
            (
                job_row[0],
                checked_at,
                json.dumps(current_state, sort_keys=True),
                current_state["dmarc"].get("raw_value"),
                current_state["spf"].get("raw_value"),
                json.dumps(current_state["dkim"], sort_keys=True),
                interval_seconds,
                error_summary,
            ),
        )
        if changed:
            conn.execute(
                """INSERT INTO domain_monitoring_history
                   (id, domain_id, changed_at, summary, previous_state_json, current_state_json, dmarc_record_raw, spf_record_raw, dkim_records_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"{HISTORY_ID_PREFIX}{uuid.uuid4().hex[:14]}",
                    job_row[0],
                    checked_at,
                    summary,
                    json.dumps(previous_state, sort_keys=True) if previous_state else None,
                    json.dumps(current_state, sort_keys=True),
                    current_state["dmarc"].get("raw_value"),
                    current_state["spf"].get("raw_value"),
                    json.dumps(current_state["dkim"], sort_keys=True),
                ),
            )
        failure_active = 1 if error_summary else 0
        previous_failure_active = 1 if domain_row[2] else 0
        conn.execute(
            """UPDATE domains
               SET monitoring_last_checked_at = ?,
                   monitoring_next_check_at = ?,
                   monitoring_last_change_at = CASE WHEN ? THEN ? ELSE monitoring_last_change_at END,
                   monitoring_failure_active = ?,
                   monitoring_last_failure_at = CASE WHEN ? THEN ? ELSE NULL END,
                   monitoring_last_failure_summary = CASE WHEN ? THEN ? ELSE NULL END
               WHERE id = ?""",
            (
                checked_at,
                next_check_iso,
                1 if changed else 0,
                checked_at,
                failure_active,
                failure_active,
                checked_at,
                failure_active,
                error_summary,
                job_row[0],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    if previous_failure_active:
        logger.info("DNS monitoring recovered for %s", job_row[1])

    return {
        "reports_scanned": 1,
        "reports_skipped": 0,
        "records_updated": 1 if changed else 0,
    }
