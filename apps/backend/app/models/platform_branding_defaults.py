"""Platform-level white-label defaults (singleton, setting_key='default').

Acts as the fallback identity for agencies that have not enabled or fully
configured their own white-label branding (see AgencyBrandingSettings).
Logo/favicon files are stored via the storage backend directly (storage_key)
rather than as Asset rows, since Asset.agency_id is NOT NULL and these
assets are platform-scoped, not agency-scoped.
"""

from __future__ import annotations

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class PlatformBrandingDefaults(BaseModel):
    __tablename__ = "platform_branding_defaults"
    __table_args__ = (Index("ix_platform_branding_setting_key", "setting_key", unique=True),)

    setting_key: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, default="default"
    )

    portal_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    login_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    login_description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    accent_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    background_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    surface_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    text_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    link_color: Mapped[str | None] = mapped_column(String(7), nullable=True)

    logo_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    logo_dark_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_dark_mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    favicon_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    favicon_mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)

    email_from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    footer_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    privacy_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    social_links: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<PlatformBrandingDefaults key={self.setting_key}>"
