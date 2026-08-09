from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class NotificationEvent(BaseModel):
    """Event queue entry. processed_at=None means pending."""

    __tablename__ = "notification_events"
    __table_args__ = (
        Index("ix_nev_agency_id", "agency_id"),
        Index("ix_nev_processed", "processed_at"),
    )

    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(BaseModel):
    """In-app notification for a specific user."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_user_id", "user_id"),
        Index("ix_notif_agency_id", "agency_id"),
        Index("ix_notif_is_read", "is_read"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationPreference(BaseModel):
    """Per-user notification preferences. One row per user (upsert on access)."""

    __tablename__ = "notification_preferences"
    __table_args__ = (Index("ix_npref_user_id", "user_id", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # {category: {"email": bool, "whatsapp": bool, "in_app": bool}}. Missing categories fall
    # back to the legacy *_enabled flags above (see NotificationPreferenceService).
    category_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class NotificationDelivery(BaseModel):
    """Delivery record per channel per notification event."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_ndel_event_id", "event_id"),
        Index("ix_ndel_notification_id", "notification_id"),
        Index("ix_ndel_provider_message_id", "provider_message_id"),
        Index("ix_ndel_template_key", "template_key"),
        Index("ix_ndel_retry_claim", "channel", "status", "next_retry_at"),
        Index("ix_ndel_agency_status_created", "agency_id", "status", "created_at"),
    )

    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # WhatsApp template-gated test-send flow (Part 6A)
    recipient_phone_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Part 6B-2 — durable link from a delivery row to the user who received
    # it, so Owner delivery history can show a display name without guessing.
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Part 6B-3 — state-machine transition timestamps not covered above.
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Retry bookkeeping (attempt_count/next_retry_at above predate this).
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_exhausted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Template-version snapshot taken at send/retry time, compared against
    # WhatsAppTemplate.revision before a queued retry is allowed to fire.
    template_revision: Mapped[int | None] = mapped_column(nullable=True)
    template_content_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Denormalized from NotificationEvent.agency_id for tenant-scoped
    # retry-claim/metrics queries without a JOIN on every call.
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
    )


class NotificationEventPreference(BaseModel):
    """Per-user, per-event WhatsApp toggle (Part 6B-2).

    Absence of a row for (user_id, event_type) means "not customized" — the
    caller falls back to NotificationPreference.whatsapp_enabled (the master
    toggle). A row here only ever narrows delivery further, never widens it:
    the master toggle and consent (User.whatsapp_opt_in) are still checked
    first in the dispatcher.
    """

    __tablename__ = "notification_event_preferences"
    __table_args__ = (
        Index("ix_nevpref_user_id", "user_id"),
        Index("uq_nevpref_user_event", "user_id", "event_type", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
