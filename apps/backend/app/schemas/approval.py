from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator

# ── Version schemas ──────────────────────────────────────────────────────────


class BriefVersionRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    version_number: int
    snapshot: dict[str, Any]
    created_by_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BriefVersionSummary(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    version_number: int
    created_by_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Approval schemas ─────────────────────────────────────────────────────────


class ApprovalRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    version_id: uuid.UUID | None
    status: str
    requested_by_id: uuid.UUID
    approved_by_email: str | None
    approved_by_name: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SendToApprovalResponse(BaseModel):
    approval: ApprovalRead
    approval_token: str
    approval_url: str


class RevokeApprovalRequest(BaseModel):
    pass


# ── Comment schemas ──────────────────────────────────────────────────────────


class ApprovalCommentRead(BaseModel):
    id: uuid.UUID
    approval_id: uuid.UUID
    user_id: uuid.UUID | None
    author_name: str | None
    author_email: str | None
    comment: str
    is_internal: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AddPublicCommentRequest(BaseModel):
    comment: str
    author_name: str | None = None
    author_email: str | None = None

    @field_validator("comment")
    @classmethod
    def comment_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("comment cannot be empty")
        if len(v) > 5000:
            raise ValueError("comment must be 5000 chars or less")
        return v


# ── Public portal schemas ─────────────────────────────────────────────────────


class PublicFieldValue(BaseModel):
    field_key: str
    label: str
    field_type: str
    is_required: bool
    options: dict[str, Any] | None
    placeholder: str | None
    value: Any


class PublicSection(BaseModel):
    title: str
    description: str | None
    fields: list[PublicFieldValue]


class PublicApprovalView(BaseModel):
    """What the public approval portal sees — no internal agency data."""

    approval_id: uuid.UUID
    status: str
    brief_title: str
    brief_description: str | None
    brief_priority: str
    brief_deadline: str | None
    brand_name: str | None
    template_name: str | None
    version_number: int
    sections: list[PublicSection]
    comments: list[ApprovalCommentRead]
    expires_at: datetime
    decided_at: datetime | None


class PublicApproveRequest(BaseModel):
    approver_name: str | None = None
    approver_email: str | None = None

    @field_validator("approver_email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v


class PublicRevisionRequest(BaseModel):
    comment: str
    approver_name: str | None = None
    approver_email: str | None = None

    @field_validator("comment")
    @classmethod
    def comment_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Revision comment cannot be empty")
        if len(v) > 5000:
            raise ValueError("comment must be 5000 chars or less")
        return v
