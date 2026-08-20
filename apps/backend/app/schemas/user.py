import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.enums import UserType


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    job_title: str | None = None
    user_type: UserType
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    locale: Literal["en", "tr"] | None = None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # password_hash — NEVER exposed
    # mfa_secret_encrypted — NEVER exposed


class UserPublic(BaseModel):
    """Minimal user info safe to embed in other responses."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
