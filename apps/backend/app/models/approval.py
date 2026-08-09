from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class BriefVersion(BaseModel):
    """Immutable snapshot of a brief taken when it is sent for approval."""

    __tablename__ = "brief_versions"
    __table_args__ = (Index("ix_bv_brief_id", "brief_id"),)

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<BriefVersion brief_id={self.brief_id} v{self.version_number}>"


class BriefChangeLog(BaseModel):
    """Records individual field-level changes on a brief."""

    __tablename__ = "brief_change_logs"
    __table_args__ = (Index("ix_bcl_brief_id", "brief_id"),)

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    field_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<BriefChangeLog brief_id={self.brief_id} field={self.field_key}>"


class Approval(BaseModel):
    """Represents one approval request cycle for a brief."""

    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approval_brief_id", "brief_id"),)

    brief_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brief_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="public_token")
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Approval brief_id={self.brief_id} status={self.status}>"


class ApprovalToken(BaseModel):
    """Stores hashed token for a public approval link. Raw token never stored."""

    __tablename__ = "approval_tokens"
    __table_args__ = (Index("ix_at_token_hash", "token_hash", unique=True),)

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ApprovalToken approval_id={self.approval_id}>"


class ApprovalEvent(BaseModel):
    """Immutable audit log for actions on an approval."""

    __tablename__ = "approval_events"
    __table_args__ = (Index("ix_ae_approval_id", "approval_id"),)

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<ApprovalEvent approval_id={self.approval_id} type={self.event_type}>"


class ApprovalComment(BaseModel):
    """Comment left on an approval — either by public reviewer or internal agency user."""

    __tablename__ = "approval_comments"
    __table_args__ = (Index("ix_ac_approval_id", "approval_id"),)

    approval_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("approvals.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<ApprovalComment approval_id={self.approval_id}>"
