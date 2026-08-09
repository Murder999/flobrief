from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AssetRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    uploaded_by_id: uuid.UUID | None
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    storage_provider: str
    checksum: str | None
    width_px: int | None = None
    height_px: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetVersionRead(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    version_number: int
    filename: str
    mime_type: str
    size_bytes: int
    checksum: str | None
    uploaded_by_id: uuid.UUID | None
    width_px: int | None = None
    height_px: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AssetLinkRead(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    brief_id: uuid.UUID | None
    calendar_item_id: uuid.UUID | None
    comment_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
