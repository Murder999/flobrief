"""Schemas for WhatsApp/Twilio provider API endpoints.

SECURITY INVARIANTS:
- Never include raw auth_token, account_sid, or webhook_verify_token in response models.
- Secret fields in request models are Optional[str] so callers can omit to keep existing value.
- account_sid_masked shows only last 4 chars ("AC************1234").
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.enums import WhatsAppProviderType

_E164_OR_WHATSAPP_RE = re.compile(r"^(whatsapp:)?\+?[1-9]\d{6,14}$")
_MIN_VERIFY_TOKEN_LEN = 8


class TwilioProviderStatusRead(BaseModel):
    """Safe provider status. No raw secrets ever returned."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    provider_type: str
    is_enabled: bool
    is_configured: bool
    connection_status: str = "not_configured"
    account_sid_masked: str | None = None
    whatsapp_from_masked: str | None = None
    auth_token_set: bool = False
    webhook_verify_token_set: bool = False
    messaging_service_sid_set: bool = False
    configured_at: datetime | None = None
    configured_by_user_id: uuid.UUID | None = None
    last_connection_check_at: datetime | None = None
    last_connection_error: str | None = None
    missing_fields: list[str] = []


class ConnectionVerifyResult(BaseModel):
    connection_status: str
    detail: str | None = None
    checked_at: datetime


class TwilioProviderUpdate(BaseModel):
    """Partial update. Omit a secret field to keep existing DB value.
    Pass null to clear (use separate /clear-secret endpoint for safety).
    """

    provider_type: WhatsAppProviderType | None = None
    is_enabled: bool | None = None

    # Secrets — optional so caller can update non-secret fields without re-entering secrets
    account_sid: str | None = None
    auth_token: str | None = None
    whatsapp_from: str | None = None
    messaging_service_sid: str | None = None
    webhook_verify_token: str | None = None

    @field_validator("account_sid", mode="before")
    @classmethod
    def validate_sid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v.startswith("AC") or len(v) < 10:
            raise ValueError("Account SID geçersiz (AC... formatında olmalı)")
        return v

    @field_validator("whatsapp_from", mode="before")
    @classmethod
    def validate_from(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not _E164_OR_WHATSAPP_RE.match(v):
            raise ValueError("whatsapp_from geçersiz format (whatsapp:+... veya +...)")
        return v

    @field_validator("webhook_verify_token", mode="before")
    @classmethod
    def validate_verify_token(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if len(v) < _MIN_VERIFY_TOKEN_LEN:
            raise ValueError(f"Verify token en az {_MIN_VERIFY_TOKEN_LEN} karakter olmalı")
        return v


class ClearSecretRequest(BaseModel):
    field: Literal[
        "auth_token",
        "account_sid",
        "whatsapp_from",
        "messaging_service_sid",
        "webhook_verify_token",
    ]


class WhatsAppTestSendRequest(BaseModel):
    to_phone: str
    message: str | None = None

    @field_validator("to_phone", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not _E164_OR_WHATSAPP_RE.match(v):
            raise ValueError("Telefon numarası geçersiz (E.164: +905... veya whatsapp:+905...)")
        return v


class WhatsAppTestSendResult(BaseModel):
    status: str
    provider: str
    provider_message_id: str | None = None
    error_message: str | None = None
    to_phone_masked: str


class WebhookEventRead(BaseModel):
    processed: bool
    provider_message_id: str | None = None
    delivery_status: str | None = None
    # Part 6B-3 — True when the reported status was actually written to the
    # delivery row. False for a duplicate/out-of-order/regressive callback
    # (see whatsapp_delivery_state_machine) or an unrecognized raw status —
    # the callback is still acknowledged (200) either way so Twilio never
    # retries, but the caller can tell whether anything changed.
    applied: bool = True
