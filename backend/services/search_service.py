"""Search service: list aggregate reports and records with domain scoping, filters, pagination."""

from datetime import datetime, timezone
from typing import Any

from backend.config.schema import Config
from backend.storage.sqlite import get_connection
from backend.services.domain_service import list_domains

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 500

ALLOWED_FILTER_FIELDS = frozenset(["spf_result", "dkim_result", "disposition", "source_ip"])
ALLOWED_GROUP_FIELDS = {
    "record_date": "date(ar.date_begin, 'unixepoch')",
    "source_ip": "COALESCE(rec.source_ip, '')",
    "resolved_name": "COALESCE(rec.resolved_name, '')",
    "resolved_name_domain": "COALESCE(rec.resolved_name_domain, '')",
}


def _record_date_from_ts(timestamp: int | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


def _normalize_group_by(group_by: str | None) -> str | None:
    value = (group_by or "").strip()
    return value if value in ALLOWED_GROUP_FIELDS else None


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


def get_aggregate_report_detail(
    config: Config,
    current_user: dict[str, Any],
    report_id: str,
) -> tuple[str, dict[str, Any] | None]:
    """Get a single aggregate report with all its records.

    Returns (status, report_dict) where status is "ok", "not_found", or "forbidden".
    """
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
            """SELECT id, source_ip, resolved_name, resolved_name_domain, count, disposition, dkim_result, spf_result,
                      header_from, envelope_from, envelope_to
               FROM aggregate_report_records WHERE aggregate_report_id = ?
               ORDER BY count DESC""",
            (report_id,),
        )
        records = [
            {
                "id": r[0],
                "source_ip": r[1],
                "resolved_name": r[2],
                "resolved_name_domain": r[3],
                "count": r[4],
                "disposition": r[5],
                "dkim_result": r[6],
                "spf_result": r[7],
                "header_from": r[8],
                "envelope_from": r[9],
                "envelope_to": r[10],
            }
            for r in cur.fetchall()
        ]
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
            """SELECT id, report_id, domain, source_ip, resolved_name, resolved_name_domain, arrival_time, org_name,
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
            "arrival_time": row[6],
            "org_name": row[7],
            "header_from": row[8],
            "envelope_from": row[9],
            "envelope_to": row[10],
            "spf_result": row[11],
            "dkim_result": row[12],
            "dmarc_result": row[13],
            "failure_type": row[14],
            "created_at": row[15],
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
            f"""SELECT id, report_id, domain, source_ip, resolved_name, resolved_name_domain, arrival_time, org_name,
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
                "arrival_time": r[6],
                "org_name": r[7],
                "header_from": r[8],
                "envelope_from": r[9],
                "envelope_to": r[10],
                "spf_result": r[11],
                "dkim_result": r[12],
                "dmarc_result": r[13],
                "failure_type": r[14],
                "created_at": r[15],
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
    escaped = query.replace('"', '""')
    terms = escaped.split()
    return " ".join(f'"{t}"*' for t in terms if t)


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
    query: free-text search over source_ip, header_from, envelope_from, envelope_to, org_name
    """
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
    normalized_group_by = _normalize_group_by(group_by)

    fts_query = _escape_fts_query(query or "")

    conn = get_connection(config.database_path)
    try:
        placeholders = ",".join("?" * len(domain_filter))
        where_parts = [f"ar.domain IN ({placeholders})"]
        params: list[Any] = list(domain_filter)

        if from_val is not None:
            where_parts.append("ar.date_end >= ?")
            params.append(from_val)
        if to_val is not None:
            where_parts.append("ar.date_begin <= ?")
            params.append(to_val)

        # Include filters
        if include:
            for field, values in include.items():
                if field not in ALLOWED_FILTER_FIELDS or not values:
                    continue
                ph = ",".join("?" * len(values))
                where_parts.append(f"rec.{field} IN ({ph})")
                params.extend(values)

        # Exclude filters
        if exclude:
            for field, values in exclude.items():
                if field not in ALLOWED_FILTER_FIELDS or not values:
                    continue
                ph = ",".join("?" * len(values))
                where_parts.append(f"(rec.{field} IS NULL OR rec.{field} NOT IN ({ph}))")
                params.extend(values)

        # FTS query
        fts_join = ""
        if fts_query:
            fts_join = "JOIN aggregate_records_fts fts ON rec.rowid = fts.rowid"
            where_parts.append("aggregate_records_fts MATCH ?")
            params.append(fts_query)

        where_sql = " AND ".join(where_parts)

        cur = conn.execute(
            f"""SELECT COUNT(*) FROM aggregate_report_records rec
                JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                {fts_join}
                WHERE {where_sql}""",
            params,
        ) if not normalized_group_by else None

        if normalized_group_by:
            group_expr = ALLOWED_GROUP_FIELDS[normalized_group_by]
            cur = conn.execute(
                f"""SELECT COUNT(*) FROM (
                        SELECT 1
                        FROM aggregate_report_records rec
                        JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
                        {fts_join}
                        WHERE {where_sql}
                        GROUP BY {group_expr}
                    ) grouped""",
                params,
            )
            total = cur.fetchone()[0]
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

        total = cur.fetchone()[0]
        cur = conn.execute(
            f"""SELECT rec.id, rec.aggregate_report_id, rec.source_ip, rec.resolved_name, rec.resolved_name_domain, rec.count,
                       rec.disposition, rec.dkim_result, rec.spf_result,
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
        items = []
        for row in cur.fetchall():
            items.append({
                "id": row[0],
                "aggregate_report_id": row[1],
                "source_ip": row[2],
                "resolved_name": row[3],
                "resolved_name_domain": row[4],
                "count": row[5],
                "disposition": row[6],
                "dkim_result": row[7],
                "spf_result": row[8],
                "header_from": row[9],
                "envelope_from": row[10],
                "envelope_to": row[11],
                "domain": row[12],
                "report_id": row[13],
                "org_name": row[14],
                "date_begin": row[15],
                "date_end": row[16],
                "record_date": _record_date_from_ts(row[15]),
            })
        return {"items": items, "total": total, "page": page, "page_size": page_size, "group_by": None}
    finally:
        conn.close()
