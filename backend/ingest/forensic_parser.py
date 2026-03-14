"""Parse DMARC forensic/failure report XML (AFRF format). Extract normalized fields."""

import xml.etree.ElementTree as ET
from typing import Any

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def parse_forensic(xml_bytes: bytes) -> dict[str, Any] | None:
    """Parse forensic feedback XML.

    Returns dict with:
      - report_id, domain, source_ip, arrival_time, org_name
      - header_from, envelope_from, envelope_to
      - spf_result, dkim_result, dmarc_result, failure_type

    Returns None on parse error or if required fields are missing.
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

    def text_of(parent: ET.Element | None, name: str) -> str | None:
        if parent is None:
            return None
        e = find_child(parent, name)
        if e is not None and e.text:
            return e.text.strip()
        return None

    def find_anywhere(name: str) -> ET.Element | None:
        for e in root.iter():
            if local_name(e) == name:
                return e
        return None

    root_name = local_name(root)
    if root_name != "feedback":
        return None

    version = text_of(root, "version")
    feedback_type = text_of(root, "feedback_type")
    if feedback_type and feedback_type.lower() not in ("auth-failure", "failure"):
        return None

    report_meta = find_anywhere("report_metadata")
    org_name = text_of(report_meta, "org_name")
    report_id = text_of(report_meta, "report_id")

    if not report_id:
        return None

    policy_published = find_anywhere("policy_published")
    domain = text_of(policy_published, "domain")
    if not domain:
        return None

    auth_failure = find_anywhere("auth_failure")
    if auth_failure is None:
        record = find_anywhere("record")
        if record is not None:
            auth_failure = find_child(record, "auth_failure")

    source_ip = None
    arrival_time = None
    header_from = None
    envelope_from = None
    envelope_to = None
    spf_result = None
    dkim_result = None
    dmarc_result = None
    failure_type = None

    if auth_failure is not None:
        source_ip = text_of(auth_failure, "source_ip")
        arrival_time = text_of(auth_failure, "arrival_date")
        if not arrival_time:
            arrival_time = text_of(auth_failure, "arrival_time")

        identifiers = find_child(auth_failure, "identifiers")
        if identifiers is not None:
            header_from = text_of(identifiers, "header_from")
            envelope_from = text_of(identifiers, "envelope_from")
            envelope_to = text_of(identifiers, "envelope_to")
        else:
            header_from = text_of(auth_failure, "header_from")
            envelope_from = text_of(auth_failure, "envelope_from")
            envelope_to = text_of(auth_failure, "envelope_to")

        auth_results = find_child(auth_failure, "auth_results")
        if auth_results is not None:
            spf_elem = find_child(auth_results, "spf")
            dkim_elem = find_child(auth_results, "dkim")
            spf_result = text_of(spf_elem, "result") if spf_elem is not None else None
            dkim_result = text_of(dkim_elem, "result") if dkim_elem is not None else None
        else:
            spf_result = text_of(auth_failure, "spf_result")
            dkim_result = text_of(auth_failure, "dkim_result")

        dmarc_result = text_of(auth_failure, "dmarc_result")
        failure_type = text_of(auth_failure, "failure_type")
        if not failure_type:
            failure_type = text_of(auth_failure, "failure")

    row = find_anywhere("row")
    if row is not None and source_ip is None:
        source_ip = text_of(row, "source_ip")

    return {
        "report_id": report_id,
        "domain": domain,
        "source_ip": source_ip,
        "arrival_time": arrival_time,
        "org_name": org_name or "",
        "header_from": header_from,
        "envelope_from": envelope_from,
        "envelope_to": envelope_to,
        "spf_result": spf_result,
        "dkim_result": dkim_result,
        "dmarc_result": dmarc_result,
        "failure_type": failure_type,
    }
