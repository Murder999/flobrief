from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

_VALID_STATUSES = {"todo", "in_progress", "done", "blocked"}
_VALID_VISIBILITIES = {"internal", "client_visible"}


class BriefTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None
    status: str = "todo"
    visibility: str = "internal"
    is_milestone: bool = False
    estimated_hours: float | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Görev başlığı boş olamaz")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"Geçersiz durum: {v}. Geçerli: {_VALID_STATUSES}")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str) -> str:
        if v not in _VALID_VISIBILITIES:
            raise ValueError(f"Geçersiz görünürlük: {v}")
        return v


class BriefTaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    assigned_to_id: uuid.UUID | None = None
    due_date: date | None = None
    status: str | None = None
    visibility: str | None = None
    is_milestone: bool | None = None
    estimated_hours: float | None = None

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Görev başlığı boş olamaz")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"Geçersiz durum: {v}")
        return v

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_VISIBILITIES:
            raise ValueError(f"Geçersiz görünürlük: {v}")
        return v


class BriefTaskRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID
    title: str
    description: str | None
    assigned_to_id: uuid.UUID | None
    due_date: date | None
    status: str
    visibility: str
    created_by_id: uuid.UUID | None
    is_milestone: bool
    estimated_hours: float | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
