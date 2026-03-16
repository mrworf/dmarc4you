#!/usr/bin/env python3
"""Export the FastAPI OpenAPI contract subset used by frontend-next."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app import app


def _schema_for_operation(schema: dict, path: str, method: str) -> dict:
    return schema["paths"][path][method.lower()]


def _json_schema_for_response(operation: dict, status_code: str) -> dict:
    return operation["responses"][status_code]["content"]["application/json"]["schema"]


def main() -> None:
    schema = app.openapi()

    payload = {
        "components": sorted(schema["components"]["schemas"].keys()),
        "contracts": {
            "auth_login_request": _schema_for_operation(schema, "/api/v1/auth/login", "POST")["requestBody"]["content"][
                "application/json"
            ]["schema"],
            "auth_login_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/auth/login", "POST"), "200"),
            "auth_me_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/auth/me", "GET"), "200"),
            "domains_list_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/domains", "GET"), "200"),
            "dashboards_list_response": _json_schema_for_response(
                _schema_for_operation(schema, "/api/v1/dashboards", "GET"), "200"
            ),
            "dashboards_create_request": _schema_for_operation(schema, "/api/v1/dashboards", "POST")["requestBody"][
                "content"
            ]["application/json"]["schema"],
            "dashboards_create_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/dashboards", "POST"), "201"),
            "dashboard_detail_response": _json_schema_for_response(
                _schema_for_operation(schema, "/api/v1/dashboards/{dashboard_id}", "GET"), "200"
            ),
            "search_request": _schema_for_operation(schema, "/api/v1/search", "POST")["requestBody"]["content"][
                "application/json"
            ]["schema"],
            "search_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/search", "POST"), "200"),
            "forensic_list_response": _json_schema_for_response(
                _schema_for_operation(schema, "/api/v1/reports/forensic", "GET"), "200"
            ),
            "users_list_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/users", "GET"), "200"),
            "users_create_request": _schema_for_operation(schema, "/api/v1/users", "POST")["requestBody"]["content"][
                "application/json"
            ]["schema"],
            "users_create_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/users", "POST"), "201"),
            "apikeys_list_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/apikeys", "GET"), "200"),
            "apikeys_create_request": _schema_for_operation(schema, "/api/v1/apikeys", "POST")["requestBody"]["content"][
                "application/json"
            ]["schema"],
            "apikeys_create_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/apikeys", "POST"), "201"),
            "audit_list_response": _json_schema_for_response(_schema_for_operation(schema, "/api/v1/audit", "GET"), "200"),
            "reports_ingest_request": _schema_for_operation(schema, "/api/v1/reports/ingest", "POST")["requestBody"][
                "content"
            ]["application/json"]["schema"],
            "reports_ingest_response": _json_schema_for_response(
                _schema_for_operation(schema, "/api/v1/reports/ingest", "POST"), "200"
            ),
        },
    }

    print(json.dumps(payload))


if __name__ == "__main__":
    main()
