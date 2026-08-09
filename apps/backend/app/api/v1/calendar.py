from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.brand import Brand
from app.schemas.calendar import (
    CalendarItemAssetRead,
    CalendarItemAssigneeRead,
    CalendarItemCreate,
    CalendarItemDetail,
    CalendarItemRead,
    CalendarItemUpdate,
    StatusChangeRequest,
)
from app.services.agency_calendar_service import (
    AgencyCalendarEntry,
    build_agency_calendar_agenda,
)
from app.services.calendar_service import CalendarService

calendar_router = APIRouter(prefix="/calendar", tags=["calendar"])

_WS_VIEW = Depends(require_permission(Permission.CALENDAR_VIEW))
_WS_MANAGE = Depends(require_permission(Permission.CALENDAR_MANAGE))


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = _WS_VIEW,
) -> CalendarService:
    return CalendarService(db, workspace)


def _svc_write(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = _WS_MANAGE,
) -> CalendarService:
    return CalendarService(db, workspace)


# ── CRUD ──────────────────────────────────────────────────────────────────────


@calendar_router.post("/items", response_model=CalendarItemRead, status_code=201)
async def create_item(
    payload: CalendarItemCreate,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemRead:
    return await svc.create(payload)


@calendar_router.get("/items", response_model=list[CalendarItemRead])
async def list_items(
    brand_id: Annotated[uuid.UUID | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    svc: CalendarService = Depends(_svc),
) -> list[CalendarItemRead]:
    return await svc.list_all(brand_id, platform, status, limit, offset)


@calendar_router.get("/items/{item_id}", response_model=CalendarItemDetail)
async def get_item(
    item_id: uuid.UUID,
    svc: CalendarService = Depends(_svc),
) -> CalendarItemDetail:
    return await svc.get(item_id)


@calendar_router.patch("/items/{item_id}", response_model=CalendarItemRead)
async def update_item(
    item_id: uuid.UUID,
    payload: CalendarItemUpdate,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemRead:
    return await svc.update(item_id, payload)


@calendar_router.delete("/items/{item_id}")
async def delete_item(
    item_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> Response:
    await svc.delete(item_id)
    return Response(status_code=204)


# ── Status change ─────────────────────────────────────────────────────────────


@calendar_router.post("/items/{item_id}/status", response_model=CalendarItemRead)
async def change_status(
    item_id: uuid.UUID,
    payload: StatusChangeRequest,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemRead:
    return await svc.change_status(item_id, payload)


# ── Asset attachment ──────────────────────────────────────────────────────────


@calendar_router.post(
    "/items/{item_id}/assets/{asset_id}",
    response_model=CalendarItemAssetRead,
    status_code=201,
)
async def attach_asset(
    item_id: uuid.UUID,
    asset_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemAssetRead:
    return await svc.attach_asset(item_id, asset_id)


@calendar_router.delete("/items/{item_id}/assets/{asset_id}")
async def detach_asset(
    item_id: uuid.UUID,
    asset_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> Response:
    await svc.detach_asset(item_id, asset_id)
    return Response(status_code=204)


# ── Assignees ─────────────────────────────────────────────────────────────────


@calendar_router.post(
    "/items/{item_id}/assignees/{user_id}",
    response_model=CalendarItemAssigneeRead,
    status_code=201,
)
async def assign_user(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemAssigneeRead:
    return await svc.assign_user(item_id, user_id)


@calendar_router.delete("/items/{item_id}/assignees/{user_id}")
async def unassign_user(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> Response:
    await svc.unassign_user(item_id, user_id)
    return Response(status_code=204)


# ── Views ─────────────────────────────────────────────────────────────────────


@calendar_router.get("/month", response_model=list[CalendarItemRead])
async def month_view(
    year: Annotated[int, Query(ge=2020, le=2099)],
    month: Annotated[int, Query(ge=1, le=12)],
    brand_id: Annotated[uuid.UUID | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    svc: CalendarService = Depends(_svc),
) -> list[CalendarItemRead]:
    return await svc.list_month(year, month, brand_id, platform, status)


@calendar_router.get("/week", response_model=list[CalendarItemRead])
async def week_view(
    year: Annotated[int, Query(ge=2020, le=2099)],
    week: Annotated[int, Query(ge=1, le=53)],
    brand_id: Annotated[uuid.UUID | None, Query()] = None,
    platform: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    svc: CalendarService = Depends(_svc),
) -> list[CalendarItemRead]:
    return await svc.list_week(year, week, brand_id, platform, status)


# ── Brief link ────────────────────────────────────────────────────────────────


@calendar_router.post(
    "/items/{item_id}/brief/{brief_id}",
    response_model=CalendarItemRead,
)
async def link_brief(
    item_id: uuid.UUID,
    brief_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> CalendarItemRead:
    return await svc.link_brief(item_id, brief_id)


@calendar_router.delete("/items/{item_id}/brief")
async def unlink_brief(
    item_id: uuid.UUID,
    svc: CalendarService = Depends(_svc_write),
) -> Response:
    await svc.unlink_brief(item_id)
    return Response(status_code=204)


# ── Agency operations agenda (merged CalendarItem + Brief + Deliverable) ──────


@calendar_router.get("/agenda", response_model=list[AgencyCalendarEntry])
async def agenda(
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    brand_id: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    event_type: Annotated[str | None, Query()] = None,
    assignee_id: Annotated[uuid.UUID | None, Query()] = None,
    priority: Annotated[str | None, Query()] = None,
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = _WS_VIEW,
) -> list[AgencyCalendarEntry]:
    """Unified agency operations calendar: real CalendarItem rows (including
    agency-internal ones with brand_id=NULL) merged with Brief milestone
    dates and Deliverable lifecycle events, all scoped to the caller's
    agency. `brand_id` accepts a brand UUID, the literal "internal" for
    agency-only entries, or is omitted for all brands + agency-internal.
    """
    internal_only = brand_id == "internal"
    parsed_brand_id: uuid.UUID | None = None
    if brand_id and not internal_only:
        try:
            parsed_brand_id = uuid.UUID(brand_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid brand_id") from exc
        result = await db.execute(
            select(Brand.id).where(
                Brand.id == parsed_brand_id,
                Brand.agency_id == workspace.agency.id,
                Brand.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Brand not found in this agency")

    return await build_agency_calendar_agenda(
        db,
        workspace.agency.id,
        date_from=from_date,
        date_to=to_date,
        brand_id=parsed_brand_id,
        internal_only=internal_only,
        status=status,
        event_type=event_type,
        assignee_id=assignee_id,
        priority=priority,
    )
