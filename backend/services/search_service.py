"""Search service: list aggregate reports and records with domain scoping, filters, pagination."""

from datetime import datetime, timezone
import json
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection
from backend.services.dmarc_alignment import backfill_missing_aggregate_alignment, load_record_auth_results
from backend.services.domain_service import list_domains

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

ALLOWED_FILTER_FIELDS = frozenset(
    [
        "spf_result",
        "dkim_result",
        "disposition",
        "source_ip",
        "spf_alignment",
        "dkim_alignment",
        "dmarc_alignment",
    ]
)
ALLOWED_GROUP_FIELDS = {
    "domain": {
        "expr": "COALESCE(ar.domain, '')",
    },
    "org_name": {
        "expr": "COALESCE(ar.org_name, '')",
    },
    "record_date": {
        "expr": "COALESCE(date(ar.date_begin, 'unixepoch'), '')",
    },
    "source_ip": {
        "expr": "COALESCE(rec.source_ip, '')",
    },
    "resolved_name": {
        "expr": "COALESCE(rec.resolved_name, '')",
    },
    "resolved_name_domain": {
        "expr": "COALESCE(rec.resolved_name_domain, '')",
    },
    "disposition": {
        "expr": "COALESCE(rec.disposition, '')",
    },
    "dmarc_alignment": {
        "expr": "COALESCE(rec.dmarc_alignment, '')",
    },
    "dkim_alignment": {
        "expr": "COALESCE(rec.dkim_alignment, '')",
    },
    "spf_alignment": {
        "expr": "COALESCE(rec.spf_alignment, '')",
    },
}
MAX_GROUPING_DEPTH = 4


