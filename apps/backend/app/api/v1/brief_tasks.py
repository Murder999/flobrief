"""Brief task/milestone endpoints — agency production planning per brief."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.models.brief import Brief
from app.models.brief_task import BriefTask
from app.models.enums import NotificationEventType
from app.schemas.brief_task import BriefTaskCreate, BriefTaskRead, BriefTaskUpdate

task_router = APIRouter(tags=["brief-tasks"])


async def _require_brief(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> Brief:
    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == workspace.agency.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if not brief:
        raise HTTPException(status_code=404, detail="Brief bulunamadı")
    return brief


async def _require_task(
    brief_id: uuid.UUID,
    task_id: uuid.UUID,
    workspace: WorkspaceContext,
    db: AsyncSession,
) -> BriefTask:
    result = await db.execute(
        select(BriefTask).where(
            BriefTask.id == task_id,
            BriefTask.brief_id == brief_id,
            BriefTask.agency_id == workspace.agency.id,
            BriefTask.deleted_at.is_(None),
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    return task


@task_router.get("/briefs/{brief_id}/tasks", response_model=list[BriefTaskRead])
async def list_tasks(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[BriefTaskRead]:
    await _require_brief(brief_id, workspace, db)
    rows = await db.execute(
        select(BriefTask)
        .where(
            BriefTask.brief_id == brief_id,
            BriefTask.agency_id == workspace.agency.id,
            BriefTask.deleted_at.is_(None),
        )
        .order_by(BriefTask.created_at.asc())
    )
    return [BriefTaskRead.model_validate(t) for t in rows.scalars().all()]


@task_router.post(
    "/briefs/{brief_id}/tasks",
    response_model=BriefTaskRead,
    status_code=201,
)
async def create_task(
    brief_id: uuid.UUID,
    data: BriefTaskCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BriefTaskRead:
    brief = await _require_brief(brief_id, workspace, db)
    task = BriefTask(
        agency_id=workspace.agency.id,
        brand_id=brief.brand_id,
        brief_id=brief_id,
        title=data.title,
        description=data.description,
        assigned_to_id=data.assigned_to_id,
        due_date=data.due_date,
        status=data.status,
        visibility=data.visibility,
        is_milestone=data.is_milestone,
        estimated_hours=data.estimated_hours,
        created_by_id=workspace.user.id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    if data.assigned_to_id and data.assigned_to_id != workspace.user.id:
        from app.services.notification_dispatcher import NotificationDispatcher

        d = NotificationDispatcher(db)
        await d.emit(
            NotificationEventType.MILESTONE_ASSIGNED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "task_title": data.title,
                "summary": f"'{data.title}' görevi size atandı",
            },
            agency_id=workspace.agency.id,
            brand_id=brief.brand_id,
            actor_user_id=workspace.user.id,
            recipient_ids=[data.assigned_to_id],
        )

    return BriefTaskRead.model_validate(task)


@task_router.patch(
    "/briefs/{brief_id}/tasks/{task_id}",
    response_model=BriefTaskRead,
)
async def update_task(
    brief_id: uuid.UUID,
    task_id: uuid.UUID,
    data: BriefTaskUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BriefTaskRead:
    task = await _require_task(brief_id, task_id, workspace, db)
    prev_assigned = task.assigned_to_id

    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.assigned_to_id is not None:
        task.assigned_to_id = data.assigned_to_id
    if data.due_date is not None:
        task.due_date = data.due_date
    if data.status is not None:
        task.status = data.status
    if data.visibility is not None:
        task.visibility = data.visibility
    if data.is_milestone is not None:
        task.is_milestone = data.is_milestone
    if data.estimated_hours is not None:
        task.estimated_hours = data.estimated_hours

    await db.commit()
    await db.refresh(task)

    new_assigned = task.assigned_to_id
    if new_assigned and new_assigned != prev_assigned and new_assigned != workspace.user.id:
        brief = await _require_brief(brief_id, workspace, db)
        from app.services.notification_dispatcher import NotificationDispatcher

        d = NotificationDispatcher(db)
        await d.emit(
            NotificationEventType.MILESTONE_ASSIGNED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "task_title": task.title,
                "summary": f"'{task.title}' görevi size atandı",
            },
            agency_id=workspace.agency.id,
            brand_id=task.brand_id,
            actor_user_id=workspace.user.id,
            recipient_ids=[new_assigned],
        )

    return BriefTaskRead.model_validate(task)


@task_router.delete(
    "/briefs/{brief_id}/tasks/{task_id}",
    status_code=204,
    response_model=None,
)
async def delete_task(
    brief_id: uuid.UUID,
    task_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await _require_task(brief_id, task_id, workspace, db)
    from datetime import UTC, datetime

    task.deleted_at = datetime.now(UTC)
    await db.commit()
