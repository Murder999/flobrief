"""CapacityCalculationService: the read-time capacity engine (plan §5/§6).

Nothing here is cached or stored — every number is recomputed from
WorkSchedule/CapacityException/TimeOff/Brief/BriefTask/BriefAssignee/
WorkAllocation/TimeEntry rows on every call, matching `TimeReportService`'s
pure-aggregation-on-read shape.

`compute_brief_planned_minutes` is the module's centerpiece: a dependency-free
pure function implementing plan §5's "tasks-present-means-tasks-win-wholesale"
double-counting rule. It is deliberately decoupled from dates/DB access so it
can be unit-tested directly against hand-built Brief/BriefTask/BriefAssignee/
WorkAllocation objects — see `test_work_allocation_double_counting.py`.

v1 scope decisions (documented, not silent):
- Neither `Brief` nor `BriefTask` carries a typed start date, so the
  estimate-derived (task/category/flat) share of `planned_minutes` is *not*
  gated by the query's date range — it represents current backlog, not a
  dated schedule. Only `WorkAllocation` rows (which do have real
  `start_date`/`end_date`) are range-filtered. This mirrors
  `TimeReportService.missing_timesheet`'s documented "no holiday calendar"
  simplification: an honest v1 boundary, not a fabricated one.
- Manual/locked `WorkAllocation` matching is done by `brief_id` or `task_id`
  only (not `deliverable_id`) — deliverable-scoped manual allocations exist
  in the data model for future UI use but are out of scope for this read
  aggregation until a deliverable-level planned view is built.
- Briefs in status `archived` or `rejected` are excluded from planned-minutes
  aggregation (dead work should not inflate a live capacity report); every
  other status is included.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency_member import AgencyMember
from app.models.agency_settings import AgencySettings
from app.models.brief import Brief, BriefAssignee
from app.models.brief_task import BriefTask
from app.models.capacity_exception import CapacityException
from app.models.enums import (
    AgencyMemberStatus,
    BriefParticipantRole,
    BriefStatus,
    TimeEntryCategory,
    TimeOffStatus,
    WorkAllocationSource,
)
from app.models.time_off import TimeOff
from app.models.user import User
from app.models.work_allocation import WorkAllocation
from app.models.work_schedule import WorkSchedule, WorkScheduleDay
from app.repositories.capacity_exception import CapacityExceptionRepository
from app.repositories.time_entry import TimeEntryRepository
from app.repositories.time_off import TimeOffRepository
from app.repositories.work_schedule import WorkScheduleRepository
from app.schemas.capacity_report import (
    BrandCapacityReport,
    BrandCapacityUserShare,
    TeamCapacityMember,
    TeamCapacityReport,
    UnassignedWorkItem,
    UnassignedWorkReport,
    UserCapacityReport,
)
from app.services.agency_settings_service import AgencySettingsService

_EXCLUDED_BRIEF_STATUSES = frozenset({BriefStatus.ARCHIVED.value, BriefStatus.REJECTED.value})

# v1 category -> participant-role attribution map for
# `Brief.estimated_hours_by_category` distribution (plan §5 step 3). A
# category with no entry here, or with zero matching assignees on the brief,
# is treated as unassigned rather than guessed at — a documented v1
# simplification, not a silent drop.
_CATEGORY_PARTICIPANT_ROLES: dict[str, frozenset[str]] = {
    TimeEntryCategory.DESIGN.value: frozenset({BriefParticipantRole.DESIGNER.value}),
    TimeEntryCategory.SOCIAL_MEDIA.value: frozenset(
        {BriefParticipantRole.SOCIAL_MEDIA_MANAGER.value}
    ),
    TimeEntryCategory.PROJECT_MANAGEMENT.value: frozenset({BriefParticipantRole.TASK_OWNER.value}),
}


@dataclass
class BriefPlannedBreakdown:
    """Result of applying plan §5's precedence rule to a single brief."""

    per_user_minutes: dict[uuid.UUID, float] = field(default_factory=dict)
    unassigned_minutes: float = 0.0
    has_estimate: bool = False
    source: str = "none"  # "tasks" | "category" | "flat" | "none"


