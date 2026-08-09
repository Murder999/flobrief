from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import CapacityExceptionType

_VALID_EXCEPTION_TYPES = {t.value for t in CapacityExceptionType}


class CapacityExceptionCreate(BaseModel):
    user_id: uuid.UUID
    date: date
    capacity_minutes: int = Field(..., ge=0)
    reason: str | None = None
    exception_type: str

    @field_validator("exception_type")
    @classmethod
    def validate_exception_type(cls, v: str) -> str:
        if v not in _VALID_EXCEPTION_TYPES:
            raise ValueError(f"Geçersiz istisna türü: {v}")
        return v

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class CapacityExceptionUpdate(BaseModel):
    capacity_minutes: int | None = Field(None, ge=0)
    reason: str | None = None
    exception_type: str | None = None

    @field_validator("exception_type")
    @classmethod
    def validate_exception_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_EXCEPTION_TYPES:
            raise ValueError(f"Geçersiz istisna türü: {v}")
        return v

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class CapacityExceptionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID
    date: date
    capacity_minutes: int
    reason: str | None
    exception_type: str
    created_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
