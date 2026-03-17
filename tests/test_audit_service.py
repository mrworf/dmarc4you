"""Unit tests for audit filter normalization."""

from backend.services.audit_service import normalize_action_types


def test_normalize_action_types_merges_legacy_and_multi_select() -> None:
    assert normalize_action_types("login_success", ["user_created,domain_assigned", "login_success"]) == [
        "login_success",
        "user_created",
        "domain_assigned",
    ]


def test_normalize_action_types_ignores_empty_values() -> None:
    assert normalize_action_types("", ["", " user_deleted , ", " "]) == ["user_deleted"]
