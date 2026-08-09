"""OnboardingService: real, live-data-backed onboarding progress.

``OnboardingProgress``/``OnboardingStepState`` only hold wizard bookkeeping
(current step, dismissal, first/last-seen, explicit skip). Whether a step
counts as *done* is recomputed here from the actual product data every time
progress is read — a user clicking a wizard button never marks a "do X" step
complete on its own; only the real X happening does.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brief import Brief, BriefAssignee
from app.models.deliverable import Deliverable
from app.models.deliverable_annotation import DeliverableAnnotation
from app.models.enums import AgencyMemberRole, OnboardingType
from app.models.mention import Mention
from app.models.notification import NotificationPreference
from app.models.onboarding import OnboardingProgress, OnboardingStepState
from app.models.time_entry import TimeEntry
from app.models.work_schedule import WorkSchedule

CURRENT_ONBOARDING_VERSION = 1

_AGENCY_OWNER_STEPS: list[str] = [
    "welcome",
    "agency_profile",
    "first_brand",
    "invite_team",
    "first_brief",
    "first_deliverable",
    "preview_center",
    "brand_portal_preview",
    "comment_mention_annotation",
    "time_tracking",
    "capacity",
    "notification_preferences",
    "summary",
]
_AGENCY_MEMBER_STEPS: list[str] = [
    "role_intro",
    "assigned_briefs",
    "comment_mention",
    "deliverable_area",
    "timer_start",
    "timesheet",
    "notifications",
]
_BRAND_USER_STEPS: list[str] = [
    "portal_intro",
    "view_briefs",
    "deliverable_preview",
    "annotation",
    "comment_mention",
    "request_revision",
    "approve",
    "calendar_invoices",
]

# Steps whose only real signal is "did the user open this screen" — completion
# comes from OnboardingStepState.first_seen_at (a real navigation event, set
# by the frontend calling POST .../step/{key}/seen when that route mounts),
# never a wizard button alone.
_VIEW_STEPS = {
    "welcome",
    "preview_center",
    "brand_portal_preview",
    "summary",
    "role_intro",
    "deliverable_area",
    "timesheet",
    "notifications",
    "portal_intro",
    "view_briefs",
    "deliverable_preview",
    "calendar_invoices",
}

_STEP_SETS: dict[str, list[str]] = {
    OnboardingType.AGENCY_OWNER_ADMIN.value: _AGENCY_OWNER_STEPS,
    OnboardingType.AGENCY_MEMBER.value: _AGENCY_MEMBER_STEPS,
    OnboardingType.BRAND_USER.value: _BRAND_USER_STEPS,
}


@dataclass(frozen=True)
class StepView:
    key: str
    completed: bool
    kind: str  # "action" | "view"
    skipped: bool
    first_seen_at: datetime | None
    last_seen_at: datetime | None


@dataclass(frozen=True)
class ProgressView:
    id: uuid.UUID
    onboarding_type: str
    current_step: str | None
    started_at: datetime
    completed_at: datetime | None
    dismissed_at: datetime | None
    version: int
    steps: list[StepView]

    @property
    def percent_complete(self) -> int:
        if not self.steps:
            return 0
        done = sum(1 for s in self.steps if s.completed or s.skipped)
        return round(done / len(self.steps) * 100)


def resolve_onboarding_type(*, is_agency_owner_or_admin: bool, is_agency: bool) -> str:
    if not is_agency:
        return OnboardingType.BRAND_USER.value
    return (
        OnboardingType.AGENCY_OWNER_ADMIN.value
        if is_agency_owner_or_admin
        else OnboardingType.AGENCY_MEMBER.value
    )


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_progress(
        self, *, user_id: uuid.UUID, agency_id: uuid.UUID | None, onboarding_type: str
    ) -> OnboardingProgress:
        stmt = select(OnboardingProgress).where(
            OnboardingProgress.user_id == user_id,
            OnboardingProgress.onboarding_type == onboarding_type,
            OnboardingProgress.deleted_at.is_(None),
        )
        progress = (await self.db.execute(stmt)).scalar_one_or_none()
        if progress is None:
            progress = OnboardingProgress(
                agency_id=agency_id,
                user_id=user_id,
                onboarding_type=onboarding_type,
                started_at=datetime.now(UTC),
                version=CURRENT_ONBOARDING_VERSION,
            )
            try:
                # Savepoint, not a full rollback: two concurrent requests
                # (e.g. the dashboard's progress GET racing a step-seen POST)
                # can both miss the SELECT above and both try to insert — the
                # loser hits uq_onboarding_user_type. A plain session
                # rollback would expire every object already loaded in this
                # request's session; the savepoint confines the damage to
                # just this insert.
                async with self.db.begin_nested():
                    self.db.add(progress)
                    await self.db.flush()
            except IntegrityError:
                progress = (await self.db.execute(stmt)).scalar_one()
            else:
                await self.db.refresh(progress)
        return progress

    async def _get_step_states(self, progress_id: uuid.UUID) -> dict[str, OnboardingStepState]:
        stmt = select(OnboardingStepState).where(
            OnboardingStepState.onboarding_progress_id == progress_id,
            OnboardingStepState.deleted_at.is_(None),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return {row.step_key: row for row in rows}

    async def _get_or_create_step_state(
        self, progress_id: uuid.UUID, step_key: str
    ) -> OnboardingStepState:
        states = await self._get_step_states(progress_id)
        if step_key in states:
            return states[step_key]
        state = OnboardingStepState(onboarding_progress_id=progress_id, step_key=step_key)
        try:
            # Same race as get_or_create_progress (savepoint-scoped so the
            # caller's already-loaded `progress` object stays intact),
            # scoped to one step's unique (onboarding_progress_id, step_key)
            # constraint.
            async with self.db.begin_nested():
                self.db.add(state)
                await self.db.flush()
        except IntegrityError:
            states = await self._get_step_states(progress_id)
            return states[step_key]
        await self.db.refresh(state)
        return state

    # ── Real completion computation ─────────────────────────────────────────

    async def _agency_action_completion(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, step_key: str
    ) -> bool:
        if step_key == "agency_profile":
            agency = await self.db.get(Agency, agency_id)
            return bool(agency and agency.name)
        if step_key == "first_brand":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Brand)
                .where(Brand.agency_id == agency_id, Brand.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "invite_team":
            count = await self.db.scalar(
                select(func.count())
                .select_from(AgencyMember)
                .where(
                    AgencyMember.agency_id == agency_id,
                    AgencyMember.deleted_at.is_(None),
                )
            )
            return bool(count and count > 1)
        if step_key == "first_brief":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Brief)
                .where(Brief.agency_id == agency_id, Brief.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "first_deliverable":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Deliverable)
                .where(Deliverable.agency_id == agency_id, Deliverable.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "comment_mention_annotation":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Mention)
                .where(Mention.agency_id == agency_id, Mention.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "time_tracking":
            count = await self.db.scalar(
                select(func.count())
                .select_from(TimeEntry)
                .where(TimeEntry.agency_id == agency_id, TimeEntry.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "capacity":
            count = await self.db.scalar(
                select(func.count())
                .select_from(WorkSchedule)
                .where(WorkSchedule.agency_id == agency_id, WorkSchedule.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "notification_preferences":
            pref = await self.db.scalar(
                select(NotificationPreference).where(NotificationPreference.user_id == user_id)
            )
            if pref is None:
                return False
            return bool(pref.category_preferences) or pref.updated_at != pref.created_at
        return False

    async def _agency_member_action_completion(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, step_key: str
    ) -> bool:
        if step_key == "assigned_briefs":
            count = await self.db.scalar(
                select(func.count())
                .select_from(BriefAssignee)
                .where(BriefAssignee.user_id == user_id, BriefAssignee.deleted_at.is_(None))
            )
            return bool(count)
        if step_key == "comment_mention":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Mention)
                .where(
                    Mention.agency_id == agency_id,
                    Mention.actor_user_id == user_id,
                    Mention.deleted_at.is_(None),
                )
            )
            return bool(count)
        if step_key == "timer_start":
            count = await self.db.scalar(
                select(func.count())
                .select_from(TimeEntry)
                .where(TimeEntry.user_id == user_id, TimeEntry.deleted_at.is_(None))
            )
            return bool(count)
        return False

    async def _brand_action_completion(
        self, brand_id: uuid.UUID, user_id: uuid.UUID, step_key: str
    ) -> bool:
        if step_key in ("annotation", "comment_mention"):
            count = await self.db.scalar(
                select(func.count())
                .select_from(DeliverableAnnotation)
                .where(
                    DeliverableAnnotation.brand_id == brand_id,
                    DeliverableAnnotation.created_by_id == user_id,
                    DeliverableAnnotation.deleted_at.is_(None),
                )
            )
            return bool(count)
        if step_key == "request_revision":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Deliverable)
                .where(
                    Deliverable.brand_id == brand_id,
                    Deliverable.status == "revision_requested",
                    Deliverable.deleted_at.is_(None),
                )
            )
            return bool(count)
        if step_key == "approve":
            count = await self.db.scalar(
                select(func.count())
                .select_from(Deliverable)
                .where(
                    Deliverable.brand_id == brand_id,
                    Deliverable.status == "approved",
                    Deliverable.deleted_at.is_(None),
                )
            )
            return bool(count)
        return False

    async def build_progress_view(
        self,
        *,
        user_id: uuid.UUID,
        agency_id: uuid.UUID | None,
        brand_id: uuid.UUID | None,
        onboarding_type: str,
    ) -> ProgressView:
        progress = await self.get_or_create_progress(
            user_id=user_id, agency_id=agency_id, onboarding_type=onboarding_type
        )
        step_keys = _STEP_SETS[onboarding_type]
        states = await self._get_step_states(progress.id)

        steps: list[StepView] = []
        for key in step_keys:
            state = states.get(key)
            kind = "view" if key in _VIEW_STEPS else "action"
            skipped = bool(state and state.status == "skipped")
            if skipped:
                completed = False
            elif kind == "view":
                completed = bool(state and state.first_seen_at is not None)
            elif onboarding_type == OnboardingType.AGENCY_OWNER_ADMIN.value:
                completed = await self._agency_action_completion(agency_id, user_id, key)
            elif onboarding_type == OnboardingType.AGENCY_MEMBER.value:
                completed = await self._agency_member_action_completion(agency_id, user_id, key)
            else:
                completed = await self._brand_action_completion(brand_id, user_id, key)
            steps.append(
                StepView(
                    key=key,
                    completed=completed,
                    kind=kind,
                    skipped=skipped,
                    first_seen_at=state.first_seen_at if state else None,
                    last_seen_at=state.last_seen_at if state else None,
                )
            )

        if all(s.completed or s.skipped for s in steps) and progress.completed_at is None:
            progress.completed_at = datetime.now(UTC)
            await self.db.flush()

        return ProgressView(
            id=progress.id,
            onboarding_type=progress.onboarding_type,
            current_step=progress.current_step,
            started_at=progress.started_at,
            completed_at=progress.completed_at,
            dismissed_at=progress.dismissed_at,
            version=progress.version,
            steps=steps,
        )

    async def mark_step_seen(self, *, progress: OnboardingProgress, step_key: str) -> None:
        state = await self._get_or_create_step_state(progress.id, step_key)
        now = datetime.now(UTC)
        if state.first_seen_at is None:
            state.first_seen_at = now
        state.last_seen_at = now
        progress.current_step = step_key
        progress.last_seen_at = now
        await self.db.flush()

    async def skip_step(self, *, progress: OnboardingProgress, step_key: str) -> None:
        state = await self._get_or_create_step_state(progress.id, step_key)
        state.status = "skipped"
        state.skipped_at = datetime.now(UTC)
        await self.db.flush()

    async def dismiss(self, *, progress: OnboardingProgress) -> None:
        progress.dismissed_at = datetime.now(UTC)
        await self.db.flush()

    async def resume(self, *, progress: OnboardingProgress) -> None:
        progress.dismissed_at = None
        await self.db.flush()


def default_onboarding_type_for_agency_role(role: str) -> str:
    if role in (AgencyMemberRole.OWNER.value, AgencyMemberRole.ADMIN.value):
        return OnboardingType.AGENCY_OWNER_ADMIN.value
    return OnboardingType.AGENCY_MEMBER.value


def default_onboarding_type_for_brand_role(role: str) -> str:
    del role  # every brand role uses the same brand onboarding track today
    return OnboardingType.BRAND_USER.value


__all__ = [
    "OnboardingService",
    "ProgressView",
    "StepView",
    "CURRENT_ONBOARDING_VERSION",
    "resolve_onboarding_type",
    "default_onboarding_type_for_agency_role",
    "default_onboarding_type_for_brand_role",
]
