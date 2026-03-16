"""Auth API schemas."""

from pydantic import BaseModel


class LoginBody(BaseModel):
    username: str = ""
    password: str = ""


class UserSummary(BaseModel):
    id: str
    username: str
    role: str
    full_name: str | None = None
    email: str | None = None


class AuthLoginResponse(BaseModel):
    user: UserSummary


class AuthMeResponse(BaseModel):
    user: UserSummary
    all_domains: bool
    domain_ids: list[str]
