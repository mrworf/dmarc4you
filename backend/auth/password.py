"""Password hashing, validation, and verification (Argon2id per SECURITY_AND_AUDIT)."""

import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


def validate_new_password(password: str) -> str | None:
    """Return a machine-readable validation error or None when the password is acceptable."""
    length = len(password)
    if length < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if length > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    return None


def hash_password(password: str) -> str:
    """Return Argon2id hash of password."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if password matches hash."""
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False


def generate_random_password(length: int = 24) -> str:
    """Return a cryptographically random password (for bootstrap admin)."""
    return secrets.token_urlsafe(length)
