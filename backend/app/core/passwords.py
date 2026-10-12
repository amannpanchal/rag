"""Versioned PBKDF2 password hashing using only Python's standard library."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 600_000
_SALT_BYTES = 16
_KEY_BYTES = 32


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_KEY_BYTES)
    return "$".join((
        _ALGORITHM,
        str(_ITERATIONS),
        base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
        base64.urlsafe_b64encode(derived).decode("ascii").rstrip("="),
    ))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, expected_text = password_hash.split("$", 3)
        iterations = int(iteration_text)
        if algorithm != _ALGORITHM or iterations != _ITERATIONS:
            return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(expected_text + "=" * (-len(expected_text) % 4))
        if len(salt) != _SALT_BYTES or len(expected) != _KEY_BYTES:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=_KEY_BYTES)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
