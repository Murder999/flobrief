from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    agency_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    event_id: uuid.UUID | None
    title: str
    body: str
    event_type: str
    payload: dict = Field(default_factory=dict)
    is_read: bool
    read_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    action_url: str | None = None


class NotificationListResponse(BaseModel):
    items: list[NotificationRead]
    unread_count: int


class NotificationRealtimeTicketRead(BaseModel):
    ticket: str
    expires_in_seconds: int
    websocket_path: str


class NotificationPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    email_enabled: bool
    whatsapp_enabled: bool
    in_app_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationPreferenceStatusRead(NotificationPreferenceRead):
    """Extends preference read with live provider/user context."""

    whatsapp_provider_active: bool
    has_phone_number: bool
    whatsapp_opt_in: bool


class NotificationPreferenceUpdate(BaseModel):
    email_enabled: bool = True
    whatsapp_enabled: bool = False
    in_app_enabled: bool = True


class NotificationEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    agency_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    payload: dict
    processed_at: datetime | None
    created_at: datetime


class NotificationDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    notification_id: uuid.UUID | None
    channel: str
    status: str
    provider: str
    provider_message_id: str | None
    error_message: str | None
    sent_at: datetime | None
    created_at: datetime


# ── WhatsApp preferences (Part 6B-2) ────────────────────────────────────────


class WhatsAppConsentUpdate(BaseModel):
    opt_in: bool


class WhatsAppConsentRead(BaseModel):
    whatsapp_opt_in: bool
    whatsapp_opt_in_at: datetime | None
    whatsapp_opt_out_at: datetime | None
    whatsapp_consent_source: str | None
    whatsapp_consent_version: str | None


class WhatsAppEventPreferenceRead(BaseModel):
    event_type: str
    event_label: str
    group: str
    group_label: str
    whatsapp_enabled: bool
    template_ready: bool
    is_customized: bool
    updated_at: datetime | None


class WhatsAppEventPreferenceUpdate(BaseModel):
    whatsapp_enabled: bool


class PhoneStatusRead(BaseModel):
    has_phone_number: bool
    phone_masked: str | None
    phone_verified: bool


class WhatsAppUserStatusRead(BaseModel):
    """Full WhatsApp status for the current user's own settings page —
    never includes a raw phone number, secret, or provider response."""

    whatsapp_provider_active: bool
    phone: PhoneStatusRead
    consent: WhatsAppConsentRead
    master_enabled: bool
    is_demo_tenant: bool
    events: list[WhatsAppEventPreferenceRead]
    last_delivery_status: str | None
    last_delivery_at: datetime | None
    last_safe_error: str | None


# ── WhatsApp Owner/Admin management center (Part 6B-2) ──────────────────────


class WhatsAppAgencySummaryRead(BaseModel):
    connection_status: str
    sender_masked: str | None
    environment: str
    opted_in_users: int
    whatsapp_enabled_users: int
    templates_ready: int
    templates_not_ready: int
    deliveries_24h: dict[str, int]
    deliveries_7d: dict[str, int]
    last_safe_error: str | None
    demo_tenant: bool
    retry_queue: int
    retry_exhausted: int
    delivery_success_rate_7d: float | None
    read_rate_7d: float | None
    top_failure_category_7d: str | None


class WhatsAppTemplateMatrixRowRead(BaseModel):
    event_type: str
    event_label: str
    template_key: str
    locale: str
    status: str
    enabled: bool
    has_content_sid: bool
    approved_at: datetime | None
    recipient_policy: str


class WhatsAppTemplatePreviewRead(BaseModel):
    event_type: str
    event_label: str
    template_key: str
    locale: str
    status: str
    sample_message: str
    variable_names: list[str]
    recipient_roles: str
    sensitive_data_note: str


class WhatsAppDeliveryHistoryItemRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    event_type: str
    template_key: str | None
    recipient_phone_masked: str | None
    recipient_display_name: str | None
    provider: str
    status: str
    attempt_count: int
    safe_error: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None


class WhatsAppDeliveryHistoryPage(BaseModel):
    items: list[WhatsAppDeliveryHistoryItemRead]
    total: int
    limit: int
    offset: int
