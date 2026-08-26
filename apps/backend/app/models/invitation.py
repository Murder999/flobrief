from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Invitation(BaseModel):
    """Invitation to join an agency or brand. token_hash stores SHA-256 of plaintext."""

    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_invitation_token_hash"),
        Index("ix_invitation_agency_email", "agency_id", "email"),
        Index("ix_invitation_expires_at", "expires_at"),
    )

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    invitation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="agency",  # agency | brand
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    resent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def is_pending(self) -> bool:
        from datetime import UTC

        now = datetime.now(UTC)
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.rejected_at is None
            and self.deleted_at is None
            and self.expires_at > now
        )

    @property
    def is_accepted(self) -> bool:
        return self.accepted_at is not None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_rejected(self) -> bool:
        return self.rejected_at is not None

    def __repr__(self) -> str:
        return f"<Invitation agency={self.agency_id} email={self.email} role={self.role}>"
