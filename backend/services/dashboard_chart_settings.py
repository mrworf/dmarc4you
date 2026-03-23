"""Shared dashboard chart configuration."""

DEFAULT_CHART_Y_AXIS = "message_count"

ALLOWED_CHART_Y_AXIS = frozenset(
    [
        "message_count",
        "row_count",
        "report_count",
    ]
)


def normalize_chart_y_axis(chart_y_axis: str | None) -> str:
    value = (chart_y_axis or "").strip()
    if value in ALLOWED_CHART_Y_AXIS:
        return value
    return DEFAULT_CHART_Y_AXIS
