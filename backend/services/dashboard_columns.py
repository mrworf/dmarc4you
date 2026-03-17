"""Shared dashboard column configuration."""

DEFAULT_VISIBLE_COLUMNS = [
    "record_date",
    "domain",
    "org_name",
    "source_ip",
    "resolved_name",
    "country_code",
    "count",
    "disposition",
    "dkim_result",
    "spf_result",
    "dmarc_alignment",
    "dkim_alignment",
    "spf_alignment",
    "header_from",
]

ALLOWED_VISIBLE_COLUMNS = frozenset(
    [
        "record_date",
        "domain",
        "org_name",
        "source_ip",
        "resolved_name",
        "resolved_name_domain",
        "country_code",
        "country_name",
        "count",
        "disposition",
        "dkim_result",
        "spf_result",
        "dmarc_alignment",
        "dkim_alignment",
        "spf_alignment",
        "header_from",
        "envelope_from",
        "envelope_to",
        "report_id",
    ]
)


def normalize_visible_columns(visible_columns: list[str] | None) -> list[str]:
    if not visible_columns:
        return list(DEFAULT_VISIBLE_COLUMNS)
    normalized: list[str] = []
    seen: set[str] = set()
    for column in visible_columns:
        value = (column or "").strip()
        if not value or value not in ALLOWED_VISIBLE_COLUMNS or value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized or list(DEFAULT_VISIBLE_COLUMNS)
