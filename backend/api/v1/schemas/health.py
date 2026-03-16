"""Health API schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessCheck(BaseModel):
    name: str
    status: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    checks: list[ReadinessCheck]
