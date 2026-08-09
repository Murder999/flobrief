from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

_SOURCE_TYPE_VALUES = {"comment", "annotation", "annotation_reply"}

MAX_MENTIONS_PER_SOURCE = 20


def validate_mention_count(v: list[uuid.UUID]) -> list[uuid.UUID]:
    """Shared validator body for every request schema that accepts
    ``mentioned_user_ids`` (thread/comment create+edit, annotation
    create+reply, on both the agency and brand portals) — a single source of
    truth for the cap so it can't drift between those paths. Enforced as a
    hard 422 rejection, not a silent truncation: the product rule is that the
    caller gets a clear error, never quietly-dropped mentions."""
    if len(v) > MAX_MENTIONS_PER_SOURCE:
        raise ValueError(f"A single comment can mention at most {MAX_MENTIONS_PER_SOURCE} people")
    return v


class MentionCandidateRead(BaseModel):
    """A single mentionable person, returned by the candidates endpoint.

    Deliberately excludes email — the frontend only needs enough to render
    a suggestion row (avatar/name/role/context), never a contact address.
    """

    member_id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None
    role_label: str
    member_type: str  # "agency" | "brand"
    context_label: str | None = None


class MentionCandidateListResponse(BaseModel):
    items: list[MentionCandidateRead]


class MentionInline(BaseModel):
    """Embedded on CommentRead/AnnotationRead/AnnotationReplyRead so the
    frontend can render mention chips without a second round-trip."""

    mentioned_user_id: uuid.UUID
    display_text: str
    is_active: bool

    model_config = {"from_attributes": True}


class MentionSyncRequest(BaseModel):
    """Sent alongside a comment/annotation create-or-edit request.

    ``mentioned_user_ids`` is never blindly trusted: the backend re-validates
    every id against (a) the real candidate list for this context and (b)
    presence of the person's display name in the submitted body text.
    """

    source_type: str
    mentioned_user_ids: list[uuid.UUID] = []

    @field_validator("source_type")
    @classmethod
    def valid_source_type(cls, v: str) -> str:
        if v not in _SOURCE_TYPE_VALUES:
            raise ValueError(f"source_type must be one of: {_SOURCE_TYPE_VALUES}")
        return v

    @field_validator("mentioned_user_ids")
    @classmethod
    def cap_mention_count(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return validate_mention_count(v)


class MentionRead(BaseModel):
    id: uuid.UUID
    agency_id: uuid.UUID
    brand_id: uuid.UUID | None
    mentioned_user_id: uuid.UUID
    actor_user_id: uuid.UUID
    source_type: str
    source_id: uuid.UUID
    brief_id: uuid.UUID | None
    deliverable_id: uuid.UUID | None
    display_text: str
    created_at: datetime

    model_config = {"from_attributes": True}
