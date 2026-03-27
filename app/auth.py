from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time


SESSION_COOKIE_NAME = "lightwebhook_session"


def _sign_value(payload: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def validate_admin_secret(candidate: str | None, configured_secret: str) -> bool:
    return bool(candidate) and secrets.compare_digest(candidate, configured_secret)


def get_session_max_age_seconds() -> int:
    raw_value = os.getenv("SESSION_MAX_AGE_SECONDS", "43200").strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError("SESSION_MAX_AGE_SECONDS must be an integer") from exc

    if value <= 0:
        raise ValueError("SESSION_MAX_AGE_SECONDS must be greater than zero")

    return value


def get_session_cookie_secure() -> bool:
    return os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes", "on"}


def create_session_token(configured_secret: str) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    payload = f"{issued_at}.{nonce}"
    signature = _sign_value(payload, configured_secret)
    return f"{payload}.{signature}"


def validate_session_token(token: str | None, configured_secret: str) -> bool:
    if not token:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False

    issued_at, nonce, signature = parts
    if not issued_at.isdigit() or not nonce or not signature:
        return False

    payload = f"{issued_at}.{nonce}"
    expected_signature = _sign_value(payload, configured_secret)
    if not secrets.compare_digest(signature, expected_signature):
        return False

    token_age = int(time.time()) - int(issued_at)
    if token_age < 0:
        return False

    return token_age <= get_session_max_age_seconds()
