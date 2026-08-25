import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "password123!",
        "Password1!",
        "Qwerty1234!",
        "12345678!a",
        "Admin1234!",
        "Welcome1!",
        "Flobrief1!",
        "PostPiloter1!",
        "Passw0rd!",
        "Test1234!",
        "Summer2024!",
    }
)


def _validate_password_strength(v: str) -> str:
    if len(v) < 10:
        raise ValueError("En az 10 karakter olmalıdır")
    if not re.search(r"[A-Z]", v):
        raise ValueError("En az bir büyük harf içermelidir")
    if not re.search(r"[a-z]", v):
        raise ValueError("En az bir küçük harf içermelidir")
    if not re.search(r"\d", v):
        raise ValueError("En az bir rakam içermelidir")
    if not re.search(r"[^a-zA-Z0-9]", v):
        raise ValueError("En az bir özel karakter içermelidir")
    if v in _COMMON_PASSWORDS:
        raise ValueError("Bu şifre çok yaygın")
    return v


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str
    phone_number: str | None = None
    whatsapp_opt_in: bool = False
    locale: Literal["en", "tr"] = "en"

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Ad en az 2 karakter olmalıdır")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        v = re.sub(r"[\s\-\(\)]", "", v)
        if not v.startswith("+"):
            v = "+" + v
        if not re.match(r"^\+[1-9]\d{6,14}$", v):
            raise ValueError("Telefon numarası E.164 formatında olmalı (+90...)")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str = ""
    token_type: str = "bearer"
    expires_in: int = 0
    mfa_required: bool = False
    mfa_session_token: str | None = None


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    job_title: str | None = None
    user_type: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    job_title: str | None = None
    avatar_url: str | None = None
    user_type: str
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    phone_number: str | None = None
    whatsapp_opt_in: bool = False
    locale: Literal["en", "tr"] | None = None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: str | None = None
    job_title: str | None = None
    phone_number: str | None = None
    whatsapp_opt_in: bool | None = None
    locale: Literal["en", "tr"] | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Ad en az 2 karakter olmalıdır")
        return v

    @field_validator("job_title", mode="before")
    @classmethod
    def strip_job(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.strip() or None

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, v: str | None) -> str | None:
        import re

        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        # Normalize: add + if missing, remove spaces/dashes
        v = re.sub(r"[\s\-\(\)]", "", v)
        if not v.startswith("+"):
            v = "+" + v
        if not re.match(r"^\+[1-9]\d{6,14}$", v):
            raise ValueError("Telefon numarası E.164 formatında olmalı (+90...)")
        return v


class PasswordResetRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def validate_current_password(cls, v: str) -> str:
        if not v:
            raise ValueError("Mevcut şifre gereklidir")
        return v

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_strength(v)


class EmailVerifyRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class MessageResponse(BaseModel):
    message: str
