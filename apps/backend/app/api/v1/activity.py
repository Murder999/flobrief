from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, require_permission
from app.core.rbac import Permission
from app.db.session import get_db
from app.schemas.activity import ActivityLogListResponse, ActivityLogRead
from app.services.activity_service import ActivityLogService

activity_router = APIRouter(prefix="/activity", tags=["activity"])

_WS_VIEW = Depends(require_permission(Permission.AGENCY_VIEW))


@activity_router.get("", response_model=ActivityLogListResponse)
async def list_activity(
    entity_type: Annotated[str | None, Query()] = None,
    actor_user_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    workspace: WorkspaceContext = _WS_VIEW,
    db: AsyncSession = Depends(get_db),
) -> ActivityLogListResponse:
    svc = ActivityLogService(db)
    items, total = await svc.list_for_agency(
        agency_id=workspace.agency.id,
        entity_type=entity_type,
        actor_user_id=actor_user_id,
        limit=limit,
        offset=offset,
    )
    return ActivityLogListResponse(
        items=[ActivityLogRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )
