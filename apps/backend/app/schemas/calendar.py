from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models.enums import (
    BriefPriority,
    CalendarItemStatus,
    CalendarItemType,
    CalendarMilestoneType,
    CalendarPlatform,
)

_VALID_TYPES = {e.value for e in CalendarItemType}
_VALID_PLATFORMS = {e.value for e in CalendarPlatform}
_VALID_STATUSES = {e.value for e in CalendarItemStatus}
_VALID_PRIORITIES = {e.value for e in BriefPriority}
_VALID_MILESTONE_TYPES = {e.value for e in CalendarMilestoneType}


class CalendarItemCreate(BaseModel):
    title: str
    description: str | None = None
    brand_id: uuid.UUID | None = None
    brief_id: uuid.UUID | None = None
    item_type: str = "post"
    platform: str = "other"
    status: str = "planned"
    priority: str = "normal"
    milestone_type: str | None = None
    publish_at: datetime | None = None
    due_at: datetime | None = None
    color_label: str | None = None

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in _VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_VALID_PRIORITIES)}")
        return v

    @field_validator("milestone_type")
    @classmethod
    def validate_milestone_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_MILESTONE_TYPES:
            raise ValueError(f"milestone_type must be one of {sorted(_VALID_MILESTONE_TYPES)}")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title is required")
        return v

    @field_validator("item_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError(f"item_type must be one of {sorted(_VALID_TYPES)}")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str) -> str:
        if v not in _VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(_VALID_PLATFORMS)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v


class CalendarItemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    brand_id: uuid.UUID | None = None
    brief_id: uuid.UUID | None = None
    item_type: str | None = None
    platform: str | None = None
    priority: str | None = None
    milestone_type: str | None = None
    publish_at: datetime | None = None
    due_at: datetime | None = None
    color_label: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("title cannot be empty")
        return v

    @field_validator("item_type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_TYPES:
            raise ValueError(f"item_type must be one of {sorted(_VALID_TYPES)}")
        return v

    @field_validator("platform")
    @classmethod
    def validate_platform(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PLATFORMS:
            raise ValueError(f"platform must be one of {sorted(_VALID_PLATFORMS)}")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(_VALID_PRIORITIES)}")
        return v

    @field_validator("milestone_type")
    @classmethod
    def validate_milestone_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_MILESTONE_TYPES:
            raise ValueError(f"milestone_type must be one of {sorted(_VALID_MILESTONE_TYPES)}")
        return v


class StatusChangeRequest(BaseModel):
    new_status: str

    @field_validator("new_status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v


class CalendarItemRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID | None
    title: str
    description: str | None
    item_type: str
    platform: str
    status: str
    priority: str
    milestone_type: str | None
    publish_at: datetime | None
    due_at: datetime | None
    color_label: str | None
    created_by_id: uuid.UUID | None
    updated_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CalendarItemAssetRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    calendar_item_id: uuid.UUID
    asset_id: uuid.UUID
    created_at: datetime


class CalendarItemAssigneeRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    calendar_item_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


class CalendarItemStatusHistoryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    calendar_item_id: uuid.UUID
    old_status: str | None
    new_status: str
    changed_by_id: uuid.UUID | None
    created_at: datetime


class CalendarItemDetail(CalendarItemRead):
    assets: list[CalendarItemAssetRead] = []
    assignees: list[CalendarItemAssigneeRead] = []
    status_history: list[CalendarItemStatusHistoryRead] = []
