from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ValidationInfo, field_validator

from app.models.enums import TimeEntryCategory

_VALID_CATEGORIES = {c.value for c in TimeEntryCategory}
_VALID_SOURCES = {"timer", "manual"}


class TimeEntryStart(BaseModel):
    """Starts a new running timer for the current user. Fails with 409 if the
    user already has an active (unstopped) timer."""

    brief_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    deliverable_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    category: str = TimeEntryCategory.OTHER.value
    description: str | None = None
    billable: bool = True

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TimeEntryStop(BaseModel):
    """Stops the caller's active timer, optionally finalizing its metadata."""

    category: str | None = None
    description: str | None = None
    billable: bool | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TimeEntryManualCreate(BaseModel):
    """Creates a completed time entry directly, without a running timer."""

    brief_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    deliverable_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    category: str = TimeEntryCategory.OTHER.value
    description: str | None = None
    started_at: datetime
    ended_at: datetime
    billable: bool = True
    # Future-dated manual entries are blocked by default; the caller must
    # explicitly confirm to allow one (e.g. logging across a timezone edge).
    confirm_future: bool = False

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("ended_at")
    @classmethod
    def validate_end_after_start(cls, v: datetime, info: ValidationInfo) -> datetime:
        started_at = info.data.get("started_at")
        if started_at is not None and v <= started_at:
            raise ValueError("Bitiş zamanı başlangıçtan sonra olmalı")
        return v


class TimeEntryUpdate(BaseModel):
    """Edits an existing entry's editable metadata. Locked entries reject all
    field changes (enforced in the service layer, not here)."""

    category: str | None = None
    description: str | None = None
    billable: bool | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_CATEGORIES:
            raise ValueError(f"Geçersiz kategori: {v}")
        return v

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None


class TimeEntryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID | None
    deliverable_id: uuid.UUID | None
    task_id: uuid.UUID | None
    user_id: uuid.UUID
    category: str
    description: str | None
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    billable: bool
    source: str
    locked: bool
    locked_by_id: uuid.UUID | None
    locked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ActiveTimerRead(BaseModel):
    """The caller's currently-running timer, or null if none is active.

    The client recomputes elapsed time from `started_at` on every mount/reload
    — this payload never carries a pre-computed elapsed/duration value, so a
    stale client interval can never become the source of truth.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    brief_id: uuid.UUID | None
    brand_id: uuid.UUID | None
    deliverable_id: uuid.UUID | None
    task_id: uuid.UUID | None
    category: str
    description: str | None
    billable: bool
    started_at: datetime


class TimeEntryCreateResult(BaseModel):
    """Wraps a created/stopped entry with a non-blocking overlap warning."""

    entry: TimeEntryRead
    overlap_warning: bool = False
