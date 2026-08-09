"""Brand Identity / Marka DNA models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class BrandIdentityDocument(BaseModel):
    """Corporate identity PDF uploaded for brand DNA extraction."""

    __tablename__ = "brand_identity_documents"
    __table_args__ = (Index("ix_bid_brand_id", "brand_id"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # uploaded | processing | analyzed | needs_review | approved | failed
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(30), nullable=True)
    extraction_debug_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<BrandIdentityDocument id={self.id} brand_id={self.brand_id}>"


class BrandIdentityProfile(BaseModel):
    """Extracted and editable brand DNA profile for a brand."""

    __tablename__ = "brand_identity_profiles"
    __table_args__ = (Index("ix_bip_brand_id", "brand_id"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_identity_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # draft | ai_generated | reviewed | approved
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_colors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    secondary_colors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    typography: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    logo_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    visual_style: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tone_of_voice: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    social_media_notes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    do_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    dont_rules: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    key_takeaways: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<BrandIdentityProfile id={self.id} brand_id={self.brand_id} status={self.status}>"


class BrandIdentityRevision(BaseModel):
    """Immutable audit record of every change to a BrandIdentityProfile."""

    __tablename__ = "brand_identity_revisions"
    __table_args__ = (Index("ix_bir_profile_id", "profile_id"),)

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_identity_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_by_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<BrandIdentityRevision id={self.id} profile_id={self.profile_id}>"
