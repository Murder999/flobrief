from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class AgencyBrandingSettings(BaseModel):
    """Per-agency white-label branding configuration. One row per agency (upserted)."""

    __tablename__ = "agency_branding_settings"
    __table_args__ = (
        UniqueConstraint("agency_id", name="uq_branding_agency_id"),
        Index("ix_branding_agency_id", "agency_id"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_name_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    email_logo_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    favicon_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    custom_footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_white_label_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    seo_title: Mapped[str | None] = mapped_column(String(60), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(160), nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    google_analytics_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<AgencyBrandingSettings agency_id={self.agency_id}>"


class BrandingAsset(BaseModel):
    """Typed association between an agency and one of its branding assets."""

    __tablename__ = "branding_assets"
    __table_args__ = (Index("ix_ba_agency_id", "agency_id"),)

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)

    def __repr__(self) -> str:
        return f"<BrandingAsset agency_id={self.agency_id} type={self.asset_type}>"


class CustomDomainSettings(BaseModel):
    """Custom domain configuration for white-label agency portals."""

    __tablename__ = "custom_domain_settings"
    __table_args__ = (
        UniqueConstraint("agency_id", name="uq_domain_agency_id"),
        Index("ix_cds_agency_id", "agency_id"),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agencies.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    verification_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<CustomDomainSettings agency_id={self.agency_id} domain={self.domain}>"