def compute_brief_planned_minutes(
    brief: Brief,
    tasks: list[BriefTask],
    assignees: list[BriefAssignee],
    manual_allocations: list[WorkAllocation],
) -> BriefPlannedBreakdown:
    """Plan §5, evaluated for a single brief:

    1. Manual/locked WorkAllocation rows for a given (user, brief|task) pair
       always win for that specific assignee's number on this brief — they
       replace, not add to, that one assignee's auto-derived figure, and
       never disturb any other assignee's number.
    2. If any BriefTask under the brief has `estimated_hours` set, task-level
       estimates become authoritative for the WHOLE brief; `Brief.
       estimated_hours`/`estimated_hours_by_category` are ignored entirely.
       Each task's hours attribute to `task.assigned_to_id` (or the
       "unassigned" bucket if the task has no assignee).
    3. Else, if `Brief.estimated_hours_by_category` is set, distribute per
       category across the brief's `BriefAssignee` rows whose
       `participant_role` implies that category (even split among multiple
       matches; unassigned if none match).
    4. Else, if `Brief.estimated_hours` is set, split evenly across all
       `BriefAssignee` rows (unassigned if there are none).
    5. Else: contributes exactly 0 planned minutes (not null), flagged via
       `has_estimate=False` for a "Süre tahmini yapılmamış" UI label.

    `manual_allocations` must already be pre-filtered by the caller to rows
    belonging to this brief (by `brief_id` or `task_id`) and overlapping the
    query's date range — this function has no notion of dates.
    """
    manual_by_user: dict[uuid.UUID, float] = {}
    for alloc in manual_allocations:
        if alloc.locked or alloc.allocation_source == WorkAllocationSource.MANUAL.value:
            manual_by_user[alloc.user_id] = (
                manual_by_user.get(alloc.user_id, 0.0) + alloc.allocated_minutes
            )

    per_user: dict[uuid.UUID, float] = {}
    unassigned = 0.0
    has_estimate = False
    source = "none"

    if tasks and any(t.estimated_hours is not None for t in tasks):
        source = "tasks"
        has_estimate = True
        for t in tasks:
            minutes = (t.estimated_hours or 0.0) * 60
            if t.assigned_to_id is not None:
                per_user[t.assigned_to_id] = per_user.get(t.assigned_to_id, 0.0) + minutes
            else:
                unassigned += minutes
    elif brief.estimated_hours_by_category:
        source = "category"
        has_estimate = True
        for category, hours in brief.estimated_hours_by_category.items():
            minutes = (hours or 0.0) * 60
            matching_roles = _CATEGORY_PARTICIPANT_ROLES.get(category, frozenset())
            matches = [a for a in assignees if a.participant_role in matching_roles]
            if matches:
                share = minutes / len(matches)
                for a in matches:
                    per_user[a.user_id] = per_user.get(a.user_id, 0.0) + share
            else:
                unassigned += minutes
    elif brief.estimated_hours is not None:
        source = "flat"
        has_estimate = True
        minutes = brief.estimated_hours * 60
        if assignees:
            share = minutes / len(assignees)
            for a in assignees:
                per_user[a.user_id] = per_user.get(a.user_id, 0.0) + share
        else:
            unassigned += minutes

    # Manual/locked allocations replace (never add to) each specific
    # assignee's auto-derived number for this brief. Other assignees'
    # numbers are untouched.
    for user_id, manual_minutes in manual_by_user.items():
        per_user[user_id] = manual_minutes
        has_estimate = True

    return BriefPlannedBreakdown(
        per_user_minutes=per_user,
        unassigned_minutes=unassigned,
        has_estimate=has_estimate,
        source=source,
    )


