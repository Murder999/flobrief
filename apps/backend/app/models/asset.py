from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Asset(BaseModel):
    """File asset uploaded by an agency user. Storage-provider-agnostic."""

    __tablename__ = "assets"
    __table_args__ = (Index("ix_asset_agency_id", "agency_id"),)

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
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # internal (agency-only) | client_visible | brand_reference
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    # Image pixel dimensions, extracted via Pillow at upload time (app/services/
    # media_metadata.py). Null for non-image files or when extraction fails —
    # never fabricated. Video duration is intentionally not captured in this pass.
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Asset id={self.id} filename={self.filename}>"


class AssetVersion(BaseModel):
    """Immutable snapshot of a new file version for an existing asset."""

    __tablename__ = "asset_versions"
    __table_args__ = (Index("ix_av_asset_id", "asset_id"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<AssetVersion asset_id={self.asset_id} v{self.version_number}>"


class AssetLink(BaseModel):
    """Associates an asset with a brief, calendar item, or comment."""

    __tablename__ = "asset_links"
    __table_args__ = (Index("ix_al_asset_id", "asset_id"),)

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("briefs.id", ondelete="CASCADE"),
        nullable=True,
    )
    # calendar_item_id FK to content_posts added in Part 9
    calendar_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="SET NULL"),
        nullable=True,
    )
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deliverables.id", ondelete="CASCADE"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<AssetLink asset_id={self.asset_id} brief_id={self.brief_id}>"
