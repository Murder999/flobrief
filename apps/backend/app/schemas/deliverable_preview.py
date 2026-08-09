from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator, model_validator

# Platforms the Preview Center actually renders a real chrome for. Reuses the
# existing CalendarPlatform enum's values rather than a new enum — this set
# is just the subset CalendarPlatform supports for preview purposes (e.g.
# "youtube"/"website"/"email"/"other" are deliberately excluded: no
# per-platform preview component exists for them).
_SUPPORTED_PREVIEW_PLATFORMS: set[str] = {
    "instagram",
    "facebook",
    "tiktok",
    "linkedin",
    "x",
}

# Platform -> set of PreviewFormat values that platform actually supports.
# The single config-driven mechanism that keeps an unsupported platform x
# format combination from ever reaching a fake preview: both the API layer
# (here) and the frontend's previewPlatformConfig.ts enforce this same shape.
_PLATFORM_FORMATS: dict[str, set[str]] = {
    "instagram": {"feed_single", "feed_carousel", "story", "reel", "reel_cover", "grid"},
    "facebook": {"feed_single", "feed_carousel", "story"},
    "linkedin": {"feed_single", "feed_carousel", "document_carousel", "text_post"},
    "x": {"feed_single", "feed_carousel", "text_post"},
    "tiktok": {"reel", "reel_cover"},
}

_CAROUSEL_FORMATS: set[str] = {"feed_carousel", "grid", "document_carousel"}

_MAX_HASHTAGS = 30
_MAX_CAPTION_LEN = 5_000


class PreviewWarning(BaseModel):
    """A single internal-heuristic warning — never an enforced platform limit."""

    code: str
    message: str
    severity: str = "warning"  # info | warning


class PreviewConfigUpsert(BaseModel):
    platform: str
    preview_format: str
    caption: str | None = None
    title: str | None = None
    cta_label: str | None = None
    hashtags: list[str] | None = None
    display_name_override: str | None = None
    profile_photo_asset_id: uuid.UUID | None = None
    cover_asset_id: uuid.UUID | None = None

    @field_validator("platform")
    @classmethod
    def valid_platform(cls, v: str) -> str:
        if v not in _SUPPORTED_PREVIEW_PLATFORMS:
            raise ValueError(f"platform must be one of: {sorted(_SUPPORTED_PREVIEW_PLATFORMS)}")
        return v

    @field_validator("caption")
    @classmethod
    def caption_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > _MAX_CAPTION_LEN:
            raise ValueError(f"caption must be {_MAX_CAPTION_LEN} chars or less")
        return v

    @field_validator("title")
    @classmethod
    def title_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError("title must be 255 chars or less")
        return v

    @field_validator("hashtags")
    @classmethod
    def hashtags_bounded(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > _MAX_HASHTAGS:
            raise ValueError(f"hashtags list must contain at most {_MAX_HASHTAGS} entries")
        return v

    @model_validator(mode="after")
    def platform_format_combination(self) -> PreviewConfigUpsert:
        allowed = _PLATFORM_FORMATS.get(self.platform, set())
        if self.preview_format not in allowed:
            raise ValueError(
                f"preview_format '{self.preview_format}' is not supported for "
                f"platform '{self.platform}'. Supported: {sorted(allowed)}"
            )
        return self


class PreviewConfigRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID
    deliverable_id: uuid.UUID
    platform: str
    preview_format: str
    caption: str | None
    title: str | None
    cta_label: str | None
    hashtags: list[str] | None
    display_name_override: str | None
    profile_photo_asset_id: uuid.UUID | None
    cover_asset_id: uuid.UUID | None
    revision_number: int
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    warnings: list[PreviewWarning] = []

    model_config = {"from_attributes": True}


class PreviewSlotRead(BaseModel):
    id: uuid.UUID
    deliverable_id: uuid.UUID
    asset_id: uuid.UUID
    position: int
    is_cover: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PreviewSlotItem(BaseModel):
    asset_id: uuid.UUID
    position: int
    is_cover: bool = False

    @field_validator("position")
    @classmethod
    def position_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("position must be >= 0")
        return v


class PreviewSlotsReorder(BaseModel):
    slots: list[PreviewSlotItem]

    @field_validator("slots")
    @classmethod
    def unique_assets(cls, v: list[PreviewSlotItem]) -> list[PreviewSlotItem]:
        asset_ids = [s.asset_id for s in v]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValueError("each asset_id may appear at most once in slots")
        cover_count = sum(1 for s in v if s.is_cover)
        if cover_count > 1:
            raise ValueError("at most one slot may be marked as cover")
        return v
