from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.asset import AssetRead


class DeliverableCreate(BaseModel):
    title: str
    description: str | None = None
    description_html: str | None = None
    deliverable_type: str = "other"

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Başlık boş olamaz")
        if len(v) > 500:
            raise ValueError("Başlık 500 karakterden fazla olamaz")
        return v

    @field_validator("deliverable_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in {"image", "video", "text", "document", "link", "other"}:
            raise ValueError("Geçersiz deliverable türü")
        return v


class DeliverableUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    description_html: str | None = None
    deliverable_type: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Başlık boş olamaz")
        return v

    @field_validator("deliverable_type")
    @classmethod
    def valid_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in {"image", "video", "text", "document", "link", "other"}:
            raise ValueError("Geçersiz deliverable türü")
        return v


class BrandApproveDeliverableRequest(BaseModel):
    note: str | None = None


class BrandReviseDeliverableRequest(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Revizyon nedeni boş olamaz")
        if len(v) > 5000:
            raise ValueError("Revizyon nedeni 5000 karakterden fazla olamaz")
        return v


class DeliverableRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID
    title: str
    description: str | None
    description_html: str | None
    deliverable_type: str
    status: str
    version_number: int
    revision_count: int
    revision_note: str | None
    approve_note: str | None
    # True unless another deliverable in this brief shares the same title
    # (normalized) and was submitted/created more recently — see
    # app/services/deliverable_versioning.py for the computation.
    is_latest_version: bool = True
    created_by_id: uuid.UUID | None = None
    submitted_by_id: uuid.UUID | None
    submitted_at: datetime | None
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    assets: list[AssetRead] = []

    model_config = {"from_attributes": True}
