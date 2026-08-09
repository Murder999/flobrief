from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Mention(BaseModel):
    """A durable @mention relationship, resolved to a real user/member ID at
    creation time — never re-derived from regex-matching comment text later.

    ``source_type`` + ``source_id`` point at whichever existing free-text row
    the mention was authored in (a ``Comment``, a ``DeliverableAnnotation``,
    or an ``AnnotationReply``); no new comment table is introduced.

    Soft-deleted (``deleted_at`` set, from ``BaseModel``) when a comment edit
    removes a previously-mentioned person, so notification-diffing on edit
    can tell "already mentioned, still mentioned" apart from "newly added".
    """

    __tablename__ = "mentions"
    __table_args__ = (
        Index("ix_mentions_agency_id", "agency_id"),
        Index("ix_mentions_source", "source_type", "source_id"),
        Index("ix_mentions_mentioned_user_id", "mentioned_user_id"),
        Index("ix_mentions_brief_id", "brief_id"),
        # A live (non-deleted) mention is unique per (source, mentioned user) —
        # editing a comment and re-adding the same person must not duplicate
        # the row or re-fire a notification. Enforced as a Postgres partial
        # unique index (see the add_mentions migration) since a plain
        # UniqueConstraint can't carry a WHERE clause.
        UniqueConstraint(
            "source_type",
            "source_id",
            "mentioned_user_id",
            name="uq_mentions_source_user",
        ),
    )

    agency_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False
    )
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True
    )

    mentioned_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mentioned_agency_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agency_members.id", ondelete="SET NULL"), nullable=True
    )
    mentioned_brand_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brand_members.id", ondelete="SET NULL"), nullable=True
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # comment | annotation | annotation_reply — see MentionSourceType
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # id of the Comment / DeliverableAnnotation / AnnotationReply row
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("briefs.id", ondelete="CASCADE"), nullable=True
    )
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deliverables.id", ondelete="CASCADE"), nullable=True
    )

    # Name frozen at mention time so a later rename never rewrites history.
    display_text: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<Mention id={self.id} source_type={self.source_type} "
            f"source_id={self.source_id} mentioned_user_id={self.mentioned_user_id}>"
        )
