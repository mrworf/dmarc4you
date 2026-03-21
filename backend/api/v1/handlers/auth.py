"""Auth endpoints: POST login, POST logout, GET me."""

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status

from backend.api.errors import api_http_exception
from backend.api.v1.schemas.auth import AuthLoginResponse, AuthMeResponse, LoginBody, UpdateProfileBody
from backend.api.v1.schemas.common import EmptyResponse, ErrorResponse
from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services.auth_service import login, logout, me_response_user, update_own_profile
from backend.auth.csrf import generate_csrf_token

router = APIRouter(prefix="/auth", tags=["auth"])


ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
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
    source_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    user, session_id = login(config, username, password, source_ip=source_ip, user_agent=user_agent)
    if not user:
        raise _unauthorized()
    response.set_cookie(
        key=config.session_cookie_name,
        value=session_id,
        max_age=config.session_max_age_days * 24 * 3600,
        path="/",
        httponly=True,
        samesite=config.session_cookie_same_site,
        secure=config.session_cookie_secure,
    )
    response.set_cookie(
        key=config.csrf_cookie_name,
        value=generate_csrf_token(),
        max_age=config.session_max_age_days * 24 * 3600,
        path="/",
        httponly=False,
        samesite=config.csrf_cookie_same_site,
        secure=config.session_cookie_secure,
    )
    return {"user": user}


@router.post("/logout", response_model=EmptyResponse, responses=ERROR_RESPONSES)
def auth_logout(
    request: Request,
    response: Response,
    config: Config = Depends(get_config),
) -> dict:
    """POST /api/v1/auth/logout: invalidate session and clear session/CSRF cookies."""
    session_id = request.cookies.get(config.session_cookie_name)
    logout(config, session_id)
    response.delete_cookie(key=config.session_cookie_name, path="/")
    response.delete_cookie(key=config.csrf_cookie_name, path="/")
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


def _unauthorized() -> HTTPException:
    return api_http_exception(status.HTTP_401_UNAUTHORIZED, "invalid_credentials", "Invalid credentials")