def _status_for_pct(pct: int, settings: AgencySettings) -> str:
    if pct < settings.capacity_available_threshold_pct:
        return "available"
    if pct < settings.capacity_balanced_threshold_pct:
        return "balanced"
    if pct < settings.capacity_near_threshold_pct:
        return "near_capacity"
    return "overloaded"


def _day_range_to_utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=UTC)
    end_dt = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=UTC)
    return start_dt, end_dt


def _date_covered_by_time_off(day: date, timezone: str, time_off: TimeOff) -> bool:
    tz = ZoneInfo(timezone)
    day_start_utc = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    day_end_utc = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
    return time_off.start_at < day_end_utc and time_off.end_at > day_start_utc


class CapacityCalculationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._schedule_repo = WorkScheduleRepository(db)
        self._exception_repo = CapacityExceptionRepository(db)
        self._time_off_repo = TimeOffRepository(db)
        self._time_entry_repo = TimeEntryRepository(db)
        self._settings_service = AgencySettingsService(db)

    # ------------------------------------------------------------------
    # Net capacity (plan §6)

    async def _net_capacity(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[int, str]:
        schedule: WorkSchedule | None = await self._schedule_repo.get_active_for_user(
            agency_id, user_id
        )
        if schedule is None:
            return 0, "no_schedule"

        days: list[WorkScheduleDay] = await self._schedule_repo.get_days(schedule.id)
        days_by_weekday = {d.weekday: d for d in days}

        exceptions = await self._exception_repo.list_for_user(
            agency_id, user_id, start_date, end_date
        )
        exceptions_by_date: dict[date, CapacityException] = {e.date: e for e in exceptions}

        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        time_offs = await self._time_off_repo.list_for_user(agency_id, user_id, start_dt, end_dt)
        approved_time_offs = [t for t in time_offs if t.status == TimeOffStatus.APPROVED.value]

        total = 0
        would_be_working_days = 0
        time_off_days = 0
        current = start_date
        while current <= end_date:
            weekday = current.weekday()  # Python: Monday=0..Sunday=6, matches WorkScheduleDay
            day_row = days_by_weekday.get(weekday)
            base_minutes = (
                day_row.capacity_minutes if (day_row is not None and day_row.is_working_day) else 0
            )
            exc = exceptions_by_date.get(current)
            if exc is not None:
                base_minutes = exc.capacity_minutes

            if base_minutes > 0:
                would_be_working_days += 1

            on_leave = any(
                _date_covered_by_time_off(current, schedule.timezone, t) for t in approved_time_offs
            )
            if on_leave and base_minutes > 0:
                time_off_days += 1
                base_minutes = 0

            total += base_minutes
            current += timedelta(days=1)

        if total > 0:
            return total, "ok"
        if would_be_working_days > 0 and time_off_days == would_be_working_days:
            return 0, "time_off"
        return 0, "no_working_days"

    # ------------------------------------------------------------------
    # Planned minutes (plan §5)

    async def _active_briefs(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID | None = None
    ) -> list[Brief]:
        conditions = [
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.status.not_in(_EXCLUDED_BRIEF_STATUSES),
        ]
        if brand_id is not None:
            conditions.append(Brief.brand_id == brand_id)
        result = await self._db.execute(select(Brief).where(*conditions))
        return list(result.scalars().all())

    async def _tasks_for_brief(self, brief_id: uuid.UUID) -> list[BriefTask]:
        result = await self._db.execute(
            select(BriefTask).where(BriefTask.brief_id == brief_id, BriefTask.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def _assignees_for_brief(self, brief_id: uuid.UUID) -> list[BriefAssignee]:
        result = await self._db.execute(
            select(BriefAssignee).where(
                BriefAssignee.brief_id == brief_id, BriefAssignee.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def _manual_allocations_for_brief(
        self,
        agency_id: uuid.UUID,
        brief: Brief,
        task_ids: list[uuid.UUID],
        start_date: date,
        end_date: date,
    ) -> list[WorkAllocation]:
        match_conditions = [WorkAllocation.brief_id == brief.id]
        if task_ids:
            match_conditions.append(WorkAllocation.task_id.in_(task_ids))
        result = await self._db.execute(
            select(WorkAllocation).where(
                WorkAllocation.agency_id == agency_id,
                WorkAllocation.deleted_at.is_(None),
                WorkAllocation.start_date <= end_date,
                WorkAllocation.end_date >= start_date,
                or_(*match_conditions),
            )
        )
        return list(result.scalars().all())

    async def _planned_minutes_by_user(
        self,
        agency_id: uuid.UUID,
        start_date: date,
        end_date: date,
        brand_id: uuid.UUID | None = None,
    ) -> tuple[dict[uuid.UUID, float], float]:
        """Returns (per_user_minutes, unassigned_minutes) across every
        eligible brief in scope."""
        briefs = await self._active_briefs(agency_id, brand_id=brand_id)
        per_user: dict[uuid.UUID, float] = {}
        unassigned = 0.0
        for brief in briefs:
            tasks = await self._tasks_for_brief(brief.id)
            assignees = await self._assignees_for_brief(brief.id)
            task_ids = [t.id for t in tasks]
            manual = await self._manual_allocations_for_brief(
                agency_id, brief, task_ids, start_date, end_date
            )
            breakdown = compute_brief_planned_minutes(brief, tasks, assignees, manual)
            for uid, minutes in breakdown.per_user_minutes.items():
                per_user[uid] = per_user.get(uid, 0.0) + minutes
            unassigned += breakdown.unassigned_minutes
        return per_user, unassigned

    # ------------------------------------------------------------------
    # Actual minutes

    async def _actual_minutes(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> tuple[float, float]:
        """Returns (closed_actual_minutes, open_timer_elapsed_minutes). The
        open timer's elapsed time is never folded into the closed total."""
        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        entries = await self._time_entry_repo.list_for_user(user_id, agency_id, start_dt, end_dt)
        closed_minutes = (
            sum((e.duration_seconds or 0) for e in entries if e.duration_seconds is not None) / 60
        )

        open_minutes = 0.0
        active = await self._time_entry_repo.get_active_for_user(user_id)
        is_active_in_range = (
            active is not None
            and active.agency_id == agency_id
            and start_dt <= active.started_at <= end_dt
        )
        if active is not None and is_active_in_range:
            elapsed = (datetime.now(UTC) - active.started_at).total_seconds() / 60
            open_minutes = max(elapsed, 0.0)
        return closed_minutes, open_minutes

    # ------------------------------------------------------------------
    # Public report methods

    async def user_capacity(
        self, agency_id: uuid.UUID, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> UserCapacityReport:
        settings = await self._settings_service.get_or_create(agency_id)
        net_minutes, reason = await self._net_capacity(agency_id, user_id, start_date, end_date)
        per_user, _unassigned = await self._planned_minutes_by_user(agency_id, start_date, end_date)
        planned_minutes = per_user.get(user_id, 0.0)
        actual_minutes, open_timer_minutes = await self._actual_minutes(
            agency_id, user_id, start_date, end_date
        )

        if net_minutes <= 0:
            planned_pct = 0
            actual_pct = 0
            planned_status = "unknown"
            actual_status = "unknown"
        else:
            planned_pct = round(planned_minutes / net_minutes * 100)
            actual_pct = round(actual_minutes / net_minutes * 100)
            planned_status = _status_for_pct(planned_pct, settings)
            actual_status = _status_for_pct(actual_pct, settings)

        return UserCapacityReport(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            net_capacity_minutes=net_minutes,
            planned_minutes=planned_minutes,
            actual_minutes=actual_minutes,
            open_timer_minutes=open_timer_minutes,
            planned_utilization_pct=planned_pct,
            actual_utilization_pct=actual_pct,
            planned_status=planned_status,
            actual_status=actual_status,
            capacity_status_reason=reason,
        )

    async def team_capacity(
        self, agency_id: uuid.UUID, start_date: date, end_date: date
    ) -> TeamCapacityReport:
        result = await self._db.execute(
            select(AgencyMember).where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.deleted_at.is_(None),
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
            )
        )
        members = list(result.scalars().all())
        names = await self._user_names([m.user_id for m in members])

        reports: list[TeamCapacityMember] = []
        for member in members:
            report = await self.user_capacity(agency_id, member.user_id, start_date, end_date)
            reports.append(
                TeamCapacityMember(
                    **report.model_dump(),
                    user_name=names.get(member.user_id, "Bilinmeyen Kullanıcı"),
                )
            )
        return TeamCapacityReport(start_date=start_date, end_date=end_date, members=reports)

    async def brand_capacity(
        self, agency_id: uuid.UUID, brand_id: uuid.UUID, start_date: date, end_date: date
    ) -> BrandCapacityReport:
        per_user, unassigned = await self._planned_minutes_by_user(
            agency_id, start_date, end_date, brand_id=brand_id
        )
        names = await self._user_names(list(per_user.keys()))
        by_user = [
            BrandCapacityUserShare(
                user_id=uid,
                user_name=names.get(uid, "Bilinmeyen Kullanıcı"),
                planned_minutes=minutes,
            )
            for uid, minutes in sorted(per_user.items(), key=lambda kv: kv[1], reverse=True)
        ]

        start_dt, end_dt = _day_range_to_utc_bounds(start_date, end_date)
        entries = await self._time_entry_repo.list_for_brand(brand_id, agency_id, start_dt, end_dt)
        actual_minutes = (
            sum((e.duration_seconds or 0) for e in entries if e.duration_seconds is not None) / 60
        )

        return BrandCapacityReport(
            brand_id=brand_id,
            start_date=start_date,
            end_date=end_date,
            planned_minutes=sum(per_user.values()) + unassigned,
            unassigned_minutes=unassigned,
            actual_minutes=actual_minutes,
            by_user=by_user,
        )

    async def unassigned_work(
        self, agency_id: uuid.UUID, start_date: date, end_date: date
    ) -> UnassignedWorkReport:
        briefs = await self._active_briefs(agency_id)
        items: list[UnassignedWorkItem] = []
        for brief in briefs:
            tasks = await self._tasks_for_brief(brief.id)
            assignees = await self._assignees_for_brief(brief.id)

            if tasks and any(t.estimated_hours is not None for t in tasks):
                for t in tasks:
                    if t.assigned_to_id is None:
                        items.append(
                            UnassignedWorkItem(
                                brief_id=brief.id,
                                brief_title=brief.title,
                                task_id=t.id,
                                task_title=t.title,
                                minutes=(t.estimated_hours or 0.0) * 60,
                                has_estimate=t.estimated_hours is not None,
                            )
                        )
            elif not assignees:
                breakdown = compute_brief_planned_minutes(brief, tasks, assignees, [])
                if breakdown.unassigned_minutes > 0 or not breakdown.has_estimate:
                    items.append(
                        UnassignedWorkItem(
                            brief_id=brief.id,
                            brief_title=brief.title,
                            task_id=None,
                            task_title=None,
                            minutes=breakdown.unassigned_minutes,
                            has_estimate=breakdown.has_estimate,
                        )
                    )

        return UnassignedWorkReport(
            start_date=start_date,
            end_date=end_date,
            items=items,
            total_minutes=sum(i.minutes for i in items),
        )

    async def _user_names(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not user_ids:
            return {}
        result = await self._db.execute(
            select(User.id, User.full_name).where(User.id.in_(user_ids))
        )
        return {row[0]: row[1] for row in result.all()}
