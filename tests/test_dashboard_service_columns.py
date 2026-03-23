import tempfile

from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.config.schema import Config
from backend.services import dashboard_service, domain_service
from backend.storage.sqlite import get_connection, run_migrations


def _setup_config() -> tuple[Config, dict[str, str], str]:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = Config(
        database_path=handle.name,
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )
    conn = get_connection(handle.name)
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    conn.close()
    current_user = {"id": admin_id, "role": "super-admin", "username": "admin"}
    status, domain = domain_service.create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"
    return config, current_user, domain["id"]


def test_create_dashboard_stores_visible_columns() -> None:
    config, current_user, domain_id = _setup_config()
    status, dashboard = dashboard_service.create_dashboard(
        config,
        name="Ops",
        description="Visibility",
        domain_ids=[domain_id],
        visible_columns=["domain", "source_ip", "dmarc_alignment"],
        chart_y_axis="row_count",
        owner_user_id=current_user["id"],
        current_user=current_user,
    )
    assert status == "ok"
    assert dashboard is not None
    assert dashboard["visible_columns"] == ["domain", "source_ip", "dmarc_alignment"]
    assert dashboard["chart_y_axis"] == "row_count"


def test_export_import_dashboard_round_trips_visible_columns() -> None:
    config, current_user, domain_id = _setup_config()
    status, dashboard = dashboard_service.create_dashboard(
        config,
        name="Ops",
        description="Visibility",
        domain_ids=[domain_id],
        visible_columns=["domain", "source_ip", "dmarc_alignment"],
        chart_y_axis="report_count",
        owner_user_id=current_user["id"],
        current_user=current_user,
    )
    assert status == "ok"
    assert dashboard is not None

    yaml_str, error = dashboard_service.export_dashboard_yaml(config, dashboard["id"], current_user)
    assert error is None
    assert "visible_columns" in (yaml_str or "")
    assert "chart_y_axis" in (yaml_str or "")

    imported_status, imported = dashboard_service.import_dashboard_yaml(
        config,
        yaml_str or "",
        {"example.com": domain_id},
        current_user,
    )
    assert imported_status == "ok"
    assert imported is not None
    assert imported["visible_columns"] == ["domain", "source_ip", "dmarc_alignment"]
    assert imported["chart_y_axis"] == "report_count"
