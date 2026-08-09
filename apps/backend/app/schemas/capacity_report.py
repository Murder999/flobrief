"""Read-time capacity report shapes returned by `CapacityCalculationService`.
Every number here is computed fresh on read from WorkSchedule/CapacityException/
TimeOff/Brief/BriefTask/WorkAllocation/TimeEntry rows — nothing is cached or
derived-and-stored, per plan §6."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.time_off import TimeOffRead
from app.schemas.work_allocation import WorkAllocationRead


class UserCapacityReport(BaseModel):
    """Net/planned/actual capacity for one user over one date range.

    `capacity_status_reason` is `"no_schedule"` when the user has no active
    `WorkSchedule` row at all, `"time_off"` when net capacity is zero
    specifically because every would-be working day in the range is covered
    by approved `TimeOff`, `"no_working_days"` when the range simply contains
    no scheduled working days (e.g. a weekend-only query for a Mon-Fri
    schedule), or `"ok"` otherwise. When the reason is not `"ok"`,
    `planned_status`/`actual_status` are `"unknown"` — the frontend must
    render the reason text instead of a bare misleading 0%.
    """

    user_id: uuid.UUID
    start_date: date
    end_date: date
    net_capacity_minutes: int
    planned_minutes: float
    actual_minutes: float
    open_timer_minutes: float
    planned_utilization_pct: int
    actual_utilization_pct: int
    planned_status: str
    actual_status: str
    capacity_status_reason: str


class TeamCapacityMember(UserCapacityReport):
    user_name: str


class TeamCapacityReport(BaseModel):
    start_date: date
    end_date: date
    members: list[TeamCapacityMember]


class BrandCapacityUserShare(BaseModel):
    user_id: uuid.UUID
    user_name: str
    planned_minutes: float


class BrandCapacityReport(BaseModel):
    """Planned/actual workload for one brand, broken down by assignee.
    `unassigned_minutes` is the portion of planned work on this brand's
    briefs that has no assignee to attribute to (see plan §5 step 5)."""

    brand_id: uuid.UUID
    start_date: date
    end_date: date
    planned_minutes: float
    unassigned_minutes: float
    actual_minutes: float
    by_user: list[BrandCapacityUserShare]


class UnassignedWorkItem(BaseModel):
    """One brief (category/flat-estimate source, zero assignees) or one task
    (task-estimate source, `assigned_to_id is None`) with no one to attribute
    planned work to. `has_estimate=False` means the UI should render "Süre
    tahmini yapılmamış" instead of a numeric 0."""

    brief_id: uuid.UUID
    brief_title: str
    task_id: uuid.UUID | None
    task_title: str | None
    minutes: float
    has_estimate: bool


class UnassignedWorkReport(BaseModel):
    start_date: date
    end_date: date
    items: list[UnassignedWorkItem]
    total_minutes: float


class WorkAllocationSaveResult(BaseModel):
    """Wraps a created/updated WorkAllocation with a non-blocking warning —
    imitates `TimeEntryCreateResult`'s overlap_warning pattern."""

    allocation: WorkAllocationRead
    over_capacity_warning: bool = False


class TimeOffSaveResult(BaseModel):
    """Wraps a requested/approved TimeOff with a non-blocking warning that
    the user already has WorkAllocation rows overlapping the leave range."""

    time_off: TimeOffRead
    allocation_warning: bool = False
