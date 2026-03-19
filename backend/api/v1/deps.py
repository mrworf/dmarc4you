"""Dependencies: config, current user from session cookie; ingest actor (session or API key); CSRF validation."""

import secrets

from fastapi import Request, HTTPException, status

from backend.config import load_config
from backend.config.schema import Config
from backend.services.auth_service import get_current_user as get_current_user_impl
from backend.services import api_key_service
from backend.auth.csrf import CSRF_HEADER_NAME


def get_config(request: Request) -> Config:
    """Return config from app.state or load (so tests can set app.state.config)."""
    if hasattr(request.app.state, "config") and request.app.state.config is not None:
        return request.app.state.config
    return load_config()


def get_current_user(request: Request) -> dict:
    """Return current user from session cookie; raise 401 if missing or invalid."""
    config = get_config(request)
    session_id = request.cookies.get(config.session_cookie_name)
    user = get_current_user_impl(config, session_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def get_ingest_actor(request: Request) -> dict:
    """Return actor for ingest: session user or API key (Bearer). Raises 401 or 403 if neither valid."""
    config = get_config(request)
    session_id = request.cookies.get(config.session_cookie_name)
    user = get_current_user_impl(config, session_id)
    if user:
        return {"type": "user", "user_id": user["id"]}
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        result = api_key_service.validate_api_key_for_ingest(config, token)
        if result:
            key_id, domain_ids = result
            return {"type": "api_key", "key_id": key_id, "domain_ids": domain_ids}
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key or missing scope")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def get_monitoring_actor(request: Request) -> dict:
    """Return actor for monitoring endpoints: session user or API key with domains:monitor scope."""
    config = get_config(request)
    session_id = request.cookies.get(config.session_cookie_name)
    user = get_current_user_impl(config, session_id)
    if user:
        actor = dict(user)
        actor["type"] = "user"
        return actor
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth[7:].strip()
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        result = api_key_service.validate_api_key_for_scope(config, token, api_key_service.SCOPE_DOMAINS_MONITOR)
        if result:
            key_id, domain_ids = result
            return {"type": "api_key", "key_id": key_id, "domain_ids": domain_ids}
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key or missing scope")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


CSRF_EXEMPT_PATHS = {"/api/v1/auth/login"}


def validate_csrf(request: Request) -> None:
    """
    Validate CSRF token for session-authenticated write requests.
    
    Skips validation for:
    - Safe methods (GET, HEAD, OPTIONS)
    - API key (Bearer) authenticated requests
    - Login endpoint (no session exists yet)
    - Requests without a session cookie (let auth handle 401)
    
    For session-authenticated POST/PUT/DELETE, validates that the X-CSRF-Token
    header matches the csrf cookie value (double-submit cookie pattern).
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    
    if request.url.path in CSRF_EXEMPT_PATHS:
        return
    
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return
    
    config = get_config(request)
    
    session_cookie = request.cookies.get(config.session_cookie_name)
    if not session_cookie:
        return
    
    csrf_cookie = request.cookies.get(config.csrf_cookie_name)
    csrf_header = request.headers.get(CSRF_HEADER_NAME)
    
    if not csrf_cookie or not csrf_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")
    
    if not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token invalid")
