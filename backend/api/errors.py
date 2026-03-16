"""API error envelopes and exception handlers."""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def build_error_payload(
    code: str,
    message: str,
    *,
    details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    payload: dict[str, Any] = {"error": error, "detail": message}
    if details:
        payload["details"] = details
    return payload


def api_http_exception(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or f"http_{exc.status_code}")
        message = str(detail.get("message") or detail.get("detail") or "Request failed")
        details = detail.get("details")
        if details is not None and not isinstance(details, list):
            details = [details]
        return JSONResponse(
            status_code=exc.status_code,
            content=build_error_payload(code, message, details=details),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_payload(f"http_{exc.status_code}", str(detail)),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {
            "loc": [str(part) for part in error.get("loc", ())],
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "validation_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=build_error_payload("invalid_request", "Invalid request", details=details),
    )
