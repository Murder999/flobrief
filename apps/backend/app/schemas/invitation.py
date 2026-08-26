from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

from app.models.enums import AgencyMemberRole, BrandMemberRole
from app.schemas.auth import _validate_password_strength


class AgencyInviteRequest(BaseModel):
    email: EmailStr
    role: str
    message: str | None = Field(None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_agency_role(cls, v: str) -> str:
        valid = {r.value for r in AgencyMemberRole}
        if v not in valid:
            msg = f"Invalid agency role. Valid: {sorted(valid)}"
            raise ValueError(msg)
        return v


class BrandInviteRequest(BaseModel):
    email: EmailStr
    role: str
    message: str | None = Field(None, max_length=500)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("role")
    @classmethod
    def validate_brand_role(cls, v: str) -> str:
        valid = {r.value for r in BrandMemberRole}
        if v not in valid:
            msg = f"Invalid brand role. Valid: {sorted(valid)}"
            raise ValueError(msg)
        return v


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    invitation_type: str
    email: str
    role: str
    invited_by: uuid.UUID
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    rejected_at: datetime | None
    resent_count: int
    created_at: datetime
    is_pending: bool


class InvitationPreview(BaseModel):
    """Public (no-auth) view of an invitation for the accept flow."""

    model_config = ConfigDict(from_attributes=True)

    agency_name: str
    brand_name: str | None
    invitation_type: Literal["agency", "brand"]
    email: str
    role: str
    expires_at: datetime
    state: Literal["pending", "accepted", "expired", "revoked", "declined"]
    account_exists: bool | None
    account_type_compatible: bool | None


class InvitationSignupRequest(BaseModel):
    full_name: str
    password: str
    password_confirmation: str
    phone_number: str | None = None
    whatsapp_opt_in: bool = False
    locale: Literal["en", "tr"] = "en"

    @field_validator("full_name", mode="before")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 2:
            raise ValueError("Ad en az 2 karakter olmalıdır")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("password_confirmation")
    @classmethod
    def validate_password_confirmation(cls, value: str) -> str:
        return _validate_password_strength(value)

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        import re

        if value is None:
            return None
        normalized = re.sub(r"[\s\-\(\)]", "", value.strip())
        if not normalized:
            return None
        if not normalized.startswith("+"):
            normalized = "+" + normalized
        if not re.match(r"^\+[1-9]\d{6,14}$", normalized):
            raise ValueError("Telefon numarası E.164 formatında olmalı (+90...)")
        return normalized

    @field_validator("password_confirmation")
    @classmethod
    def passwords_match(cls, value: str, info: ValidationInfo) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("Şifreler eşleşmiyor")
        return value


class InvitationExistingAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class InvitationSignupResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    redirect_to: Literal["/dashboard", "/brand/dashboard"]
