"""Pytest fixtures: test client, temp DB, config, CSRF helper."""

import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config.schema import Config


class CsrfTestClient:
    """Wrapper around TestClient that automatically handles CSRF tokens."""

    def __init__(self, client: TestClient, csrf_cookie_name: str = "dmarc_csrf"):
        self._client = client
        self._csrf_cookie_name = csrf_cookie_name
        self._csrf_token: str | None = None

    def _get_csrf_token(self) -> str:
        """Get the current CSRF token from cookies."""
        if self._csrf_token:
            return self._csrf_token
        return self._client.cookies.get(self._csrf_cookie_name, "")

    def _update_csrf_from_response(self, response: Any) -> None:
        """Update stored CSRF token from response cookies."""
        if hasattr(response, "cookies") and self._csrf_cookie_name in response.cookies:
            self._csrf_token = response.cookies.get(self._csrf_cookie_name)

    def _add_csrf_header(self, headers: dict | None) -> dict:
        """Add CSRF header to request headers if we have a token."""
        headers = dict(headers) if headers else {}
        csrf = self._get_csrf_token()
        if csrf:
            headers["X-CSRF-Token"] = csrf
        return headers

    def get(self, url: str, **kwargs: Any) -> Any:
        response = self._client.get(url, **kwargs)
        self._update_csrf_from_response(response)
        return response

    def post(self, url: str, headers: dict | None = None, **kwargs: Any) -> Any:
        headers = self._add_csrf_header(headers)
        response = self._client.post(url, headers=headers, **kwargs)
        self._update_csrf_from_response(response)
        return response

    def put(self, url: str, headers: dict | None = None, **kwargs: Any) -> Any:
        headers = self._add_csrf_header(headers)
        response = self._client.put(url, headers=headers, **kwargs)
        self._update_csrf_from_response(response)
        return response

    def delete(self, url: str, headers: dict | None = None, **kwargs: Any) -> Any:
        headers = self._add_csrf_header(headers)
        response = self._client.delete(url, headers=headers, **kwargs)
        self._update_csrf_from_response(response)
        return response

    @property
    def cookies(self) -> Any:
        return self._client.cookies

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def wrap_client_with_csrf(client: TestClient, csrf_cookie_name: str = "dmarc_csrf") -> CsrfTestClient:
    """Wrap a TestClient with CSRF token handling."""
    return CsrfTestClient(client, csrf_cookie_name)


@pytest.fixture
def temp_db_path() -> str:
    """A temporary SQLite database path (unique per test)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    import os
    os.close(fd)
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def test_client() -> TestClient:
    """FastAPI test client for /api/v1 (no DB override; app uses default config at runtime)."""
    return TestClient(app)
