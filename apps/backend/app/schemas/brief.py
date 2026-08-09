from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

from app.models.enums import BriefPriority, BriefStatus

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_ORDER = ["start_date", "draft_date", "feedback_date", "deadline", "publish_date"]
_DATE_LABELS = {
    "start_date": "Başlangıç tarihi",
    "draft_date": "İlk taslak tarihi",
    "feedback_date": "Geri bildirim tarihi",
    "deadline": "Nihai teslim tarihi",
    "publish_date": "Yayın tarihi",
}


def _check_date_format(v: str | None, field: str) -> str | None:
    if v is None:
        return v
    if not _DATE_RE.match(v):
        raise ValueError(f"{field} must be in YYYY-MM-DD format")
    return v


def _check_date_order(values: dict[str, Any]) -> None:
    """Reject illogical date ordering wherever two or more of the 5 planning
    dates are set (string comparison is safe since all are YYYY-MM-DD)."""
    present = [(k, values[k]) for k in _DATE_ORDER if values.get(k)]
    for (k1, v1), (k2, v2) in zip(present, present[1:], strict=False):
        if v1 > v2:
            raise ValueError(f"{_DATE_LABELS[k1]}, {_DATE_LABELS[k2]} tarihinden sonra olamaz")


class BriefFieldValueIn(BaseModel):
    template_field_id: uuid.UUID
    value: Any


class BriefCreate(BaseModel):
    template_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    description_html: str | None = None
    priority: BriefPriority = BriefPriority.NORMAL
    start_date: str | None = None
    draft_date: str | None = None
    feedback_date: str | None = None
    deadline: str | None = None
    publish_date: str | None = None
    add_to_calendar: bool = True
    platforms: list[str] = []
    content_types: list[str] = []
    reference_links: list[str] = []
    assignee_ids: list[uuid.UUID] = []
    estimated_hours: float | None = None
    estimated_hours_by_category: dict[str, float] | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

    @field_validator("start_date", "draft_date", "feedback_date", "deadline", "publish_date")
    @classmethod
    def date_format(cls, v: str | None, info: Any) -> str | None:
        return _check_date_format(v, info.field_name)

    @model_validator(mode="after")
    def date_order(self) -> BriefCreate:
        _check_date_order(self.model_dump(include=set(_DATE_ORDER)))
        return self


class BriefUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    description_html: str | None = None
    priority: BriefPriority | None = None
    start_date: str | None = None
    draft_date: str | None = None
    feedback_date: str | None = None
    deadline: str | None = None
    publish_date: str | None = None
    platforms: list[str] | None = None
    content_types: list[str] | None = None
    reference_links: list[str] | None = None
    brand_id: uuid.UUID | None = None
    estimated_hours: float | None = None
    estimated_hours_by_category: dict[str, float] | None = None

    @field_validator("start_date", "draft_date", "feedback_date", "deadline", "publish_date")
    @classmethod
    def date_format(cls, v: str | None, info: Any) -> str | None:
        return _check_date_format(v, info.field_name)

    @model_validator(mode="after")
    def date_order(self) -> BriefUpdate:
        # Partial update: only validate ordering among the dates actually being set.
        _check_date_order(self.model_dump(include=set(_DATE_ORDER)))
        return self


class BriefStatusUpdate(BaseModel):
    status: BriefStatus


class BriefFieldValuesUpdate(BaseModel):
    values: list[BriefFieldValueIn]


class AssigneeAdd(BaseModel):
    user_id: uuid.UUID
    role_label: str | None = None


class AssigneeRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    user_id: uuid.UUID
    role_label: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FieldValueRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    template_field_id: uuid.UUID
    value: Any
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BriefRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    template_id: uuid.UUID | None
    title: str
    description: str | None
    description_html: str | None = None
    status: str
    priority: str
    start_date: str | None = None
    draft_date: str | None = None
    feedback_date: str | None = None
    deadline: str | None
    publish_date: str | None = None
    platforms: list[str] | None = None
    content_types: list[str] | None = None
    source: str | None = None
    meta: dict | None = None
    estimated_hours: float | None = None
    estimated_hours_by_category: dict[str, float] | None = None
    created_by_id: uuid.UUID
    updated_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _fallback_from_meta(self) -> BriefRead:
        """Legacy rows stored platforms/content_types only inside `meta` JSON —
        fall back to that so old brief records keep rendering correctly."""
        meta = self.meta or {}
        if not self.platforms:
            self.platforms = meta.get("platforms") or []
        if not self.content_types:
            self.content_types = meta.get("content_types") or []
        return self


class BriefDetail(BriefRead):
    field_values: list[FieldValueRead] = []
    assignees: list[AssigneeRead] = []
    linked_calendar_item_id: uuid.UUID | None = None


class BriefListResponse(BaseModel):
    items: list[BriefRead]
    total: int
    offset: int
    limit: int


def default_caps_for_role(role: str) -> dict:
    """Return default capability flags per participant role."""
    caps: dict[str, bool] = {
        "can_comment": True,
        "can_upload": True,
        "can_edit": False,
        "can_approve": False,
        "can_request_revision": False,
    }
    if role in ("task_owner", "brand_manager"):
        caps["can_edit"] = True
        caps["can_approve"] = True
        caps["can_request_revision"] = True
    elif role in ("designer", "developer", "social_media_manager"):
        caps["can_edit"] = True
    elif role == "brand_representative":
        caps["can_approve"] = True
        caps["can_request_revision"] = True
    elif role == "external_approver":
        caps["can_approve"] = True
        caps["can_request_revision"] = True
        caps["can_comment"] = True
        caps["can_upload"] = False
    elif role == "viewer":
        caps["can_comment"] = False
        caps["can_upload"] = False
    return caps


class BriefParticipantRead(BaseModel):
    id: uuid.UUID
    brief_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None
    user_email: str | None
    participant_role: str | None
    role_label: str | None
    can_comment: bool
    can_upload: bool
    can_edit: bool
    can_approve: bool
    can_request_revision: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BriefParticipantCreate(BaseModel):
    user_id: uuid.UUID
    participant_role: str
    role_label: str | None = None
    can_comment: bool = True
    can_upload: bool = True
    can_edit: bool = False
    can_approve: bool = False
    can_request_revision: bool = False


class BriefParticipantUpdate(BaseModel):
    participant_role: str | None = None
    role_label: str | None = None
    can_comment: bool | None = None
    can_upload: bool | None = None
    can_edit: bool | None = None
    can_approve: bool | None = None
    can_request_revision: bool | None = None
