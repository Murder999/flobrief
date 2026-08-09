import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.models.enums import UserType  # noqa: E402

TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_EMAIL_VERIFY = "email_verify"
TOKEN_TYPE_PASSWORD_RESET = "password_reset"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def get_refresh_token_expires(user_type: str) -> datetime:
    if user_type == UserType.PLATFORM_ADMIN.value:
        hours = settings.PLATFORM_ADMIN_REFRESH_TOKEN_EXPIRE_HOURS
        return datetime.now(UTC) + timedelta(hours=hours)
    return datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def get_access_token_expire_minutes(user_type: str) -> int:
    if user_type == UserType.PLATFORM_ADMIN.value:
        return settings.PLATFORM_ADMIN_ACCESS_TOKEN_EXPIRE_MINUTES
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES


def new_token_family() -> uuid.UUID:
    return uuid.uuid4()


def get_email_verify_expires() -> datetime:
    return datetime.now(UTC) + timedelta(hours=24)


def get_password_reset_expires() -> datetime:
    return datetime.now(UTC) + timedelta(hours=1)
