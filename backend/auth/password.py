"""Password hashing and verification (Argon2id per SECURITY_AND_AUDIT)."""

import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


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
