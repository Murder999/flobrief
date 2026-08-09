"""Schemas for Resend email provider API endpoints.

SECURITY INVARIANTS:
- Never include raw API key in response models.
- email_api_key_masked shows only masked representation.
- API key field in request is Optional[str] so callers can omit to keep existing value.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class ResendProviderStatusRead(BaseModel):
    """Safe email provider status. No raw secrets ever returned."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    is_enabled: bool
    is_configured: bool
    api_key_set: bool = False
    email_api_key_masked: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    reply_to: str | None = None
    configured_at: datetime | None = None
    configured_by_user_id: uuid.UUID | None = None
    missing_fields: list[str] = []


class ResendProviderUpdate(BaseModel):
    """Partial update. Omit api_key to keep existing DB value."""

    is_enabled: bool | None = None
    api_key: str | None = None
    from_name: str | None = None
    from_email: str | None = None
    reply_to: str | None = None

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("re_") or len(v) < 10:
            raise ValueError(
                "Resend API anahtarı 're_' ile başlamalı ve geçerli formatta olmalıdır"
            )
        return v

    @field_validator("from_email", mode="before")
    @classmethod
    def validate_from_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir e-posta adresi girin")
        return v.lower()

    @field_validator("reply_to", mode="before")
    @classmethod
    def validate_reply_to(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir reply-to e-posta adresi girin")
        return v.lower()


class ClearEmailSecretRequest(BaseModel):
    field: str = "api_key"


class EmailTestSendRequest(BaseModel):
    to_email: str
    subject: str | None = None
    message: str | None = None

    @field_validator("to_email", mode="before")
    @classmethod
    def validate_to_email(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Geçerli bir alıcı e-posta adresi girin")
        return v.lower()


class EmailTestSendResult(BaseModel):
    status: str
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None
    to_email_masked: str
