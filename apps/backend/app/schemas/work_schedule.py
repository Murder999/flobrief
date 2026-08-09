from __future__ import annotations

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class WorkScheduleDayCreate(BaseModel):
    weekday: int = Field(..., ge=0, le=6)
    is_working_day: bool = True
    capacity_minutes: int = Field(..., ge=0)


class WorkScheduleCreate(BaseModel):
    """Creates (or replaces) a user's active WorkSchedule aggregate. An edit
    is always a full soft-delete-old + insert-new — never a partial patch —
    so `WorkScheduleUpdate` reuses this exact shape."""

    user_id: uuid.UUID
    timezone: str = "Europe/Istanbul"
    effective_from: date | None = None
    days: list[WorkScheduleDayCreate]

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as err:
            raise ValueError(f"Geçersiz saat dilimi: {v}") from err
        return v

    @model_validator(mode="after")
    def validate_unique_weekdays(self) -> WorkScheduleCreate:
        weekdays = [d.weekday for d in self.days]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("Her hafta günü yalnızca bir kez tanımlanabilir")
        return self


class WorkScheduleUpdate(WorkScheduleCreate):
    """Same shape as create — see `WorkScheduleCreate` docstring."""


class WorkScheduleDayRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    weekday: int
    is_working_day: bool
    capacity_minutes: int


class WorkScheduleRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    user_id: uuid.UUID
    timezone: str
    effective_from: date | None
    days: list[WorkScheduleDayRead]
    created_at: datetime
    updated_at: datetime
