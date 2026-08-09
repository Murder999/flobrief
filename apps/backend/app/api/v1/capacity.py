"""Capacity/resource-planning endpoints (plan §9): schedules, ad-hoc
exceptions, time-off, manual allocations, and read-time capacity reports.
Every mutating endpoint writes an `ActivityLogRepository` row. View endpoints
follow the same own-vs-team split already used by `time_reports.py`:
`CAPACITY_VIEW_OWN` covers the caller's own data, `CAPACITY_VIEW_TEAM` is
required to view anyone else's."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context, require_permission
from app.core.exceptions import PermissionDeniedError
from app.core.rbac import Permission
from app.core.time_utils import utc_today
from app.db.session import get_db
from app.models.work_schedule import WorkSchedule, WorkScheduleDay
from app.repositories.activity import ActivityLogRepository
from app.schemas.capacity_exception import CapacityExceptionCreate, CapacityExceptionRead
from app.schemas.capacity_report import (
    BrandCapacityReport,
    TeamCapacityReport,
    TimeOffSaveResult,
    UnassignedWorkReport,
    UserCapacityReport,
    WorkAllocationSaveResult,
)
from app.schemas.time_off import TimeOffCreate, TimeOffRead, TimeOffReject
from app.schemas.work_allocation import (
    WorkAllocationCreate,
    WorkAllocationRead,
    WorkAllocationUpdate,
)
from app.schemas.work_schedule import WorkScheduleCreate, WorkScheduleDayRead, WorkScheduleRead
from app.services.capacity_calculation_service import CapacityCalculationService
from app.services.capacity_exception_service import CapacityExceptionService
from app.services.time_off_service import TimeOffService
from app.services.work_allocation_service import WorkAllocationService
from app.services.work_schedule_service import WorkScheduleService

capacity_router = APIRouter(prefix="/capacity", tags=["capacity"])


def _require_own_or_view_team(target_user_id: uuid.UUID, workspace: WorkspaceContext) -> None:
    if target_user_id == workspace.user.id:
        if not (
            workspace.has_permission(Permission.CAPACITY_VIEW_OWN)
            or workspace.has_permission(Permission.CAPACITY_VIEW_TEAM)
        ):
            raise PermissionDeniedError("Kapasite görüntüleme yetkiniz yok")
        return
    if not workspace.has_permission(Permission.CAPACITY_VIEW_TEAM):
        raise PermissionDeniedError("Başkasının kapasitesini görüntüleme yetkiniz yok")


def _default_range() -> tuple[date, date]:
    today = utc_today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def _schedule_read(schedule: WorkSchedule, days: list[WorkScheduleDay]) -> WorkScheduleRead:
    return WorkScheduleRead(
        id=schedule.id,
        agency_id=schedule.agency_id,
        user_id=schedule.user_id,
        timezone=schedule.timezone,
        effective_from=schedule.effective_from,
        days=[WorkScheduleDayRead.model_validate(d) for d in days],
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


# ------------------------------------------------------------------
# Schedules


@capacity_router.get("/schedules/{user_id}", response_model=WorkScheduleRead)
async def get_schedule(
    user_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> WorkScheduleRead:
    _require_own_or_view_team(user_id, workspace)
    result = await WorkScheduleService(db).get_active(workspace.agency.id, user_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Çalışma programı bulunamadı"
        )
    schedule, days = result
    return _schedule_read(schedule, days)


@capacity_router.put("/schedules/{user_id}", response_model=WorkScheduleRead)
async def upsert_schedule(
    user_id: uuid.UUID,
    data: WorkScheduleCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_MANAGE_SCHEDULE)),
    db: AsyncSession = Depends(get_db),
) -> WorkScheduleRead:
    payload = data.model_copy(update={"user_id": user_id})
    schedule, days = await WorkScheduleService(db).upsert(workspace.agency.id, payload)

    await ActivityLogRepository(db).create(
        action="work_schedule.updated",
        entity_type="work_schedule",
        entity_id=schedule.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(user_id), "timezone": schedule.timezone},
    )
    await db.commit()
    return _schedule_read(schedule, days)


# ------------------------------------------------------------------
# Capacity exceptions


@capacity_router.get("/exceptions", response_model=list[CapacityExceptionRead])
async def list_exceptions(
    user_id: uuid.UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[CapacityExceptionRead]:
    _require_own_or_view_team(user_id, workspace)
    items = await CapacityExceptionService(db).list_for_user(
        workspace.agency.id, user_id, start, end
    )
    return [CapacityExceptionRead.model_validate(i) for i in items]


@capacity_router.post("/exceptions", response_model=CapacityExceptionRead, status_code=201)
async def create_exception(
    data: CapacityExceptionCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_MANAGE_SCHEDULE)),
    db: AsyncSession = Depends(get_db),
) -> CapacityExceptionRead:
    obj = await CapacityExceptionService(db).create(workspace.agency.id, workspace.user.id, data)

    await ActivityLogRepository(db).create(
        action="capacity_exception.created",
        entity_type="capacity_exception",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={
            "target_user_id": str(data.user_id),
            "date": data.date.isoformat(),
            "exception_type": data.exception_type,
        },
    )
    await db.commit()
    return CapacityExceptionRead.model_validate(obj)


@capacity_router.delete("/exceptions/{exception_id}", status_code=204, response_model=None)
async def delete_exception(
    exception_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_MANAGE_SCHEDULE)),
    db: AsyncSession = Depends(get_db),
) -> None:
    await CapacityExceptionService(db).delete(workspace.agency.id, exception_id)

    await ActivityLogRepository(db).create(
        action="capacity_exception.deleted",
        entity_type="capacity_exception",
        entity_id=exception_id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
    )
    await db.commit()


# ------------------------------------------------------------------
# Time off


@capacity_router.get("/time-off", response_model=list[TimeOffRead])
async def list_time_off(
    user_id: uuid.UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[TimeOffRead]:
    _require_own_or_view_team(user_id, workspace)
    start_dt = datetime.combine(start, datetime.min.time()).replace(tzinfo=UTC) if start else None
    end_dt = datetime.combine(end, datetime.max.time()).replace(tzinfo=UTC) if end else None
    items = await TimeOffService(db).list_for_user(workspace.agency.id, user_id, start_dt, end_dt)
    return [TimeOffRead.model_validate(i) for i in items]


@capacity_router.post("/time-off", response_model=TimeOffSaveResult, status_code=201)
async def request_time_off(
    data: TimeOffCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_OFF_REQUEST)),
    db: AsyncSession = Depends(get_db),
) -> TimeOffSaveResult:
    if data.user_id != workspace.user.id and not workspace.has_permission(
        Permission.TIME_OFF_APPROVE
    ):
        raise PermissionDeniedError("Başkası adına izin talebi oluşturma yetkiniz yok")

    obj, warning = await TimeOffService(db).request(workspace.agency.id, data)

    await ActivityLogRepository(db).create(
        action="time_off.requested",
        entity_type="time_off",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(data.user_id), "type": data.type, "all_day": data.all_day},
    )
    await db.commit()
    return TimeOffSaveResult(time_off=TimeOffRead.model_validate(obj), allocation_warning=warning)


@capacity_router.patch("/time-off/{time_off_id}/approve", response_model=TimeOffSaveResult)
async def approve_time_off(
    time_off_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_OFF_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> TimeOffSaveResult:
    obj, warning = await TimeOffService(db).approve(
        workspace.agency.id, time_off_id, workspace.user.id
    )

    await ActivityLogRepository(db).create(
        action="time_off.approved",
        entity_type="time_off",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(obj.user_id)},
    )
    await db.commit()
    return TimeOffSaveResult(time_off=TimeOffRead.model_validate(obj), allocation_warning=warning)


@capacity_router.patch("/time-off/{time_off_id}/reject", response_model=TimeOffRead)
async def reject_time_off(
    time_off_id: uuid.UUID,
    data: TimeOffReject,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_OFF_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> TimeOffRead:
    obj = await TimeOffService(db).reject(workspace.agency.id, time_off_id, workspace.user.id, data)

    await ActivityLogRepository(db).create(
        action="time_off.rejected",
        entity_type="time_off",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(obj.user_id)},
    )
    await db.commit()
    return TimeOffRead.model_validate(obj)


# ------------------------------------------------------------------
# Manual allocations


@capacity_router.get("/allocations", response_model=list[WorkAllocationRead])
async def list_allocations(
    user_id: uuid.UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[WorkAllocationRead]:
    _require_own_or_view_team(user_id, workspace)
    items = await WorkAllocationService(db).list_for_user(workspace.agency.id, user_id, start, end)
    return [WorkAllocationRead.model_validate(i) for i in items]


@capacity_router.post("/allocations", response_model=WorkAllocationSaveResult, status_code=201)
async def create_allocation(
    data: WorkAllocationCreate,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.CAPACITY_MANAGE_ALLOCATION)
    ),
    db: AsyncSession = Depends(get_db),
) -> WorkAllocationSaveResult:
    obj, warning = await WorkAllocationService(db).create(
        workspace.agency.id, workspace.user.id, data
    )

    await ActivityLogRepository(db).create(
        action="work_allocation.created",
        entity_type="work_allocation",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        brand_id=obj.brand_id,
        actor_user_id=workspace.user.id,
        meta={
            "target_user_id": str(obj.user_id),
            "brief_id": str(obj.brief_id) if obj.brief_id else None,
            "allocated_minutes": obj.allocated_minutes,
        },
    )
    await db.commit()
    return WorkAllocationSaveResult(
        allocation=WorkAllocationRead.model_validate(obj), over_capacity_warning=warning
    )


@capacity_router.patch("/allocations/{allocation_id}", response_model=WorkAllocationSaveResult)
async def update_allocation(
    allocation_id: uuid.UUID,
    data: WorkAllocationUpdate,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.CAPACITY_MANAGE_ALLOCATION)
    ),
    db: AsyncSession = Depends(get_db),
) -> WorkAllocationSaveResult:
    obj, warning = await WorkAllocationService(db).update(workspace.agency.id, allocation_id, data)

    await ActivityLogRepository(db).create(
        action="work_allocation.updated",
        entity_type="work_allocation",
        entity_id=obj.id,
        agency_id=workspace.agency.id,
        brand_id=obj.brand_id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(obj.user_id), "allocated_minutes": obj.allocated_minutes},
    )
    await db.commit()
    return WorkAllocationSaveResult(
        allocation=WorkAllocationRead.model_validate(obj), over_capacity_warning=warning
    )


@capacity_router.delete("/allocations/{allocation_id}", status_code=204, response_model=None)
async def delete_allocation(
    allocation_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(
        require_permission(Permission.CAPACITY_MANAGE_ALLOCATION)
    ),
    db: AsyncSession = Depends(get_db),
) -> None:
    svc = WorkAllocationService(db)
    obj = await svc.get(workspace.agency.id, allocation_id)
    target_user_id = obj.user_id
    await svc.delete(workspace.agency.id, allocation_id)

    await ActivityLogRepository(db).create(
        action="work_allocation.deleted",
        entity_type="work_allocation",
        entity_id=allocation_id,
        agency_id=workspace.agency.id,
        actor_user_id=workspace.user.id,
        meta={"target_user_id": str(target_user_id)},
    )
    await db.commit()


# ------------------------------------------------------------------
# Reports


@capacity_router.get("/report/team", response_model=TeamCapacityReport)
async def team_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_VIEW_TEAM)),
    db: AsyncSession = Depends(get_db),
) -> TeamCapacityReport:
    default_start, default_end = _default_range()
    return await CapacityCalculationService(db).team_capacity(
        workspace.agency.id, start_date or default_start, end_date or default_end
    )


@capacity_router.get("/report/user/{user_id}", response_model=UserCapacityReport)
async def user_report(
    user_id: uuid.UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> UserCapacityReport:
    _require_own_or_view_team(user_id, workspace)
    default_start, default_end = _default_range()
    return await CapacityCalculationService(db).user_capacity(
        workspace.agency.id, user_id, start_date or default_start, end_date or default_end
    )


@capacity_router.get("/report/brand/{brand_id}", response_model=BrandCapacityReport)
async def brand_report(
    brand_id: uuid.UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_VIEW_TEAM)),
    db: AsyncSession = Depends(get_db),
) -> BrandCapacityReport:
    default_start, default_end = _default_range()
    return await CapacityCalculationService(db).brand_capacity(
        workspace.agency.id, brand_id, start_date or default_start, end_date or default_end
    )


@capacity_router.get("/report/unassigned", response_model=UnassignedWorkReport)
async def unassigned_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.CAPACITY_VIEW_TEAM)),
    db: AsyncSession = Depends(get_db),
) -> UnassignedWorkReport:
    default_start, default_end = _default_range()
    return await CapacityCalculationService(db).unassigned_work(
        workspace.agency.id, start_date or default_start, end_date or default_end
    )
