from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PartnershipInvitation(BaseModel):
    """Single-use invitation that links one brand to one operational agency."""

    __tablename__ = "partnership_invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_partnership_invitation_token_hash"),
        CheckConstraint(
            "(direction = 'agency_invites_brand' AND agency_id IS NOT NULL AND brand_id IS NULL) "
            "OR (direction = 'brand_invites_agency' AND brand_id IS NOT NULL "
            "AND agency_id IS NULL)",
            name="ck_partnership_invitation_source",
        ),
        Index("ix_partnership_invitation_email", "email"),
        Index("ix_partnership_invitation_expires_at", "expires_at"),
    )

    direction: Mapped[str] = mapped_column(String(40), nullable=False)
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
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_pending(self) -> bool:
        return (
            self.accepted_at is None
            and self.revoked_at is None
            and self.deleted_at is None
            and self.expires_at > datetime.now(UTC)
        )
