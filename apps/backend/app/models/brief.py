from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Brief(BaseModel):
    """A brief document created from a template, scoped to an agency."""

    __tablename__ = "briefs"
    __table_args__ = (
        Index("ix_brief_agency_id", "agency_id"),
        Index("ix_brief_brand_id", "brand_id"),
        Index("ix_brief_status", "status"),
        Index("ix_brief_template_id", "template_id"),
        Index("ix_brief_source", "source"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    deadline: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    draft_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    feedback_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    publish_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    platforms: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    content_types: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    source: Mapped[str | None] = mapped_column(String(30), nullable=True, default="agency")
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    estimated_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_hours_by_category: Mapped[dict[str, float] | None] = mapped_column(
        JSONB, nullable=True
    )

    def __repr__(self) -> str:
        return f"<Brief id={self.id} title={self.title!r} status={self.status}>"


class BriefFieldValue(BaseModel):
    """Stores the value a user filled in for one template field on a brief."""

    __tablename__ = "brief_field_values"
    __table_args__ = (
        UniqueConstraint("brief_id", "template_field_id", name="uq_brief_field_value"),
        Index("ix_bfv_brief_id", "brief_id"),
    )

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_template_fields.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<BriefFieldValue brief_id={self.brief_id} field_id={self.template_field_id}>"


class BriefAssignee(BaseModel):
    """An agency member assigned to work on a brief."""

    __tablename__ = "brief_assignees"
    __table_args__ = (
        UniqueConstraint("brief_id", "user_id", name="uq_brief_assignee"),
        Index("ix_brief_assignee_brief_id", "brief_id"),
    )

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    participant_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    can_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_approve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_request_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<BriefAssignee brief_id={self.brief_id} user_id={self.user_id}>"