def _record_date_from_ts(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def _normalize_group_by(group_by: str | None) -> str | None:
    value = (group_by or "").strip()
    return value if value in ALLOWED_GROUP_FIELDS else None


def _normalize_grouping(grouping: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for field in grouping or []:
        value = str(field or "").strip()
        if not value or value not in ALLOWED_GROUP_FIELDS or value in normalized:
            continue
        normalized.append(value)
        if len(normalized) >= MAX_GROUPING_DEPTH:
            break
    return normalized


def _parse_ts(value: str | int | None) -> int | None:
    """Parse from/to to Unix timestamp. Accept int or ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def list_aggregate_reports(
    config: Config,
    current_user: dict[str, Any],
    *,
    domains_param: list[str] | None = None,
    from_ts: str | int | None = None,
    to_ts: str | int | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "date_begin",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    """List aggregate report rows with domain scoping, optional domain/time filter, pagination, sort."""
    allowed_domains = [d["name"] for d in list_domains(config, current_user)]
    if not allowed_domains:
        return {"items": [], "total": 0, "page": max(1, page), "page_size": _cap_page_size(page_size)}

    domain_filter = allowed_domains
    if domains_param:
        domain_filter = [d for d in domains_param if d in allowed_domains]

    from_val = _parse_ts(from_ts)
    to_val = _parse_ts(to_ts)
    page = max(1, page)
    page_size = _cap_page_size(page_size)
    offset = (page - 1) * page_size

    sort_col = "date_begin" if sort_by == "date_begin" else "date_begin"
    sort_order = "DESC" if sort_dir == "desc" else "ASC"

    conn = get_connection(config.database_path)
    try:
        placeholders = ",".join("?" * len(domain_filter))
        where_parts = [f"domain IN ({placeholders})"]
        params: list[Any] = list(domain_filter)
        if from_val is not None:
            where_parts.append("date_end >= ?")
            params.append(from_val)
        if to_val is not None:
            where_parts.append("date_begin <= ?")
            params.append(to_val)
        where_sql = " AND ".join(where_parts)

        cur = conn.execute(
            f"SELECT COUNT(*) FROM aggregate_reports WHERE {where_sql}",
            params,
        )
        total = cur.fetchone()[0]

        cur = conn.execute(
            f"""SELECT id, report_id, org_name, domain, date_begin, date_end, created_at
                FROM aggregate_reports WHERE {where_sql}
                ORDER BY {sort_col} {sort_order}
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        rows = cur.fetchall()
        items = [
            {
                "id": r[0],
                "report_id": r[1],
                "org_name": r[2],
                "domain": r[3],
                "date_begin": r[4],
                "date_end": r[5],
                "record_date": _record_date_from_ts(r[4]),
                "created_at": r[6],
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        conn.close()


def _cap_page_size(size: int) -> int:
    if size < 1:
        return DEFAULT_PAGE_SIZE
    return min(size, MAX_PAGE_SIZE)


def _allowed_domain_names(config: Config, current_user: dict[str, Any]) -> list[str]:
    return [d["name"] for d in list_domains(config, current_user)]


def _resolve_domain_filter(allowed_domains: list[str], domains_param: list[str] | None) -> list[str]:
    if not domains_param:
        return allowed_domains
    return [domain for domain in domains_param if domain in allowed_domains]


def _build_record_where_clause(
    domain_filter: list[str],
    *,
    from_ts: str | int | None,
    to_ts: str | int | None,
    include: dict[str, list[str]] | None,
    exclude: dict[str, list[str]] | None,
    query: str | None,
    path: list[dict[str, str]] | None = None,
) -> tuple[str, list[Any], str]:
    if not domain_filter:
        return "1 = 0", [], ""

    from_val = _parse_ts(from_ts)
    to_val = _parse_ts(to_ts)
    placeholders = ",".join("?" * len(domain_filter))
    where_parts = [f"ar.domain IN ({placeholders})"]
    params: list[Any] = list(domain_filter)

    if from_val is not None:
        where_parts.append("ar.date_end >= ?")
        params.append(from_val)
    if to_val is not None:
        where_parts.append("ar.date_begin <= ?")
        params.append(to_val)

    if include:
        for field, values in include.items():
            filtered_values = [value for value in values if value]
            if field not in ALLOWED_FILTER_FIELDS or not filtered_values:
                continue
            ph = ",".join("?" * len(filtered_values))
            where_parts.append(f"rec.{field} IN ({ph})")
            params.extend(filtered_values)

    if exclude:
        for field, values in exclude.items():
            filtered_values = [value for value in values if value]
            if field not in ALLOWED_FILTER_FIELDS or not filtered_values:
                continue
            ph = ",".join("?" * len(filtered_values))
            where_parts.append(f"(rec.{field} IS NULL OR rec.{field} NOT IN ({ph}))")
            params.extend(filtered_values)

    if path:
        for part in path:
            field = str(part.get("field") or "").strip()
            value = str(part.get("value") or "")
            if field not in ALLOWED_GROUP_FIELDS:
                raise ValueError(f"Unsupported grouping field: {field}")
            where_parts.append(f"{ALLOWED_GROUP_FIELDS[field]['expr']} = ?")
            params.append(value)

    fts_query = _escape_fts_query(query or "")
    fts_join = ""
    if fts_query:
        fts_join = "JOIN aggregate_records_fts fts ON rec.rowid = fts.rowid"
        where_parts.append("aggregate_records_fts MATCH ?")
        params.append(fts_query)

    return " AND ".join(where_parts), params, fts_join


def get_aggregate_report_detail(
    config: Config,
    current_user: dict[str, Any],
    report_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """Get a single aggregate report with all its records.

    Returns (status, report_dict) where status is "ok", "not_found", or "forbidden".
    """
    backfill_missing_aggregate_alignment(config.database_path)
    allowed_domains = [d["name"] for d in list_domains(config, current_user)]

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, report_id, org_name, domain, date_begin, date_end, created_at
               FROM aggregate_reports WHERE id = ?""",
            (report_id,),
        )
        row = cur.fetchone()
        if not row:
            return ("not_found", None)

        report = {
            "id": row[0],
            "report_id": row[1],
            "org_name": row[2],
            "domain": row[3],
            "date_begin": row[4],
            "date_end": row[5],
            "created_at": row[6],
        }

        if report["domain"] not in allowed_domains:
            return ("forbidden", None)

        cur = conn.execute(
            """SELECT id, source_ip, resolved_name, resolved_name_domain, country_code, country_name, geo_provider, count, disposition, dkim_result, spf_result,
                      dkim_alignment, spf_alignment, dmarc_alignment, header_from, envelope_from, envelope_to
               FROM aggregate_report_records WHERE aggregate_report_id = ?
               ORDER BY count DESC""",
            (report_id,),
        )
        records = []
        for r in cur.fetchall():
            record_id = r[0]
            override_cur = conn.execute(
                """SELECT reason_type, comment
                   FROM aggregate_record_policy_overrides
                   WHERE aggregate_record_id = ?
                   ORDER BY id""",
                (record_id,),
            )
            records.append(
                {
                    "id": record_id,
                    "source_ip": r[1],
                    "resolved_name": r[2],
                    "resolved_name_domain": r[3],
                    "country_code": r[4],
                    "country_name": r[5],
                    "geo_provider": r[6],
                    "count": r[7],
                    "disposition": r[8],
                    "dkim_result": r[9],
                    "spf_result": r[10],
                    "dkim_alignment": r[11],
                    "spf_alignment": r[12],
                    "dmarc_alignment": r[13],
                    "header_from": r[14],
                    "envelope_from": r[15],
                    "envelope_to": r[16],
                    "policy_overrides": [
                        {"type": row[0], "comment": row[1]}
                        for row in override_cur.fetchall()
                    ],
                    "auth_results": load_record_auth_results(conn, record_id),
                }
            )
        report["contact_email"] = row_get(report["id"], conn, "contact_email")
        report["extra_contact_info"] = row_get(report["id"], conn, "extra_contact_info")
        report["error_messages"] = _load_json_list(row_get(report["id"], conn, "error_messages_json"))
        report["published_policy"] = {
            "adkim": row_get(report["id"], conn, "adkim"),
            "aspf": row_get(report["id"], conn, "aspf"),
            "p": row_get(report["id"], conn, "policy_p"),
            "sp": row_get(report["id"], conn, "policy_sp"),
            "pct": row_get(report["id"], conn, "policy_pct"),
            "fo": row_get(report["id"], conn, "policy_fo"),
        }
        report["records"] = records
        return ("ok", report)
    finally:
        conn.close()


def get_forensic_report_detail(
    config: Config,
    current_user: dict[str, Any],
    report_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """Get a single forensic report.

    Returns (status, report_dict) where status is "ok", "not_found", or "forbidden".
    """
    allowed_domains = [d["name"] for d in list_domains(config, current_user)]

    conn = get_connection(config.database_path)
    try:
        cur = conn.execute(
            """SELECT id, report_id, domain, source_ip, resolved_name, resolved_name_domain, country_code, country_name, geo_provider, arrival_time, org_name,
                      header_from, envelope_from, envelope_to,
                      spf_result, dkim_result, dmarc_result, failure_type, created_at
               FROM forensic_reports WHERE id = ?""",
            (report_id,),
        )
        row = cur.fetchone()
        if not row:
            return ("not_found", None)

        report = {
            "id": row[0],
            "report_id": row[1],
            "domain": row[2],
            "source_ip": row[3],
            "resolved_name": row[4],
            "resolved_name_domain": row[5],
            "country_code": row[6],
            "country_name": row[7],
            "geo_provider": row[8],
            "arrival_time": row[9],
            "org_name": row[10],
            "header_from": row[11],
            "envelope_from": row[12],
            "envelope_to": row[13],
            "spf_result": row[14],
            "dkim_result": row[15],
            "dmarc_result": row[16],
            "failure_type": row[17],
            "created_at": row[18],
        }

        if report["domain"] not in allowed_domains:
            return ("forbidden", None)

        return ("ok", report)
    finally:
        conn.close()


def list_forensic_reports(
    config: Config,
    current_user: dict[str, Any],
    *,
    domains_param: list[str] | None = None,
    from_ts: str | int | None = None,
    to_ts: str | int | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
) -> dict[str, Any]:
    """List forensic report rows with domain scoping, optional domain/time filter, pagination, sort."""
    allowed_domains = [d["name"] for d in list_domains(config, current_user)]
    if not allowed_domains:
        return {"items": [], "total": 0, "page": max(1, page), "page_size": _cap_page_size(page_size)}

    domain_filter = allowed_domains
    if domains_param:
        domain_filter = [d for d in domains_param if d in allowed_domains]

    from_val = _parse_ts(from_ts)
    to_val = _parse_ts(to_ts)
    page = max(1, page)
    page_size = _cap_page_size(page_size)
    offset = (page - 1) * page_size

    sort_col = "created_at" if sort_by in ("created_at", "arrival_time") else "created_at"
    if sort_by == "arrival_time":
        sort_col = "arrival_time"
    sort_order = "DESC" if sort_dir == "desc" else "ASC"

    conn = get_connection(config.database_path)
    try:
        placeholders = ",".join("?" * len(domain_filter))
        where_parts = [f"domain IN ({placeholders})"]
        params: list[Any] = list(domain_filter)
        if from_val is not None:
            where_parts.append("created_at >= datetime(?, 'unixepoch')")
            params.append(from_val)
        if to_val is not None:
            where_parts.append("created_at <= datetime(?, 'unixepoch')")
            params.append(to_val)
        where_sql = " AND ".join(where_parts)

        cur = conn.execute(
            f"SELECT COUNT(*) FROM forensic_reports WHERE {where_sql}",
            params,
        )
        total = cur.fetchone()[0]

        cur = conn.execute(
            f"""SELECT id, report_id, domain, source_ip, resolved_name, resolved_name_domain, country_code, country_name, geo_provider, arrival_time, org_name,
                       header_from, envelope_from, envelope_to,
                       spf_result, dkim_result, dmarc_result, failure_type, created_at
                FROM forensic_reports WHERE {where_sql}
                ORDER BY {sort_col} {sort_order}
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        rows = cur.fetchall()
        items = [
            {
                "id": r[0],
                "report_id": r[1],
                "domain": r[2],
                "source_ip": r[3],
                "resolved_name": r[4],
                "resolved_name_domain": r[5],
                "country_code": r[6],
                "country_name": r[7],
                "geo_provider": r[8],
                "arrival_time": r[9],
                "org_name": r[10],
                "header_from": r[11],
                "envelope_from": r[12],
                "envelope_to": r[13],
                "spf_result": r[14],
                "dkim_result": r[15],
                "dmarc_result": r[16],
                "failure_type": r[17],
                "created_at": r[18],
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}
    finally:
        conn.close()


def _escape_fts_query(query: str) -> str:
    """Escape special FTS5 characters and format for prefix matching."""
    if not query or not query.strip():
        return ""
    terms: list[str] = []
    current: list[str] = []
    in_quotes = False
    index = 0

    while index < len(query):
        character = query[index]
        if in_quotes:
            if character == '"':
                if index + 1 < len(query) and query[index + 1] == '"':
                    current.append('"')
                    index += 2
                    continue
                in_quotes = False
                index += 1
                continue
            current.append(character)
            index += 1
            continue

        if character.isspace():
            term = "".join(current).strip()
            if term:
                terms.append(term)
            current = []
            index += 1
            continue

        if character == '"' and not current:
            in_quotes = True
            index += 1
            continue

        current.append(character)
        index += 1

    term = "".join(current).strip()
    if term:
        terms.append(term)

    def build_phrase(value: str) -> str:
        parts = [part for part in value.split() if part]
        if not parts:
            return ""
        escaped_parts = []
        for part in parts:
            escaped_part = part.replace('"', '""')
            escaped_parts.append(f'"{escaped_part}"')
        escaped_parts[-1] = f"{escaped_parts[-1]}*"
        return " + ".join(escaped_parts)

    return " ".join(filter(None, (build_phrase(term) for term in terms)))


def _build_record_item(row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "id": row[0],
        "type": "row",
        "aggregate_report_id": row[1],
        "source_ip": row[2],
        "resolved_name": row[3],
        "resolved_name_domain": row[4],
        "country_code": row[5],
        "country_name": row[6],
        "geo_provider": row[7],
        "count": row[8],
        "disposition": row[9],
        "dkim_result": row[10],
        "spf_result": row[11],
        "dkim_alignment": row[12],
        "spf_alignment": row[13],
        "dmarc_alignment": row[14],
        "header_from": row[15],
        "envelope_from": row[16],
        "envelope_to": row[17],
        "domain": row[18],
        "report_id": row[19],
        "org_name": row[20],
        "date_begin": row[21],
        "date_end": row[22],
        "record_date": _record_date_from_ts(row[21]),
    }


def _search_record_rows(
    conn,
    *,
    where_sql: str,
    params: list[Any],
    fts_join: str,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    total = conn.execute(
        f"""SELECT COUNT(*) FROM aggregate_report_records rec
            JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
            {fts_join}
            WHERE {where_sql}""",
        params,
    ).fetchone()[0]
    cur = conn.execute(
        f"""SELECT rec.id, rec.aggregate_report_id, rec.source_ip, rec.resolved_name, rec.resolved_name_domain, rec.country_code, rec.country_name, rec.geo_provider, rec.count,
                   rec.disposition, rec.dkim_result, rec.spf_result, rec.dkim_alignment, rec.spf_alignment, rec.dmarc_alignment,
                   rec.header_from, rec.envelope_from, rec.envelope_to,
                   ar.domain, ar.report_id, ar.org_name, ar.date_begin, ar.date_end
            FROM aggregate_report_records rec
            JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
            {fts_join}
            WHERE {where_sql}
            ORDER BY ar.date_begin DESC, rec.count DESC
            LIMIT ? OFFSET ?""",
        params + [page_size, offset],
    )
    items = [_build_record_item(row) for row in cur.fetchall()]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def search_grouped_records(
    config: Config,
    current_user: dict[str, Any],
    *,
    domains_param: list[str] | None = None,
    from_ts: str | int | None = None,
    to_ts: str | int | None = None,
    include: dict[str, list[str]] | None = None,
    exclude: dict[str, list[str]] | None = None,
    query: str | None = None,
    grouping: list[str] | None = None,
    path: list[dict[str, str]] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    backfill_missing_aggregate_alignment(config.database_path)
    allowed_domains = _allowed_domain_names(config, current_user)
    if not allowed_domains:
        return {
            "items": [],
            "total": 0,
            "page": max(1, page),
            "page_size": _cap_page_size(page_size),
            "grouping": [],
            "path": path or [],
            "level_kind": "group",
        }

    normalized_grouping = _normalize_grouping(grouping)
    if not normalized_grouping:
        raise ValueError("At least one grouping field is required")

    current_path = path or []
    if len(current_path) > len(normalized_grouping):
        raise ValueError("Grouping path is deeper than the configured grouping")
    for index, item in enumerate(current_path):
        expected_field = normalized_grouping[index]
        field = str(item.get("field") or "").strip()
        if field != expected_field:
            raise ValueError("Grouping path must match the configured grouping order")

    domain_filter = _resolve_domain_filter(allowed_domains, domains_param)
    page = max(1, page)
    page_size = _cap_page_size(page_size)
    where_sql, params, fts_join = _build_record_where_clause(
        domain_filter,
        from_ts=from_ts,
        to_ts=to_ts,
        include=include,
        exclude=exclude,
        query=query,
        path=current_path,
    )

    conn = get_connection(config.database_path)
    try:
        if len(current_path) >= len(normalized_grouping):
            rows = _search_record_rows(
                conn,
                where_sql=where_sql,
                params=params,
                fts_join=fts_join,
                page=page,
                page_size=page_size,
            )
            rows["grouping"] = normalized_grouping
            rows["path"] = current_path
            rows["level_kind"] = "row"
            return rows

        group_field = normalized_grouping[len(current_path)]
        group_expr = ALLOWED_GROUP_FIELDS[group_field]["expr"]
        offset = (page - 1) * page_size
        total = conn.execute(
            f"""SELECT COUNT(*) FROM (
                    SELECT 1
                    FROM aggregate_report_records rec
                    JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                    {fts_join}
                    WHERE {where_sql}
                    GROUP BY {group_expr}
                ) grouped""",
            params,
        ).fetchone()[0]
        cur = conn.execute(
            f"""SELECT {group_expr} AS group_value,
                       COUNT(*) AS row_count,
                       COUNT(DISTINCT ar.id) AS report_count,
                       COALESCE(SUM(rec.count), 0) AS message_count,
                       MIN(ar.date_begin) AS min_date_begin,
                       MAX(ar.date_end) AS max_date_end,
                       COALESCE(SUM(CASE WHEN rec.dmarc_alignment = 'pass' THEN rec.count ELSE 0 END), 0) AS dmarc_pass_count,
                       COALESCE(SUM(CASE WHEN rec.dmarc_alignment = 'fail' THEN rec.count ELSE 0 END), 0) AS dmarc_fail_count,
                       COALESCE(SUM(CASE WHEN rec.dmarc_alignment IS NULL OR rec.dmarc_alignment = 'unknown' THEN rec.count ELSE 0 END), 0) AS dmarc_unknown_count,
                       COALESCE(SUM(CASE WHEN rec.disposition = 'none' THEN rec.count ELSE 0 END), 0) AS disposition_none_count,
                       COALESCE(SUM(CASE WHEN rec.disposition = 'quarantine' THEN rec.count ELSE 0 END), 0) AS disposition_quarantine_count,
                       COALESCE(SUM(CASE WHEN rec.disposition = 'reject' THEN rec.count ELSE 0 END), 0) AS disposition_reject_count
                FROM aggregate_report_records rec
                JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                {fts_join}
                WHERE {where_sql}
                GROUP BY {group_expr}
                ORDER BY message_count DESC, group_value ASC
                LIMIT ? OFFSET ?""",
            params + [page_size, offset],
        )
        items: list[dict[str, Any]] = []
        for row in cur.fetchall():
            group_value = row[0] or ""
            group_path = [*current_path, {"field": group_field, "value": group_value}]
            items.append(
                {
                    "type": "group",
                    "field": group_field,
                    "value": group_value,
                    "label": group_value or "(empty)",
                    "path": group_path,
                    "row_count": row[1],
                    "report_count": row[2],
                    "message_count": row[3],
                    "first_record_date": _record_date_from_ts(row[4]),
                    "last_record_date": _record_date_from_ts(row[5]),
                    "dmarc_alignment_summary": {
                        "pass": row[6],
                        "fail": row[7],
                        "unknown": row[8],
                    },
                    "disposition_summary": {
                        "none": row[9],
                        "quarantine": row[10],
                        "reject": row[11],
                    },
                    "has_children": row[1] > 0,
                }
            )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "grouping": normalized_grouping,
            "path": current_path,
            "level_kind": "group",
        }
    finally:
        conn.close()


def search_records(
    config: Config,
    current_user: dict[str, Any],
    *,
    domains_param: list[str] | None = None,
    from_ts: str | int | None = None,
    to_ts: str | int | None = None,
    include: dict[str, list[str]] | None = None,
    exclude: dict[str, list[str]] | None = None,
    query: str | None = None,
    group_by: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Search aggregate_report_records with domain scoping, include/exclude filters, and free-text query.

    include: e.g. {"spf_result": ["fail"]} -> only rows where spf_result IN ('fail')
    exclude: e.g. {"disposition": ["none"]} -> only rows where disposition NOT IN ('none')
    query: free-text search over source_ip, resolved_name, resolved_name_domain, header_from, envelope_from,
           envelope_to, and org_name
    """
    backfill_missing_aggregate_alignment(config.database_path)
    allowed_domains = _allowed_domain_names(config, current_user)
    if not allowed_domains:
        return {"items": [], "total": 0, "page": max(1, page), "page_size": _cap_page_size(page_size)}

    domain_filter = _resolve_domain_filter(allowed_domains, domains_param)
    page = max(1, page)
    page_size = _cap_page_size(page_size)
    offset = (page - 1) * page_size
    normalized_group_by = _normalize_group_by(group_by)

    conn = get_connection(config.database_path)
    try:
        where_sql, params, fts_join = _build_record_where_clause(
            domain_filter,
            from_ts=from_ts,
            to_ts=to_ts,
            include=include,
            exclude=exclude,
            query=query,
        )

        if normalized_group_by:
            group_expr = ALLOWED_GROUP_FIELDS[normalized_group_by]["expr"]
            total = conn.execute(
                f"""SELECT COUNT(*) FROM (
                        SELECT 1
                        FROM aggregate_report_records rec
                        JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                        {fts_join}
                        WHERE {where_sql}
                        GROUP BY {group_expr}
                    ) grouped""",
                params,
            ).fetchone()[0]
            cur = conn.execute(
                f"""SELECT {group_expr} AS group_value,
                           COUNT(*) AS row_count,
                           COUNT(DISTINCT ar.id) AS report_count,
                           SUM(rec.count) AS total_count,
                           MIN(ar.date_begin) AS min_date_begin,
                           MAX(ar.date_end) AS max_date_end
                    FROM aggregate_report_records rec
                    JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                    {fts_join}
                    WHERE {where_sql}
                    GROUP BY {group_expr}
                    ORDER BY min_date_begin DESC, group_value ASC
                    LIMIT ? OFFSET ?""",
                params + [page_size, offset],
            )
            items = []
            for row in cur.fetchall():
                group_value = row[0] or ""
                items.append({
                    "group_by": normalized_group_by,
                    "group_value": group_value,
                    "group_label": group_value or "(empty)",
                    "row_count": row[1],
                    "report_count": row[2],
                    "count": row[3] or 0,
                    "date_begin": row[4],
                    "date_end": row[5],
                    "record_date": group_value if normalized_group_by == "record_date" else _record_date_from_ts(row[4]),
                })
            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "group_by": normalized_group_by,
            }
        rows = _search_record_rows(
            conn,
            where_sql=where_sql,
            params=params,
            fts_join=fts_join,
            page=page,
            page_size=page_size,
        )
        return {
            "items": [{key: value for key, value in item.items() if key != "type"} for item in rows["items"]],
            "total": rows["total"],
            "page": rows["page"],
            "page_size": rows["page_size"],
            "group_by": None,
        }
    finally:
        conn.close()


def _load_json_list(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        data = json.loads(raw_value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if isinstance(item, str)]


def row_get(report_id: str, conn, column_name: str) -> Any:
    cur = conn.execute(f"SELECT {column_name} FROM aggregate_reports WHERE id = ?", (report_id,))
    row = cur.fetchone()
    return row[0] if row else None
