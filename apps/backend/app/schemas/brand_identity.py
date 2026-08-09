"""Schemas for Brand Identity / Marka DNA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ColorEntry(BaseModel):
    name: str | None = None
    hex: str | None = None
    rgb: str | None = None
    cmyk: str | None = None
    usage: str | None = None


class FontEntry(BaseModel):
    role: str | None = None
    family: str | None = None
    weight: str | None = None
    usage: str | None = None


class BrandIdentityDocumentRead(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    agency_id: uuid.UUID | None
    uploaded_by_id: uuid.UUID | None
    file_name: str
    file_size: int
    content_type: str
    status: str
    analysis_error: str | None
    page_count: int | None = None
    extraction_method: str | None = None
    extraction_debug_json: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandIdentityProfileRead(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    agency_id: uuid.UUID | None
    source_document_id: uuid.UUID | None
    status: str
    summary: str | None
    primary_colors: list[Any] | None
    secondary_colors: list[Any] | None
    typography: list[Any] | None
    logo_rules: list[Any] | None
    visual_style: dict[str, Any] | None
    tone_of_voice: dict[str, Any] | None
    social_media_notes: list[Any] | None
    do_rules: list[Any] | None
    dont_rules: list[Any] | None
    key_takeaways: list[Any] | None
    confidence_score: int | None
    is_active: bool
    reviewed_by_id: uuid.UUID | None
    approved_by_id: uuid.UUID | None
    reviewed_at: datetime | None
    approved_at: datetime | None
    approved_by_name: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandIdentityProfileUpdate(BaseModel):
    summary: str | None = None
    primary_colors: list[Any] | None = None
    secondary_colors: list[Any] | None = None
    typography: list[Any] | None = None
    logo_rules: list[Any] | None = None
    visual_style: dict[str, Any] | None = None
    tone_of_voice: dict[str, Any] | None = None
    social_media_notes: list[Any] | None = None
    do_rules: list[Any] | None = None
    dont_rules: list[Any] | None = None
    key_takeaways: list[Any] | None = None
    change_note: str | None = None


class BrandIdentityRevisionRead(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    changed_by_id: uuid.UUID | None
    changed_by_name: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    change_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandIdentityOverview(BaseModel):
    profile: BrandIdentityProfileRead | None
    documents: list[BrandIdentityDocumentRead]


class BrandDNASummary(BaseModel):
    """Lightweight DNA summary for use in brief/deliverable panels."""

    profile_id: uuid.UUID | None
    status: str | None
    summary: str | None
    primary_colors: list[Any] | None
    typography: list[Any] | None
    tone_of_voice: dict[str, Any] | None
    key_takeaways: list[Any] | None
    dont_rules: list[Any] | None
    approved_by_name: str | None
    approved_at: datetime | None
