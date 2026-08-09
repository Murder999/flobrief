from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_color(v: str | None) -> str | None:
    if v is None:
        return None
    if not _HEX_RE.match(v):
        raise ValueError("Color must be a 6-digit hex value like #6366F1")
    return v.upper()


class BrandingSettingsRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_name_override: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    logo_url: str | None
    email_logo_url: str | None
    favicon_url: str | None
    custom_footer_text: str | None
    is_white_label_enabled: bool
    white_label_entitlement: bool
    seo_title: str | None = None
    seo_description: str | None = None
    og_image_url: str | None = None
    google_analytics_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandingSettingsUpdate(BaseModel):
    brand_name_override: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    accent_color: str | None = None
    custom_footer_text: str | None = None
    is_white_label_enabled: bool | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    og_image_url: str | None = None
    google_analytics_id: str | None = None

    @field_validator("primary_color", "secondary_color", "accent_color", mode="before")
    @classmethod
    def validate_colors(cls, v: str | None) -> str | None:
        return _validate_color(v)


class BrandingAssetRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    asset_id: uuid.UUID
    asset_type: str
    asset_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomDomainRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    domain: str
    status: str
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomDomainCreate(BaseModel):
    domain: str

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or len(v) > 255:
            raise ValueError("Domain must be between 1 and 255 characters")
        return v


class CustomDomainCreated(CustomDomainRead):
    verification_token: str


class PublicBrandingView(BaseModel):
    """Safe public view — no internal IDs, only what the public portal needs."""

    agency_name: str
    brand_name: str | None
    primary_color: str | None
    secondary_color: str | None
    accent_color: str | None
    logo_url: str | None
    favicon_url: str | None
    custom_footer_text: str | None
    is_branded: bool
