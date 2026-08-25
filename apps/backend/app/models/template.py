from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class EmailTemplate(BaseModel):
    """DB-stored email templates using $variable substitution syntax (stdlib string.Template)."""

    __tablename__ = "email_templates"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WhatsAppTemplate(BaseModel):
    """Approved-template registry for WhatsApp Business API sends (Part 6A).

    `code` is the template_key used by callers. A row's `status` gates whether it
    may be used for a real send — only `approved` templates with a `content_sid`
    are usable. Event→template mapping (populating `event_type` for real PostPiloter
    events beyond the seeded test template) is Part 6B scope; see docs/DECISIONS.md.
    """

    __tablename__ = "whatsapp_templates"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="twilio")
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), nullable=False, default="tr")
    content_sid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    variable_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Part 6B-3 — bumped by WhatsAppTemplateRepository.update_approval whenever
    # status or content_sid actually changes. A queued retry snapshots this
    # value at send time (NotificationDelivery.template_revision) and refuses
    # to fire if the template has since moved to a different revision.
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
