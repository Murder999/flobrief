from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.asset import AssetRead
from app.schemas.mention import MentionInline, validate_mention_count

_VISIBILITY_VALUES = {"internal", "client_visible"}
_THREAD_TYPE_VALUES = {"brief", "field", "asset", "approval"}


class CommentRead(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    author_user_id: uuid.UUID | None
    author_name: str | None
    author_email: str | None
    author_job_title: str | None = None
    body: str
    visibility: str
    created_at: datetime
    updated_at: datetime
    attachments: list[AssetRead] = []
    mentions: list[MentionInline] = []

    model_config = {"from_attributes": True}


class ThreadRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brief_id: uuid.UUID | None
    approval_id: uuid.UUID | None
    field_key: str | None
    asset_id: uuid.UUID | None
    thread_type: str
    status: str
    created_by_id: uuid.UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    comments: list[CommentRead] = []

    model_config = {"from_attributes": True}


class ThreadCreate(BaseModel):
    thread_type: str = "brief"
    brief_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    field_key: str | None = None
    asset_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None
    initial_comment: str
    visibility: str = "internal"
    attachment_ids: list[uuid.UUID] | None = None
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("thread_type")
    @classmethod
    def valid_thread_type(cls, v: str) -> str:
        if v not in _THREAD_TYPE_VALUES:
            raise ValueError(f"thread_type must be one of: {_THREAD_TYPE_VALUES}")
        return v

    @field_validator("initial_comment")
    @classmethod
    def comment_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("initial_comment cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Comment must be 50 000 chars or less")
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


class AddCommentRequest(BaseModel):
    body: str
    visibility: str = "internal"
    author_name: str | None = None
    author_email: str | None = None
    attachment_ids: list[uuid.UUID] | None = None
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Comment must be 50 000 chars or less")
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


class UpdateCommentRequest(BaseModel):
    body: str
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("body")
    @classmethod
    def body_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("body cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Comment must be 50 000 chars or less")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mentions(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)
