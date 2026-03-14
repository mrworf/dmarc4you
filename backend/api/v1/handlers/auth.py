"""Auth endpoints: POST login, POST logout, GET me."""

from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from pydantic import BaseModel

from backend.config.schema import Config
from backend.api.v1.deps import get_config, get_current_user
from backend.services.auth_service import login, logout, me_response_user
from backend.auth.csrf import generate_csrf_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = ""
    password: str = ""


@router.post("/login")
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
        samesite="lax",
        secure=False,
    )
    response.set_cookie(
        key=config.csrf_cookie_name,
        value=generate_csrf_token(),
        max_age=config.session_max_age_days * 24 * 3600,
        path="/",
        httponly=False,
        samesite="strict",
        secure=False,
    )
    return {"user": user}


@router.post("/logout")
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


@router.get("/me")
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
            samesite="strict",
            secure=False,
        )
    return me_response_user(config, current_user)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
