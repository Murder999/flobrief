from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PlatformDemoSettings(BaseModel):
    """Singleton configuration controlled by platform admins."""

    __tablename__ = "platform_demo_settings"
    __table_args__ = (Index("ix_platform_demo_setting_key", "setting_key", unique=True),)

    setting_key: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, default="default"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    duration_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    max_active_sandboxes: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_creations_per_ip_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    captcha_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class DemoSandbox(BaseModel):
    """Lifecycle and abuse-audit record for an isolated demo tenant."""

    __tablename__ = "demo_sandboxes"
    __table_args__ = (
        Index("ix_demo_sandboxes_status_expires", "status", "expires_at"),
        Index("ix_demo_sandboxes_ip_created", "ip_hash", "created_at"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
