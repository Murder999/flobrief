from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class CommentThread(BaseModel):
    """Container for a discussion thread scoped to a brief, field, asset, or approval."""

    __tablename__ = "comment_threads"
    __table_args__ = (
        Index("ix_ct_agency_id", "agency_id"),
        Index("ix_ct_brief_id", "brief_id"),
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
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=True,
    )
    approval_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # asset_id stored without FK to avoid circular dependency; validated in service
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    thread_type: Mapped[str] = mapped_column(String(20), nullable=False, default="brief")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CommentThread id={self.id} type={self.thread_type} status={self.status}>"


class Comment(BaseModel):
    """A single comment within a thread. Supports soft-delete for moderation."""

    __tablename__ = "comments"
    __table_args__ = (Index("ix_comment_thread_id", "thread_id"),)

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comment_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_job_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # internal = agency-only; client_visible = brand/public can see
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")

    def __repr__(self) -> str:
        return f"<Comment id={self.id} visibility={self.visibility}>"
