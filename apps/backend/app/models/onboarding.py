from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class OnboardingProgress(BaseModel):
    """One row per (user, onboarding_type). Step completion is NOT trusted
    from this row alone — ``OnboardingService`` recomputes each step's real
    status from live product data on every read; this row only tracks wizard
    bookkeeping (current step, dismissal, resume, version)."""

    __tablename__ = "onboarding_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "onboarding_type", name="uq_onboarding_user_type"),
        Index("ix_onboarding_progress_user_id", "user_id"),
        Index("ix_onboarding_progress_agency_id", "agency_id"),
    )

    agency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agencies.id", ondelete="CASCADE"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # agency_owner_admin | agency_member | brand_user — see OnboardingType
    onboarding_type: Mapped[str] = mapped_column(String(30), nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(60), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    onboarding_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    def __repr__(self) -> str:
        return (
            f"<OnboardingProgress id={self.id} user_id={self.user_id} "
            f"onboarding_type={self.onboarding_type}>"
        )


class OnboardingStepState(BaseModel):
    """Bookkeeping (seen/skipped/explicitly-completed timestamps) for a single
    step within an OnboardingProgress. The authoritative "is this step done"
    answer still comes from live data via OnboardingService — this table
    exists for first/last-seen tracking and explicit user skip actions, not
    as the source of truth for completion."""

    __tablename__ = "onboarding_step_state"
    __table_args__ = (
        UniqueConstraint(
            "onboarding_progress_id", "step_key", name="uq_onboarding_step_progress_key"
        ),
        Index("ix_onboarding_step_state_progress_id", "onboarding_progress_id"),
    )

    onboarding_progress_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_progress.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(String(60), nullable=False)
    # pending | completed | skipped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<OnboardingStepState step_key={self.step_key} status={self.status}>"
