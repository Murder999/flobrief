from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.models.enums import TimeEntryCategory, WorkAllocationSource

_VALID_CATEGORIES = {c.value for c in TimeEntryCategory}
_VALID_SOURCES = {s.value for s in WorkAllocationSource}


class WorkAllocationCreate(BaseModel):
    """Schema only in Phase 1 — `WorkAllocationService`/API ship in Phase 2.
    A brief/task/deliverable-less "general capacity block" (internal ops
    time) is a valid allocation on purpose."""

    user_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    brief_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    deliverable_id: uuid.UUID | None = None
    category: str | None = None
    start_date: date
    end_date: date
    allocated_minutes: int = Field(..., gt=0)
    allocation_source: str = WorkAllocationSource.MANUAL.value
    locked: bool = False

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v

    @field_validator("allocation_source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in _VALID_SOURCES:
            raise ValueError(f"Geçersiz kaynak: {v}")
        return v

    @field_validator("end_date")
    @classmethod
    def validate_end_after_start(cls, v: date, info: ValidationInfo) -> date:
        start_date = info.data.get("start_date")
        if start_date is not None and v < start_date:
            raise ValueError("Bitiş tarihi başlangıçtan önce olamaz")
        return v


class WorkAllocationUpdate(BaseModel):
    category: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    allocated_minutes: int | None = Field(None, gt=0)
    locked: bool | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v


class WorkAllocationRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID | None
    task_id: uuid.UUID | None
    deliverable_id: uuid.UUID | None
    user_id: uuid.UUID
    category: str | None
    start_date: date
    end_date: date
    allocated_minutes: int
    allocation_source: str
    locked: bool
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
