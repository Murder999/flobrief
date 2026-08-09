"""Pydantic schemas for platform-level white-label defaults."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_color(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not _HEX_RE.match(v):
        raise ValueError("Color must be a 6-digit hex value like #6366F1")
    return v.upper()


class PlatformBrandingDefaultsRead(BaseModel):
    portal_name: str | None
    login_title: str | None
    login_description: str | None
    primary_color: str | None
    accent_color: str | None
    background_color: str | None
    surface_color: str | None
    text_color: str | None
    link_color: str | None
    logo_url: str | None
    logo_dark_url: str | None
    favicon_url: str | None
    email_from_name: str | None
    support_email: str | None
    footer_text: str | None
    terms_url: str | None
    privacy_url: str | None
    social_links: dict | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformBrandingDefaultsUpdate(BaseModel):
    portal_name: str | None = None
    login_title: str | None = None
    login_description: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    surface_color: str | None = None
    text_color: str | None = None
    link_color: str | None = None
    email_from_name: str | None = None
    support_email: str | None = None
    footer_text: str | None = None
    terms_url: str | None = None
    privacy_url: str | None = None
    social_links: dict | None = None

    @field_validator(
        "primary_color",
        "accent_color",
        "background_color",
        "surface_color",
        "text_color",
        "link_color",
        mode="before",
    )
    @classmethod
    def validate_colors(cls, v: str | None) -> str | None:
        return _validate_color(v)

    @field_validator("terms_url", "privacy_url", mode="before")
    @classmethod
    def validate_urls(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    @field_validator("support_email", mode="before")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if "@" not in v or " " in v:
            raise ValueError("Invalid email address")
        return v
