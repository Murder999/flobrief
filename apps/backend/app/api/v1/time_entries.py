"""Time tracking endpoints — timers, manual entries, locking, and per-brief
estimate summaries. No brand-portal router exists for this module at all —
a structural guarantee that brand users can never see agency-internal hours."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context, require_permission
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.brief import Brief
from app.models.time_entry import TimeEntry
from app.repositories.time_entry import TimeEntryRepository
from app.schemas.time_entry import (
    ActiveTimerRead,
    TimeEntryCreateResult,
    TimeEntryManualCreate,
    TimeEntryRead,
    TimeEntryStart,
    TimeEntryStop,
    TimeEntryUpdate,
)
from app.schemas.time_report import BriefTimeSummary
from app.services.time_tracking_service import TimeTrackingService

time_entry_router = APIRouter(prefix="/time-entries", tags=["time-entries"])
brief_time_router = APIRouter(tags=["time-entries"])


def _svc(db: AsyncSession = Depends(get_db)) -> TimeTrackingService:
    return TimeTrackingService(db)


async def _require_entry(
    entry_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> TimeEntry:
    repo = TimeEntryRepository(db)
    entry = await repo.get_by_id(entry_id, workspace.agency.id)
    if entry is None:
        raise NotFoundError("Zaman kaydı", str(entry_id))
    return entry


def _require_own_or_manage(entry: TimeEntry, workspace: WorkspaceContext) -> None:
    if entry.user_id != workspace.user.id and not workspace.has_permission(
        Permission.TIME_ENTRY_MANAGE
    ):
        raise PermissionDeniedError("Bu kaydı düzenleme yetkiniz yok")


@time_entry_router.post("/start", response_model=TimeEntryRead, status_code=201)
async def start_timer(
    data: TimeEntryStart,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_LOG)),
    svc: TimeTrackingService = Depends(_svc),
) -> TimeEntryRead:
    entry = await svc.start_timer(workspace.agency.id, workspace.user.id, data)
    return TimeEntryRead.model_validate(entry)


@time_entry_router.get("/active", response_model=ActiveTimerRead | None)
async def get_active_timer(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: TimeTrackingService = Depends(_svc),
) -> ActiveTimerRead | None:
    entry = await svc.get_active_timer(workspace.user.id)
    if entry is None or entry.agency_id != workspace.agency.id:
        return None
    return ActiveTimerRead.model_validate(entry)


@time_entry_router.post("/{entry_id}/stop", response_model=TimeEntryCreateResult)
async def stop_timer(
    entry_id: uuid.UUID,
    data: TimeEntryStop,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: TimeTrackingService = Depends(_svc),
) -> TimeEntryCreateResult:
    can_manage_peers = workspace.has_permission(Permission.TIME_ENTRY_MANAGE)
    return await svc.stop_timer(
        workspace.agency.id, workspace.user.id, entry_id, data, can_manage_peers
    )


@time_entry_router.post("", response_model=TimeEntryCreateResult, status_code=201)
async def create_manual_entry(
    data: TimeEntryManualCreate,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_LOG)),
    svc: TimeTrackingService = Depends(_svc),
) -> TimeEntryCreateResult:
    return await svc.create_manual_entry(workspace.agency.id, workspace.user.id, data)


@time_entry_router.get("/{entry_id}", response_model=TimeEntryRead)
async def get_entry(
    entry_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> TimeEntryRead:
    entry = await _require_entry(entry_id, workspace, db)
    if entry.user_id != workspace.user.id and not workspace.has_permission(
        Permission.TIME_ENTRY_VIEW_TEAM
    ):
        raise PermissionDeniedError("Bu kaydı görüntüleme yetkiniz yok")
    return TimeEntryRead.model_validate(entry)


@time_entry_router.patch("/{entry_id}", response_model=TimeEntryRead)
async def update_entry(
    entry_id: uuid.UUID,
    data: TimeEntryUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
    svc: TimeTrackingService = Depends(_svc),
) -> TimeEntryRead:
    entry = await _require_entry(entry_id, workspace, db)
    _require_own_or_manage(entry, workspace)
    updated = await svc.update_entry(entry, data)
    return TimeEntryRead.model_validate(updated)


@time_entry_router.delete("/{entry_id}", status_code=204, response_model=None)
async def delete_entry(
    entry_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
    svc: TimeTrackingService = Depends(_svc),
) -> None:
    entry = await _require_entry(entry_id, workspace, db)
    _require_own_or_manage(entry, workspace)
    await svc.delete_entry(entry)


@time_entry_router.post("/{entry_id}/lock", response_model=TimeEntryRead)
async def lock_entry(
    entry_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_APPROVE)),
    db: AsyncSession = Depends(get_db),
    svc: TimeTrackingService = Depends(_svc),
) -> TimeEntryRead:
    entry = await _require_entry(entry_id, workspace, db)
    locked = await svc.lock_entry(entry, workspace.user.id)
    return TimeEntryRead.model_validate(locked)


@brief_time_router.get("/briefs/{brief_id}/time-summary", response_model=BriefTimeSummary)
async def get_brief_time_summary(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
    svc: TimeTrackingService = Depends(_svc),
) -> BriefTimeSummary:
    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == workspace.agency.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brief bulunamadı")
    return await svc.compute_brief_time_summary(brief, workspace.agency.id)
