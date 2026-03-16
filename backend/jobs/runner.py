"""In-process job runner: claim queued/processing job, process items, update state."""

import base64
import gzip
import logging
import uuid
from datetime import datetime, timezone

from backend.config.schema import Config
from backend.services import domain_service
from backend.storage.sqlite import get_connection
from backend.auth.user_lookup import get_user_by_id
from backend.ingest.aggregate_parser import parse_aggregate
from backend.ingest.forensic_parser import parse_forensic
from backend.ingest.domain_check import can_ingest_for_domain
from backend.ingest.dedupe import is_duplicate, is_forensic_duplicate
from backend.ingest.dns_resolver import resolve_ip
from backend.ingest.mime_parser import is_mime_message, extract_attachments
from backend.archive.filesystem import FilesystemArchiveStorage

logger = logging.getLogger(__name__)

MAX_DECOMPRESSED_BYTES = 10 * 1024 * 1024  # 10 MB
AGGREGATE_ID_PREFIX = "agg_"
FORENSIC_ID_PREFIX = "for_"


def _get_archive_storage(config: Config) -> FilesystemArchiveStorage | None:
    """Return archive storage instance if configured, else None."""
    if config.archive_storage_path:
        return FilesystemArchiveStorage(config.archive_storage_path)
    return None


