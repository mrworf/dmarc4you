"""In-process job runner: claim queued/processing job, process items, update state."""

import base64
import gzip
import json
import logging
import uuid
from datetime import datetime, timezone

from backend.archive.filesystem import FilesystemArchiveStorage
from backend.auth.user_lookup import get_user_by_id
from backend.config.schema import Config
from backend.ingest.aggregate_parser import parse_aggregate
from backend.ingest.compression import ZipExtractionError, extract_zip_members
from backend.ingest.forensic_parser import parse_forensic
from backend.ingest.domain_check import can_ingest_for_domain
from backend.ingest.dedupe import is_duplicate, is_forensic_duplicate
from backend.ingest.dns_resolver import resolve_ip
from backend.ingest.geoip import build_geoip_provider
from backend.ingest.mime_parser import is_mime_message, extract_attachments
from backend.services import domain_service
from backend.storage.sqlite import get_connection

logger = logging.getLogger(__name__)

MAX_DECOMPRESSED_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ZIP_MEMBERS = 20
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
    geoip_provider = build_geoip_provider(config)
    now_iso = datetime.now(timezone.utc).isoformat()
    has_failure = False
    for item_id, raw_content, transfer_enc, content_enc in items:
        status, reason, domain_detected, report_type = _process_one_item(
            config, job_id, item_id, raw_content or "", transfer_enc, content_enc,
            actor_user_id=actor_user_id, actor_role=actor_role, key_domain_ids=key_domain_ids,
            archive_storage=archive_storage,
            geoip_provider=geoip_provider,
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
    geoip_provider=None,
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
    return _process_blob(
        config,
        item_id,
        data,
        _normalize_content_encoding(content_enc),
        actor_user_id,
        actor_role,
        key_domain_ids,
        archive_storage,
        geoip_provider,
        allow_zip=True,
    )


def _process_raw_report(
    config: Config,
    item_id: str,
    data: bytes,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    geoip_provider=None,
) -> tuple[str, str | None, str | None, str | None]:
    """Try to parse data as aggregate or forensic XML. Return (status, reason, domain, report_type)."""
    parsed_agg = parse_aggregate(data)
    if parsed_agg:
        return _process_aggregate(
            config,
            item_id,
            parsed_agg,
            actor_user_id,
            actor_role,
            key_domain_ids,
            archive_storage,
            data,
            geoip_provider,
        )

    parsed_for = parse_forensic(data)
    if parsed_for:
        return _process_forensic(
            config,
            item_id,
            parsed_for,
            actor_user_id,
            actor_role,
            key_domain_ids,
            archive_storage,
            data,
            geoip_provider,
        )

    return "invalid", "parse", None, None


def _process_blob(
    config: Config,
    item_id: str,
    data: bytes,
    content_encoding: str | None,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    geoip_provider=None,
    *,
    allow_zip: bool,
) -> tuple[str, str | None, str | None, str | None]:
    normalized_encoding = _normalize_content_encoding(content_encoding)
    if normalized_encoding == "gzip":
        try:
            data = gzip.decompress(data)
            if len(data) > MAX_DECOMPRESSED_BYTES:
                return "invalid", "size", None, None
        except Exception:
            return "invalid", "decompress", None, None
    elif normalized_encoding == "zip":
        if not allow_zip:
            return "invalid", "nested_zip", None, "zip"
        try:
            members = extract_zip_members(
                data,
                max_members=MAX_ZIP_MEMBERS,
                max_member_bytes=MAX_DECOMPRESSED_BYTES,
                max_total_bytes=MAX_DECOMPRESSED_BYTES,
            )
        except ZipExtractionError as exc:
            return "invalid", f"zip_{exc}", None, "zip"
        if not members:
            return "invalid", "zip_no_supported_members", None, "zip"
        results = [
            _process_blob(
                config,
                item_id,
                member["content"],
                _normalize_content_encoding(member.get("content_encoding")),
                actor_user_id,
                actor_role,
                key_domain_ids,
                archive_storage,
                geoip_provider,
                allow_zip=False,
            )
            for member in members
        ]
        return _combine_nested_results(results, default_report_type="zip")

    if is_mime_message(data):
        return _process_mime_message(
            config, item_id, data, actor_user_id, actor_role, key_domain_ids, archive_storage, geoip_provider
        )

    return _process_raw_report(
        config, item_id, data, actor_user_id, actor_role, key_domain_ids, archive_storage, geoip_provider
    )


def _process_mime_message(
    config: Config,
    item_id: str,
    data: bytes,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    geoip_provider=None,
) -> tuple[str, str | None, str | None, str | None]:
    """Extract attachments from MIME message and process each. Return best outcome."""
    attachments = extract_attachments(data)
    if not attachments:
        return "invalid", "no_attachments", None, "email"

    results: list[tuple[str, str | None, str | None, str | None]] = []
    for att in attachments:
        result = _process_blob(
            config,
            item_id,
            att["content"],
            _normalize_content_encoding(att.get("content_encoding")),
            actor_user_id,
            actor_role,
            key_domain_ids,
            archive_storage,
            geoip_provider,
            allow_zip=True,
        )
        results.append(result)

    return _combine_nested_results(results, default_report_type="email")


def _process_aggregate(
    config: Config,
    item_id: str,
    parsed: dict,
    actor_user_id: str | None,
    actor_role: str | None,
    key_domain_ids: frozenset[str] | None,
    archive_storage: FilesystemArchiveStorage | None = None,
    raw_data: bytes | None = None,
    geoip_provider=None,
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
            """INSERT INTO aggregate_reports
               (id, report_id, org_name, domain, date_begin, date_end, job_item_id, created_at,
                contact_email, extra_contact_info, error_messages_json, adkim, aspf, policy_p, policy_sp, policy_pct, policy_fo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                agg_id,
                parsed["report_id"],
                parsed["org_name"] or "",
                domain,
                parsed["date_begin"],
                parsed["date_end"],
                item_id,
                created_at,
                parsed.get("contact_email"),
                parsed.get("extra_contact_info"),
                json.dumps(parsed.get("error_messages") or []),
                parsed.get("adkim"),
                parsed.get("aspf"),
                parsed.get("policy_p"),
                parsed.get("policy_sp"),
                parsed.get("policy_pct"),
                parsed.get("policy_fo"),
            ),
        )
        for rec in parsed.get("records") or []:
            rec_id = f"rec_{uuid.uuid4().hex[:12]}"
            resolved_name, resolved_name_domain = resolve_ip(config, rec.get("source_ip"))
            geo_result = geoip_provider.lookup_country(rec.get("source_ip")) if geoip_provider else None
            conn.execute(
                """INSERT INTO aggregate_report_records
                   (id, aggregate_report_id, source_ip, resolved_name, resolved_name_domain, country_code, country_name, geo_provider, count, disposition, dkim_result, spf_result, header_from, envelope_from, envelope_to)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec_id,
                    agg_id,
                    rec.get("source_ip"),
                    resolved_name,
                    resolved_name_domain,
                    geo_result.country_code if geo_result else None,
                    geo_result.country_name if geo_result else None,
                    geo_result.provider if geo_result else None,
                    rec.get("count") or 0,
                    rec.get("disposition"),
                    rec.get("dkim_result"),
                    rec.get("spf_result"),
                    rec.get("header_from"),
                    rec.get("envelope_from"),
                    rec.get("envelope_to"),
                ),
            )
            for override in rec.get("policy_overrides") or []:
                conn.execute(
                    """INSERT INTO aggregate_record_policy_overrides (id, aggregate_record_id, reason_type, comment)
                       VALUES (?, ?, ?, ?)""",
                    (
                        f"ovr_{uuid.uuid4().hex[:12]}",
                        rec_id,
                        override.get("type"),
                        override.get("comment"),
                    ),
                )
            for auth_result in rec.get("auth_results") or []:
                conn.execute(
                    """INSERT INTO aggregate_record_auth_results
                       (id, aggregate_record_id, auth_method, domain, selector, scope, result, human_result)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        f"auth_{uuid.uuid4().hex[:12]}",
                        rec_id,
                        auth_result.get("auth_method") or "",
                        auth_result.get("domain"),
                        auth_result.get("selector"),
                        auth_result.get("scope"),
                        auth_result.get("result"),
                        auth_result.get("human_result"),
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
    geoip_provider=None,
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
        resolved_name, resolved_name_domain = resolve_ip(config, parsed.get("source_ip"))
        geo_result = geoip_provider.lookup_country(parsed.get("source_ip")) if geoip_provider else None
        conn.execute(
            """INSERT INTO forensic_reports
               (id, report_id, domain, source_ip, resolved_name, resolved_name_domain, country_code, country_name, geo_provider, arrival_time, org_name, header_from, envelope_from, envelope_to, spf_result, dkim_result, dmarc_result, failure_type, job_item_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                for_id,
                parsed["report_id"],
                domain,
                parsed.get("source_ip"),
                resolved_name,
                resolved_name_domain,
                geo_result.country_code if geo_result else None,
                geo_result.country_name if geo_result else None,
                geo_result.provider if geo_result else None,
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


def _combine_nested_results(
    results: list[tuple[str, str | None, str | None, str | None]],
    *,
    default_report_type: str,
) -> tuple[str, str | None, str | None, str | None]:
    if not results:
        return "invalid", f"{default_report_type}_no_supported_members", None, default_report_type
    accepted = [r for r in results if r[0] == "accepted"]
    if accepted:
        domains = [r[2] for r in accepted if r[2]]
        report_types = [r[3] for r in accepted if r[3]]
        domain_detected = domains[0] if len(set(domains)) == 1 and domains else ("multiple" if len(domains) > 1 else None)
        report_type = report_types[0] if len(set(report_types)) == 1 and report_types else ("mixed" if report_types else default_report_type)
        return "accepted", None, domain_detected, report_type
    duplicates = [r for r in results if r[0] == "duplicate"]
    if duplicates:
        return duplicates[0]
    rejected = [r for r in results if r[0] == "rejected"]
    if rejected:
        return rejected[0]
    return results[0]


def _normalize_content_encoding(content_encoding: str | None) -> str | None:
    value = (content_encoding or "").strip().lower()
    if value in {"", "none"}:
        return None
    return value


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
