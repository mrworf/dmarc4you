"""Common API response schemas."""

from typing import Any

from pydantic import BaseModel


class ErrorField(BaseModel):
    loc: list[str]
    message: str
    type: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[ErrorField] | list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    detail: str
    details: list[ErrorField] | list[dict[str, Any]] | None = None


class EmptyResponse(BaseModel):
    pass