def run_one_job(config: Config) -> bool:
    """Claim and process one job (queued or processing). Return True if a job was processed."""
    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            "SELECT id, actor_user_id, actor_api_key_id FROM ingest_jobs WHERE state IN ('queued', 'processing') ORDER BY submitted_at LIMIT 1"
        )
        row = cur.fetchone()
        if not row:
            return False
        job_id, actor_user_id, actor_api_key_id = row
        conn.execute("UPDATE ingest_jobs SET state = 'processing', started_at = ? WHERE id = ?", (datetime.now(timezone.utc).isoformat(), job_id))
        conn.commit()
    finally:
        conn.close()

    key_domain_ids = None
    if actor_api_key_id:
        conn = get_connection(config.database_path)
        try:
            cur = conn.execute(
                "SELECT domain_id FROM api_key_domains WHERE api_key_id = ?",
                (actor_api_key_id,),
            )
            key_domain_ids = frozenset(r[0] for r in cur.fetchall())
        finally:
            conn.close()
        actor_user_id = None
        actor_role = None
    else:
        user = get_user_by_id(config.database_path, actor_user_id)
        actor_role = user["role"] if user else "viewer"

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, raw_content, raw_content_transfer_encoding, raw_content_encoding FROM ingest_job_items WHERE job_id = ? ORDER BY sequence_no""",
            (job_id,),
        )
        items = cur.fetchall()
    finally:
        conn.close()

    archive_storage = _get_archive_storage(config)
    now_iso = datetime.now(timezone.utc).isoformat()
    has_failure = False
    for item_id, raw_content, transfer_enc, content_enc in items:
        status, reason, domain_detected, report_type = _process_one_item(
            config, job_id, item_id, raw_content or "", transfer_enc, content_enc,
            actor_user_id=actor_user_id, actor_role=actor_role, key_domain_ids=key_domain_ids,
            archive_storage=archive_storage,
        )
        conn = get_connection(config.database_path)
        try:
            conn.execute(
                """UPDATE ingest_job_items SET report_type_detected = ?, domain_detected = ?, status = ?, status_reason = ?, started_at = ?, completed_at = ? WHERE id = ?""",
                (report_type, domain_detected, status, reason or None, now_iso, now_iso, item_id),
            )
            conn.commit()
        finally:
            conn.close()
        if status in ("rejected", "invalid"):
            has_failure = True

    conn = get_connection(config.database_path)
    try:
        new_state = "completed_with_warnings" if has_failure else "completed"
        conn.execute(
            "UPDATE ingest_jobs SET state = ?, completed_at = ? WHERE id = ?",
            (new_state, datetime.now(timezone.utc).isoformat(), job_id),
        )
        conn.commit()
    finally:
        conn.close()
    return True


def _process_one_item(
    config: Config,
    job_id: str,
    item_id: str,
    raw_content: str,
    transfer_enc: str | None,
    content_enc: str | None,
    actor_user_id: str | None = None,
    actor_role: str | None = None,
    key_domain_ids: frozenset[str] | None = None,
    archive_storage: FilesystemArchiveStorage | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    """Decode, decompress, parse, check domain, dedupe, persist, archive. Return (status, reason, domain_detected, report_type)."""
    try:
        data = raw_content.encode("utf-8") if isinstance(raw_content, str) else raw_content
    except Exception:
        return "invalid", "encoding", None, None
    if transfer_enc and str(transfer_enc).lower() == "base64":
        try:
            data = base64.b64decode(data, validate=True)
        except Exception:
            return "invalid", "base64", None, None
    if content_enc and str(content_enc).lower() == "gzip":
        try:
            data = gzip.decompress(data)
            if len(data) > MAX_DECOMPRESSED_BYTES:
                return "invalid", "size", None, None
        except Exception:
            return "invalid", "decompress", None, None

    if is_mime_message(data):
        return _process_mime_message(
            config, item_id, data, actor_user_id, actor_role, key_domain_ids, archive_storage
        )

    return _process_raw_report(config, item_id, data, actor_user_id, actor_role, key_domain_ids, archive_storage)


def _process_raw_report(
    config: Config,
    item_id: str,
    data: bytes,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    """Try to parse data as aggregate or forensic XML. Return (status, reason, domain, report_type)."""
    parsed_agg = parse_aggregate(data)
    if parsed_agg:
        return _process_aggregate(config, item_id, parsed_agg, actor_user_id, actor_role, key_domain_ids, archive_storage, data)

    parsed_for = parse_forensic(data)
    if parsed_for:
        return _process_forensic(config, item_id, parsed_for, actor_user_id, actor_role, key_domain_ids, archive_storage, data)

    return "invalid", "parse", None, None


def _process_mime_message(
    config: Config,
    item_id: str,
    data: bytes,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
) -> tuple[str, str | None, str | None, str | None]:
    """Extract attachments from MIME message and process each. Return best outcome."""
    attachments = extract_attachments(data)
    if not attachments:
        return "invalid", "no_attachments", None, "email"

    results: list[tuple[str, str | None, str | None, str | None]] = []
    for att in attachments:
        att_data = att["content"]
        att_encoding = att.get("content_encoding")
        if att_encoding == "gzip":
            try:
                att_data = gzip.decompress(att_data)
                if len(att_data) > MAX_DECOMPRESSED_BYTES:
                    results.append(("invalid", "size", None, None))
                    continue
            except Exception:
                results.append(("invalid", "decompress", None, None))
                continue
        result = _process_raw_report(config, item_id, att_data, actor_user_id, actor_role, key_domain_ids, archive_storage)
        results.append(result)

    if not results:
        return "invalid", "no_attachments", None, "email"

    accepted = [r for r in results if r[0] == "accepted"]
    if accepted:
        domains = [r[2] for r in accepted if r[2]]
        domain_str = domains[0] if len(domains) == 1 else ("multiple" if len(domains) > 1 else None)
        types = [r[3] for r in accepted if r[3]]
        type_str = types[0] if len(set(types)) == 1 else ("mixed" if types else None)
        return "accepted", None, domain_str, type_str

    duplicates = [r for r in results if r[0] == "duplicate"]
    if duplicates:
        return duplicates[0]

    rejected = [r for r in results if r[0] == "rejected"]
    if rejected:
        return rejected[0]

    return results[0]


def _process_aggregate(
    config: Config,
    item_id: str,
    parsed: dict,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    raw_data: bytes | None = None,
) -> tuple[str, str | None, str | None, str]:
    """Check domain auth, dedupe, persist aggregate report, archive raw. Return (status, reason, domain, 'aggregate')."""
    domain = parsed["domain"]
    if key_domain_ids is not None:
        allowed, _reason = can_ingest_for_domain(config, domain, key_domain_ids=key_domain_ids)
    else:
        allowed, _reason = can_ingest_for_domain(config, domain, actor_user_id=actor_user_id, actor_role=actor_role)
    if not allowed:
        return "rejected", None, domain, "aggregate"
    if is_duplicate(config, parsed["report_id"], domain):
        return "duplicate", None, domain, "aggregate"
    conn = get_connection(config.database_path)
    try:
        agg_id = f"{AGGREGATE_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO aggregate_reports (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (agg_id, parsed["report_id"], parsed["org_name"] or "", domain, parsed["date_begin"], parsed["date_end"], item_id, created_at),
        )
        for rec in parsed.get("records") or []:
            rec_id = f"rec_{uuid.uuid4().hex[:12]}"
            resolved_name, resolved_name_domain = resolve_ip(rec.get("source_ip"))
            conn.execute(
                """INSERT INTO aggregate_report_records
                   (id, aggregate_report_id, source_ip, resolved_name, resolved_name_domain, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec_id,
                    agg_id,
                    rec.get("source_ip"),
                    resolved_name,
                    resolved_name_domain,
                    rec.get("count") or 0,
                    rec.get("disposition"),
                    rec.get("dkim_result"),
                    rec.get("spf_result"),
                    rec.get("header_from"),
                    rec.get("envelope_from"),
                    rec.get("envelope_to"),
                ),
            )
        conn.commit()
    except Exception as e:
        logger.exception("aggregate_reports insert: %s", e)
        return "invalid", "persist", domain, "aggregate"
    finally:
        conn.close()

    if archive_storage and raw_data:
        try:
            archive_storage.store(domain, parsed["report_id"], raw_data)
        except Exception as e:
            logger.warning("Failed to archive aggregate report %s: %s", parsed["report_id"], e)

    return "accepted", None, domain, "aggregate"


