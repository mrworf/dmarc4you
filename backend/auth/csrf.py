"""CSRF token generation and validation using double-submit cookie pattern."""

import secrets

CSRF_TOKEN_BYTES = 32
CSRF_HEADER_NAME = "X-CSRF-Token"


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)
