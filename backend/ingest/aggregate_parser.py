"""Parse DMARC aggregate XML (safe). Extract report metadata and per-record details."""

import xml.etree.ElementTree as ET
from typing import Any

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def parse_aggregate(xml_bytes: bytes) -> dict[str, Any] | None:
    """Parse aggregate feedback XML.

    Returns dict with:
      - report metadata and published policy fields
      - records: list of per-record dicts with summary fields, override reasons,
        and auth_results details

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
    contact_email = text_of(meta, "email")
    extra_contact_info = text_of(meta, "extra_contact_info")
    error_messages = [
        (child.text or "").strip()
        for child in meta
        if local_name(child) == "error" and (child.text or "").strip()
    ]
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
    adkim = text_of(policy, "adkim")
    aspf = text_of(policy, "aspf")
    policy_p = text_of(policy, "p")
    policy_sp = text_of(policy, "sp")
    policy_pct = int_of(policy, "pct")
    policy_fo = text_of(policy, "fo")

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
        "contact_email": contact_email,
        "extra_contact_info": extra_contact_info,
        "error_messages": error_messages,
        "adkim": adkim,
        "aspf": aspf,
        "policy_p": policy_p,
        "policy_sp": policy_sp,
        "policy_pct": policy_pct,
        "policy_fo": policy_fo,
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
    policy_overrides = _parse_policy_overrides(policy_evaluated, text_of)
    auth_results = _parse_auth_results(find_child(record_elem, "auth_results"), find_child, text_of)

    return {
        "source_ip": source_ip,
        "count": count,
        "disposition": disposition,
        "dkim_result": dkim_result,
        "spf_result": spf_result,
        "header_from": header_from,
        "envelope_from": envelope_from,
        "envelope_to": envelope_to,
        "policy_overrides": policy_overrides,
        "auth_results": auth_results,
    }


def _parse_policy_overrides(policy_evaluated: ET.Element | None, text_of) -> list[dict[str, str | None]]:
    if policy_evaluated is None:
        return []
    overrides: list[dict[str, str | None]] = []
    for child in policy_evaluated:
        if child.tag.endswith("reason") or child.tag == "reason":
            overrides.append({
                "type": text_of(child, "type"),
                "comment": text_of(child, "comment"),
            })
    return overrides


def _parse_auth_results(auth_results: ET.Element | None, find_child, text_of) -> list[dict[str, str | None]]:
    if auth_results is None:
        return []
    results: list[dict[str, str | None]] = []
    for child in auth_results:
        tag = child.tag.split("}", 1)[1] if child.tag.startswith("{") else child.tag
        if tag == "dkim":
            results.append({
                "auth_method": "dkim",
                "domain": text_of(child, "domain"),
                "selector": text_of(child, "selector"),
                "scope": None,
                "result": text_of(child, "result"),
                "human_result": text_of(child, "human_result"),
            })
        elif tag == "spf":
            results.append({
                "auth_method": "spf",
                "domain": text_of(child, "domain"),
                "selector": None,
                "scope": text_of(child, "scope"),
                "result": text_of(child, "result"),
                "human_result": text_of(child, "human_result"),
            })
    return results
