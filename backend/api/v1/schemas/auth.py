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


class UpdateProfileBody(BaseModel):
    full_name: str | None = None
    email: str | None = None


class AuthLoginResponse(BaseModel):
    user: UserSummary
    password_change_required: bool


class AuthMeResponse(BaseModel):
    user: UserSummary
    all_domains: bool
    domain_ids: list[str]
    password_change_required: bool


class UpdatePasswordBody(BaseModel):
    current_password: str = ""
    new_password: str = ""


class UpdatePasswordResponse(BaseModel):
    password_changed: bool
    reauth_required: bool
