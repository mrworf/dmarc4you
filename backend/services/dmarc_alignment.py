"""DMARC alignment helpers for aggregate records."""

from __future__ import annotations

from email.utils import parseaddr
from functools import lru_cache
from typing import Any

from publicsuffix2 import get_sld, get_tld

from backend.storage.sqlite import get_connection


AlignmentValue = str

_PASS_RESULT = "pass"


def normalize_domain(value: str | None) -> str | None:
    """Return a normalized domain from a header/domain-like value."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    parsed = parseaddr(raw)[1] or raw
    candidate = parsed.rsplit("@", 1)[-1].strip().strip(".").lower()
    candidate = candidate.strip("<>[]()\"'")
    if not candidate or " " in candidate:
        return None

    try:
        normalized = candidate.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None

    labels = normalized.split(".")
    if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
        return None
    return normalized


def get_organizational_domain(value: str | None) -> str | None:
    """Return the organizational domain for relaxed alignment checks."""
    normalized = normalize_domain(value)
    if not normalized:
        return None
    if get_tld(normalized) == normalized:
        return None
    return get_sld(normalized) or None


def _normalize_alignment_mode(value: str | None) -> str:
    return "s" if (value or "").strip().lower() == "s" else "r"


def _is_pass(value: str | None) -> bool:
    return (value or "").strip().lower() == _PASS_RESULT


def classify_alignment(identifier_domain: str | None, header_from: str | None, mode: str | None) -> AlignmentValue:
    """Classify a single identifier against the visible From domain."""
    identifier = normalize_domain(identifier_domain)
    visible_from = normalize_domain(header_from)
    if not identifier or not visible_from:
        return "unknown"
    if identifier == visible_from:
        return "strict"
    if _normalize_alignment_mode(mode) == "s":
        return "none"

    identifier_org = get_organizational_domain(identifier)
    visible_org = get_organizational_domain(visible_from)
    if not identifier_org or not visible_org:
        return "unknown"
    return "relaxed" if identifier_org == visible_org else "none"


def compute_dkim_alignment(
    header_from: str | None,
    auth_results: list[dict[str, Any]] | None,
    dkim_result: str | None,
    adkim: str | None,
) -> AlignmentValue:
    passing_results = [
        result
        for result in (auth_results or [])
        if result.get("auth_method") == "dkim" and _is_pass(result.get("result"))
    ]
    if not passing_results:
        return "unknown" if _is_pass(dkim_result) else ("none" if dkim_result else "unknown")

    saw_unknown = False
    saw_relaxed = False
    for result in passing_results:
        classification = classify_alignment(result.get("domain"), header_from, adkim)
        if classification == "strict":
            return "strict"
        if classification == "relaxed":
            saw_relaxed = True
        elif classification == "unknown":
            saw_unknown = True

    if saw_relaxed:
        return "relaxed"
    return "unknown" if saw_unknown else "none"


def compute_spf_alignment(
    header_from: str | None,
    envelope_from: str | None,
    auth_results: list[dict[str, Any]] | None,
    spf_result: str | None,
    aspf: str | None,
) -> AlignmentValue:
    passing_results = [
        result
        for result in (auth_results or [])
        if result.get("auth_method") == "spf"
        and _is_pass(result.get("result"))
        and (not result.get("scope") or (result.get("scope") or "").strip().lower() == "mfrom")
    ]
    candidates = [result.get("domain") for result in passing_results]

    if not candidates and _is_pass(spf_result) and envelope_from:
        candidates = [envelope_from]

    if not candidates:
        return "unknown" if _is_pass(spf_result) else ("none" if spf_result else "unknown")

    saw_unknown = False
    saw_relaxed = False
    for candidate in candidates:
        classification = classify_alignment(candidate, header_from, aspf)
        if classification == "strict":
            return "strict"
        if classification == "relaxed":
            saw_relaxed = True
        elif classification == "unknown":
            saw_unknown = True

    if saw_relaxed:
        return "relaxed"
    return "unknown" if saw_unknown else "none"


def compute_dmarc_alignment(dkim_alignment: AlignmentValue, spf_alignment: AlignmentValue) -> str:
    if dkim_alignment in {"strict", "relaxed"} or spf_alignment in {"strict", "relaxed"}:
        return "pass"
    if dkim_alignment == "none" and spf_alignment == "none":
        return "fail"
    return "unknown"


def compute_aggregate_alignment(
    *,
    header_from: str | None,
    envelope_from: str | None,
    dkim_result: str | None,
    spf_result: str | None,
    auth_results: list[dict[str, Any]] | None,
    adkim: str | None,
    aspf: str | None,
) -> dict[str, str]:
    dkim_alignment = compute_dkim_alignment(header_from, auth_results, dkim_result, adkim)
    spf_alignment = compute_spf_alignment(header_from, envelope_from, auth_results, spf_result, aspf)
    return {
        "dkim_alignment": dkim_alignment,
        "spf_alignment": spf_alignment,
        "dmarc_alignment": compute_dmarc_alignment(dkim_alignment, spf_alignment),
    }


def load_record_auth_results(conn: Any, aggregate_record_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT auth_method, domain, selector, scope, result, human_result
           FROM aggregate_record_auth_results
           WHERE aggregate_record_id = ?
           ORDER BY id""",
        (aggregate_record_id,),
    ).fetchall()
    return [
        {
            "auth_method": row[0],
            "domain": row[1],
            "selector": row[2],
            "scope": row[3],
            "result": row[4],
            "human_result": row[5],
        }
        for row in rows
    ]


@lru_cache(maxsize=16)
def _alignment_columns_exist(database_path: str) -> bool:
    conn = get_connection(database_path)
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(aggregate_report_records)").fetchall()
        }
        return {"dkim_alignment", "spf_alignment", "dmarc_alignment"}.issubset(columns)
    finally:
        conn.close()


def backfill_missing_aggregate_alignment(database_path: str) -> None:
    """Persist alignment values for legacy aggregate rows that predate alignment columns."""
    if not _alignment_columns_exist(database_path):
        return

    conn = get_connection(database_path)
    try:
        rows = conn.execute(
            """SELECT rec.id, rec.header_from, rec.envelope_from, rec.dkim_result, rec.spf_result, ar.adkim, ar.aspf
               FROM aggregate_report_records rec
               JOIN aggregate_reports ar ON rec.aggregate_report_id = ar.id
               WHERE rec.dkim_alignment IS NULL
                  OR rec.spf_alignment IS NULL
                  OR rec.dmarc_alignment IS NULL"""
        ).fetchall()
        if not rows:
            return

        for row in rows:
            auth_results = load_record_auth_results(conn, row[0])
            alignment = compute_aggregate_alignment(
                header_from=row[1],
                envelope_from=row[2],
                dkim_result=row[3],
                spf_result=row[4],
                auth_results=auth_results,
                adkim=row[5],
                aspf=row[6],
            )
            conn.execute(
                """UPDATE aggregate_report_records
                   SET dkim_alignment = ?, spf_alignment = ?, dmarc_alignment = ?
                   WHERE id = ?""",
                (
                    alignment["dkim_alignment"],
                    alignment["spf_alignment"],
                    alignment["dmarc_alignment"],
                    row[0],
                ),
            )
        conn.commit()
    finally:
        conn.close()
