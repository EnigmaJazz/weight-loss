"""Password hashing and session-token helpers (pure module, no I/O).

Mirrors the rewards.py convention: pure logic lives outside the storage
layer so it can be unit-tested without a database. All scrypt parameters
are centralized in constants.py and stay testable.
"""

import hashlib
import hmac
import secrets

from constants import (
    RESET_TOKEN_BYTES,
    SCRIPT_DKLEN,
    SCRIPT_N,
    SCRIPT_P,
    SCRIPT_R,
    SESSION_TOKEN_BYTES,
)


def generate_password_salt() -> str:
    """Return a fresh random 16-byte salt, hex-encoded (32 chars)."""
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    """Derive the scrypt hash of ``password`` with ``salt``, hex-encoded."""
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=SCRIPT_N,
        r=SCRIPT_R,
        p=SCRIPT_P,
        dklen=SCRIPT_DKLEN,
    )
    return derived.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Constant-time comparison of a freshly derived hash against the stored one."""
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, expected_hash)


def generate_session_token() -> str:
    """Return a fresh random session secret (never persisted in plaintext)."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """Return the SHA-256 hex digest that is stored instead of the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_reset_token() -> str:
    """Return a fresh random one-time password-reset secret (never persisted)."""
    return secrets.token_urlsafe(RESET_TOKEN_BYTES)


def hash_reset_token(token: str) -> str:
    """Return the SHA-256 hex digest that is stored instead of the raw token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
