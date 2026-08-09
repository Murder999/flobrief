from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ValidationInfo, field_validator

from app.models.enums import TimeOffType

_VALID_TYPES = {t.value for t in TimeOffType}


class TimeOffCreate(BaseModel):
    """Requests a leave period for the current user (or, when created by a
    manager, for `user_id`). When `all_day=True`, the exact UTC boundaries
    stored are recomputed by `TimeOffService` from the user's WorkSchedule
    timezone — the raw `start_at`/`end_at` sent here are only the calendar
    dates of intent in that case."""

    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    all_day: bool = True
    type: str = TimeOffType.VACATION.value
    notes: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"Geçersiz izin türü: {v}")
        return v

    @field_validator("end_at")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info: ValidationInfo) -> datetime:
        start_at = info.data.get("start_at")
        if start_at is not None and v < start_at:
            raise ValueError("Bitiş zamanı başlangıçtan önce olamaz")
        return v

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TimeOffReject(BaseModel):
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TimeOffRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    all_day: bool
    type: str
    status: str
    notes: str | None
    approved_by_id: uuid.UUID | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
