"""Brand DNA change-proposal workflow (non-manager suggestions on a BrandIdentityProfile)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class BrandIdentitySuggestion(BaseModel):
    """A proposed set of field changes to a BrandIdentityProfile, pending manager review."""

    __tablename__ = "brand_identity_suggestions"
    __table_args__ = (
        Index("ix_bis_profile_id", "profile_id"),
        Index("ix_bis_status", "status"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_identity_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # {field_name: proposed_value} — only fields the proposer changed
    proposed_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    # pending | accepted | partially_accepted | rejected | comment_requested
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    # subset of proposed_fields keys actually applied (set on accept/partial-accept)
    applied_fields: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return (
            f"<BrandIdentitySuggestion id={self.id} "
            f"profile_id={self.profile_id} status={self.status}>"
        )
