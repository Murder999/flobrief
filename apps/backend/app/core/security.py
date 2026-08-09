import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=BCRYPT_ROUNDS),
    ).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("ascii"),
        )
    except (ValueError, TypeError, UnicodeError):
        return False


def create_access_token(
    subject: str | Any,
    extra_claims: dict[str, Any] | None = None,
    expire_minutes: int | None = None,
) -> str:
    minutes = expire_minutes if expire_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(UTC) + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise ValueError("Invalid token type")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc


def generate_secure_token(length: int = 64) -> str:
    return secrets.token_urlsafe(length)


def create_mfa_session_token(user_id: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=2)
    payload: dict[str, Any] = {
        "sub": user_id,
        "type": "mfa_session",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_mfa_session_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "mfa_session":
            raise ValueError("Invalid token type")
        return payload
    except JWTError as exc:
        raise ValueError("Invalid or expired MFA session token") from exc
