from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.mention import MentionInline, validate_mention_count

_STATUS_VALUES = {"open", "resolved"}
_TYPE_VALUES = {"general", "revision", "approval_note"}
_VISIBILITY_VALUES = {"internal", "client_visible"}


class AnnotationReplyRead(BaseModel):
    id: uuid.UUID
    annotation_id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_name: str | None
    body: str
    body_html: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime
    mentions: list[MentionInline] = []

    model_config = {"from_attributes": True}


class AnnotationRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    brief_id: uuid.UUID
    deliverable_id: uuid.UUID
    asset_id: uuid.UUID | None
    version_number: int
    x_percent: float | None
    y_percent: float | None
    label_number: int
    status: str
    annotation_type: str
    visibility: str
    body: str | None
    body_html: str | None
    created_by_id: uuid.UUID | None
    created_by_name: str | None = None
    resolved_by_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    replies: list[AnnotationReplyRead] = []
    mentions: list[MentionInline] = []

    model_config = {"from_attributes": True}


class AnnotationCreate(BaseModel):
    asset_id: uuid.UUID | None = None
    version_number: int = 1
    x_percent: float | None = None
    y_percent: float | None = None
    annotation_type: str = "general"
    visibility: str = "client_visible"
    body: str
    body_html: str | None = None
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("annotation_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in _TYPE_VALUES:
            raise ValueError(f"annotation_type must be one of: {_TYPE_VALUES}")
        return v

    @field_validator("visibility")
    @classmethod
    def valid_visibility(cls, v: str) -> str:
        if v not in _VISIBILITY_VALUES:
            raise ValueError(f"visibility must be one of: {_VISIBILITY_VALUES}")
        return v

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        if len(v) > 10_000:
            raise ValueError("body must be 10 000 chars or less")
        return v

    @field_validator("x_percent", "y_percent")
    @classmethod
    def valid_percent(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError("coordinate must be between 0 and 100")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mentions(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)


class AnnotationReplyCreate(BaseModel):
    body: str
    body_html: str | None = None
    visibility: str = "client_visible"
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        if len(v) > 10_000:
            raise ValueError("body must be 10 000 chars or less")
        return v

    @field_validator("visibility")
    @classmethod
    def valid_visibility(cls, v: str) -> str:
        if v not in _VISIBILITY_VALUES:
            raise ValueError(f"visibility must be one of: {_VISIBILITY_VALUES}")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mentions(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)


class AnnotationUpdateStatus(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in _STATUS_VALUES:
            raise ValueError(f"status must be one of: {_STATUS_VALUES}")
        return v
