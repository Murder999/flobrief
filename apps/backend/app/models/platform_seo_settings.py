"""Platform SEO and growth settings models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PlatformSeoPageSettings(BaseModel):
    """Per-page SEO metadata managed by platform admin."""

    __tablename__ = "platform_seo_page_settings"
    __table_args__ = (Index("ix_seo_page_key", "page_key", unique=True),)

    page_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    og_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    og_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    twitter_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    twitter_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    indexable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    follow_links: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlatformGrowthSettings(BaseModel):
    """Singleton growth/analytics configuration (setting_key='default')."""

    __tablename__ = "platform_growth_settings"
    __table_args__ = (Index("ix_growth_setting_key", "setting_key", unique=True),)

    setting_key: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, default="default"
    )
    google_analytics_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    google_tag_manager_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    search_console_verification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meta_pixel_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linkedin_partner_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    robots_txt: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitemap_last_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    public_app_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
