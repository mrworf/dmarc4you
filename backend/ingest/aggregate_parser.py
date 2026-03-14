"""Parse DMARC aggregate XML (safe). Extract report metadata and per-record details."""

import xml.etree.ElementTree as ET
from typing import Any

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def parse_aggregate(xml_bytes: bytes) -> dict[str, Any] | None:
    """Parse aggregate feedback XML.

    Returns dict with:
      - org_name, report_id, date_begin, date_end, domain (report-level)
      - records: list of per-record dicts with source_ip, count, disposition,
        dkim_result, spf_result, header_from, envelope_from, envelope_to

    Returns None on parse error.
    """
    if len(xml_bytes) > MAX_BYTES:
        return None
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    def local_name(e: ET.Element) -> str:
        if e.tag.startswith("{"):
            return e.tag.split("}", 1)[1]
        return e.tag

    def find_child(parent: ET.Element, name: str) -> ET.Element | None:
        for c in parent:
            if local_name(c) == name:
                return c
        return None

    def text_of(parent: ET.Element, name: str) -> str | None:
        e = find_child(parent, name)
        if e is not None and e.text:
            return e.text.strip()
        return None

    def int_of(parent: ET.Element, name: str) -> int | None:
        t = text_of(parent, name)
        if t is None:
            return None
        try:
            return int(t)
        except ValueError:
            return None

    # report_metadata
    meta = None
    for e in root.iter():
        if local_name(e) == "report_metadata":
            meta = e
            break
    if meta is None:
        return None
    org_name = text_of(meta, "org_name")
    report_id = text_of(meta, "report_id")
    date_range = find_child(meta, "date_range")
    if date_range is None or report_id is None:
        return None
    date_begin = int_of(date_range, "begin")
    date_end = int_of(date_range, "end")
    if date_begin is None or date_end is None:
        return None

    # policy_published.domain
    policy = None
    for e in root.iter():
        if local_name(e) == "policy_published":
            policy = e
            break
    if policy is None:
        return None
    domain = text_of(policy, "domain")
    if not domain:
        return None

    # Extract records
    records = []
    for elem in root.iter():
        if local_name(elem) != "record":
            continue
        rec = _parse_record(elem, find_child, text_of, int_of)
        records.append(rec)

    return {
        "org_name": org_name or "",
        "report_id": report_id,
        "date_begin": date_begin,
        "date_end": date_end,
        "domain": domain,
        "records": records,
    }


def _parse_record(
    record_elem: ET.Element,
    find_child,
    text_of,
    int_of,
) -> dict[str, Any]:
    """Extract fields from a single <record> element."""
    row = find_child(record_elem, "row")
    source_ip = text_of(row, "source_ip") if row is not None else None
    count = int_of(row, "count") if row is not None else 0
    if count is None:
        count = 0

    policy_evaluated = find_child(row, "policy_evaluated") if row is not None else None
    disposition = text_of(policy_evaluated, "disposition") if policy_evaluated is not None else None
    dkim_result = text_of(policy_evaluated, "dkim") if policy_evaluated is not None else None
    spf_result = text_of(policy_evaluated, "spf") if policy_evaluated is not None else None

    identifiers = find_child(record_elem, "identifiers")
    header_from = text_of(identifiers, "header_from") if identifiers is not None else None
    envelope_from = text_of(identifiers, "envelope_from") if identifiers is not None else None
    envelope_to = text_of(identifiers, "envelope_to") if identifiers is not None else None

    return {
        "source_ip": source_ip,
        "count": count,
        "disposition": disposition,
        "dkim_result": dkim_result,
        "spf_result": spf_result,
        "header_from": header_from,
        "envelope_from": envelope_from,
        "envelope_to": envelope_to,
    }
