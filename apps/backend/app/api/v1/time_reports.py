"""Time reporting endpoints. `weekly` is self-service (any workspace member
can see their own timesheet); `team`/`by-brand`/`by-brief`/`missing`/
`export.csv` are team-scoped and require TIME_ENTRY_VIEW_TEAM — enforced
server-side, not just hidden client-side."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context, require_permission
from app.core.rbac import Permission
from app.core.time_utils import utc_today
from app.db.session import get_db
from app.models.brief import Brief
from app.schemas.time_report import (
    BrandTimeSummary,
    BriefTimeSummary,
    MissingTimesheetResponse,
    TeamTimeReportResponse,
    WeeklyTimesheetResponse,
)
from app.services.time_report_service import TimeReportService
from app.services.time_tracking_service import TimeTrackingService

time_report_router = APIRouter(prefix="/time-reports", tags=["time-reports"])


def _svc(db: AsyncSession = Depends(get_db)) -> TimeReportService:
    return TimeReportService(db)


def _default_week() -> tuple[date, date]:
    today = utc_today()
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


@time_report_router.get("/weekly", response_model=WeeklyTimesheetResponse)
async def weekly_timesheet(
    user_id: uuid.UUID | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(get_workspace_context),
    svc: TimeReportService = Depends(_svc),
) -> WeeklyTimesheetResponse:
    target_user_id = user_id or workspace.user.id
    if target_user_id != workspace.user.id and not workspace.has_permission(
        Permission.TIME_ENTRY_VIEW_TEAM
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Başkasının zaman çizelgesini görüntüleme yetkiniz yok",
        )
    default_start, default_end = _default_week()
    return await svc.weekly_timesheet(
        workspace.agency.id,
        target_user_id,
        start_date or default_start,
        end_date or default_end,
    )


@time_report_router.get("/team", response_model=TeamTimeReportResponse)
async def team_report(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_VIEW_TEAM)),
    svc: TimeReportService = Depends(_svc),
) -> TeamTimeReportResponse:
    default_start, default_end = _default_week()
    return await svc.team_report(
        workspace.agency.id, start_date or default_start, end_date or default_end
    )


@time_report_router.get("/by-brand", response_model=BrandTimeSummary)
async def by_brand_report(
    brand_id: uuid.UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_VIEW_TEAM)),
    svc: TimeReportService = Depends(_svc),
) -> BrandTimeSummary:
    return await svc.brand_summary(workspace.agency.id, brand_id, start_date, end_date)


@time_report_router.get("/by-brief", response_model=BriefTimeSummary)
async def by_brief_report(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_VIEW_TEAM)),
    db: AsyncSession = Depends(get_db),
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
    return await TimeTrackingService(db).compute_brief_time_summary(brief, workspace.agency.id)


@time_report_router.get("/missing", response_model=MissingTimesheetResponse)
async def missing_timesheet(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_VIEW_TEAM)),
    svc: TimeReportService = Depends(_svc),
) -> MissingTimesheetResponse:
    default_start, default_end = _default_week()
    return await svc.missing_timesheet(
        workspace.agency.id, start_date or default_start, end_date or default_end
    )


@time_report_router.get("/export.csv")
async def export_csv(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    workspace: WorkspaceContext = Depends(require_permission(Permission.TIME_ENTRY_VIEW_TEAM)),
    svc: TimeReportService = Depends(_svc),
) -> StreamingResponse:
    default_start, default_end = _default_week()
    effective_start = start_date or default_start
    effective_end = end_date or default_end
    csv_bytes = await svc.export_csv(workspace.agency.id, effective_start, effective_end)
    filename = f"postpiloter-time-entries-{effective_start}-{effective_end}.csv"
    return StreamingResponse(
        BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