def _process_forensic(
    config: Config,
    item_id: str,
    parsed: dict,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    raw_data: bytes | None = None,
) -> tuple[str, str | None, str | None, str]:
    """Check domain auth, dedupe, persist forensic report, archive raw. Return (status, reason, domain, 'forensic')."""
    domain = parsed["domain"]
    if key_domain_ids is not None:
        allowed, _reason = can_ingest_for_domain(config, domain, key_domain_ids=key_domain_ids)
    else:
        allowed, _reason = can_ingest_for_domain(config, domain, actor_user_id=actor_user_id, actor_role=actor_role)
    if not allowed:
        return "rejected", None, domain, "forensic"
    if is_forensic_duplicate(config, parsed["report_id"], domain):
        return "duplicate", None, domain, "forensic"
    conn = get_connection(config.database_path)
    try:
        for_id = f"{FORENSIC_ID_PREFIX}{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        resolved_name, resolved_name_domain = resolve_ip(parsed.get("source_ip"))
        conn.execute(
            """INSERT INTO forensic_reports
               (id, report_id, domain, source_ip, resolved_name, resolved_name_domain, arrival_time, org_name, header_from, envelope_from, envelope_to, spf_result, dkim_result, dmarc_result, failure_type, job_item_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                for_id,
                parsed["report_id"],
                domain,
                parsed.get("source_ip"),
                resolved_name,
                resolved_name_domain,
                parsed.get("arrival_time"),
                parsed.get("org_name") or "",
                parsed.get("header_from"),
                parsed.get("envelope_from"),
                parsed.get("envelope_to"),
                parsed.get("spf_result"),
                parsed.get("dkim_result"),
                parsed.get("dmarc_result"),
                parsed.get("failure_type"),
                item_id,
                created_at,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.exception("forensic_reports insert: %s", e)
        return "invalid", "persist", domain, "forensic"
    finally:
        conn.close()

    if archive_storage and raw_data:
        try:
            archive_storage.store(domain, parsed["report_id"], raw_data)
        except Exception as e:
            logger.warning("Failed to archive forensic report %s: %s", parsed["report_id"], e)

    return "accepted", None, domain, "forensic"


def run_loop(config: Config, stop_event: object | None = None, interval_seconds: float = 2.0) -> None:
    """Loop run_one_job until stop_event is set. Used from background thread."""
    import time
    while stop_event is None or not getattr(stop_event, "is_set", lambda: False)():
        try:
            run_one_job(config)
        except Exception as e:
            logger.exception("job runner: %s", e)
        try:
            domain_service.run_retention_purge(config)
        except Exception as e:
            logger.exception("retention purge: %s", e)
        if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
            break
        time.sleep(interval_seconds)
