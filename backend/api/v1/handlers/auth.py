"""Auth endpoints: POST login, POST logout, GET me, PUT me, PUT password."""

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status

from backend.api.errors import api_http_exception
from backend.api.v1.schemas.auth import (
    AuthLoginResponse,
    AuthMeResponse,
    LoginBody,
    UpdatePasswordBody,
    UpdatePasswordResponse,
    UpdateProfileBody,
)
from backend.api.v1.schemas.common import EmptyResponse, ErrorResponse
from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services.auth_service import change_own_password, login, logout, me_response_user, update_own_profile
from backend.auth.csrf import generate_csrf_token

router = APIRouter(prefix="/auth", tags=["auth"])


ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post("/login", response_model=AuthLoginResponse, responses=ERROR_RESPONSES)
def auth_login(
    request: Request,
    response: Response,
    body: LoginBody,
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/auth/login: body { username, password }. Returns { user }; sets session and CSRF cookies."""
    username = (body.username or "").strip()
    password = body.password or ""
    source_ip = _get_source_ip(request)
    user_agent = request.headers.get("user-agent")
    user, session_id, retry_after_seconds = login(config, username, password, source_ip=source_ip, user_agent=user_agent)
    if not user:
        if retry_after_seconds is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "login_throttled",
                    "message": "Too many login attempts. Try again later.",
                    "details": [{"retry_after_seconds": retry_after_seconds}],
                },
                headers={"Retry-After": str(retry_after_seconds)},
            )
        raise _unauthorized()
    response.set_cookie(
        key=config.session_cookie_name,
        value=session_id,
        max_age=config.session_max_age_days * 24 * 3600,
        path="/",
        domain=config.cookie_domain,
        httponly=True,
        samesite=config.session_cookie_same_site,
        secure=config.session_cookie_secure,
    )
    response.set_cookie(
        key=config.csrf_cookie_name,
        value=generate_csrf_token(),
        max_age=config.session_max_age_days * 24 * 3600,
        path="/",
        domain=config.cookie_domain,
        httponly=False,
        samesite=config.csrf_cookie_same_site,
        secure=config.session_cookie_secure,
    )
    return {"user": user, "password_change_required": bool(user.get("must_change_password"))}


@router.post("/logout", response_model=EmptyResponse, responses=ERROR_RESPONSES)
def auth_logout(
    request: Request,
    response: Response,
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/auth/logout: invalidate session and clear session/CSRF cookies."""
    session_id = request.cookies.get(config.session_cookie_name)
    logout(config, session_id)
    response.delete_cookie(key=config.session_cookie_name, path="/", domain=config.cookie_domain)
    response.delete_cookie(key=config.csrf_cookie_name, path="/", domain=config.cookie_domain)
    return {}


@router.get("/me", response_model=AuthMeResponse, responses=ERROR_RESPONSES)
def auth_me(
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """GET /api/v1/auth/me: current user + domain visibility; refreshes CSRF cookie if missing."""
    csrf_cookie = request.cookies.get(config.csrf_cookie_name)
    if not csrf_cookie:
        response.set_cookie(
            key=config.csrf_cookie_name,
            value=generate_csrf_token(),
            max_age=config.session_max_age_days * 24 * 3600,
            path="/",
            domain=config.cookie_domain,
            httponly=False,
            samesite=config.csrf_cookie_same_site,
            secure=config.session_cookie_secure,
        )
    return me_response_user(config, current_user)


@router.put("/me", response_model=AuthMeResponse, responses=ERROR_RESPONSES)
def auth_update_me(
    body: UpdateProfileBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """PUT /api/v1/auth/me: update the current user's optional profile fields."""
    updated_user = update_own_profile(
        config,
        current_user,
        new_full_name=body.full_name,
        new_email=body.email,
    )
    return me_response_user(config, updated_user)


@router.put("/password", response_model=UpdatePasswordResponse, responses=ERROR_RESPONSES)
def auth_update_password(
    request: Request,
    response: Response,
    body: UpdatePasswordBody,
    current_user: dict = Depends(get_current_user),
    config: Config = Depends(get_config),
) -> dict:
    """PUT /api/v1/auth/password: change the signed-in user's password and require re-login."""
    result = change_own_password(
        config,
        current_user,
        current_password=body.current_password,
        new_password=body.new_password,
    )
    if result == "invalid_current_password":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "invalid_current_password", "Current password is incorrect")
    if result == "password_reuse":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "password_reuse", "New password must be different from the current password")
    if result != "ok":
        raise api_http_exception(status.HTTP_400_BAD_REQUEST, "password_policy_violation", result)

    response.delete_cookie(key=config.session_cookie_name, path="/", domain=config.cookie_domain)
    response.delete_cookie(key=config.csrf_cookie_name, path="/", domain=config.cookie_domain)
    return {"password_changed": True, "reauth_required": True}


def _unauthorized() -> HTTPException:
    return api_http_exception(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid credentials")


def _get_source_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    return request.client.host if request.client else None
