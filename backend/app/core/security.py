"""Password hashing (PBKDF2-HMAC-SHA256) and JWT helpers.

Uses only the standard library to avoid native build issues; PBKDF2 with
per-password salt is appropriate for this service's single-role demo auth.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Any

import jwt

from app.core.config import settings

_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt, digest = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def create_access_token(subject: str, role: str = "merchant") -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + settings.access_token_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])


def sign_webhook_payload(raw_body: bytes, secret: str | None = None) -> str:
    secret_bytes = (secret or settings.webhook_secret).encode()
    return hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str | None = None) -> bool:
    expected = sign_webhook_payload(raw_body, secret)
    return hmac.compare_digest(expected, signature or "")
