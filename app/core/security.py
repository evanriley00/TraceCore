from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings


def _pbkdf2_digest(value: str, salt: str, iterations: int = 600_000) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        value.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return digest.hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 600_000
    digest = _pbkdf2_digest(password, salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(password: str, encoded_password: str) -> bool:
    scheme, raw_iterations, salt, expected = encoded_password.split("$", maxsplit=3)
    if scheme != "pbkdf2_sha256":
        return False
    candidate = _pbkdf2_digest(password, salt, int(raw_iterations))
    return secrets.compare_digest(candidate, expected)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return "tc_" + secrets.token_urlsafe(32)


def create_access_token(subject: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

