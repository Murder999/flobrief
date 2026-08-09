from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import HTTP_204_NO_CONTENT

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.db.session import get_db
from app.models.brief import BriefAssignee
from app.models.user import User
from app.schemas.brief import (
    AssigneeAdd,
    AssigneeRead,
    BriefCreate,
    BriefDetail,
    BriefFieldValuesUpdate,
    BriefListResponse,
    BriefParticipantCreate,
    BriefParticipantRead,
    BriefParticipantUpdate,
    BriefStatusUpdate,
    BriefUpdate,
)
from app.services.brief_service import BriefService

brief_router = APIRouter(prefix="/briefs", tags=["briefs"])


def _svc(
    db: AsyncSession = Depends(get_db),
    workspace: WorkspaceContext = Depends(get_workspace_context),
) -> BriefService:
    return BriefService(db, workspace)


@brief_router.get("", response_model=BriefListResponse)
async def list_briefs(
    brand_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assignee_id: uuid.UUID | None = Query(default=None),
    deadline_before: str | None = Query(default=None),
    search: str | None = Query(default=None),
    source: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    svc: BriefService = Depends(_svc),
) -> BriefListResponse:
    return await svc.list_briefs(
        brand_id=brand_id,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        deadline_before=deadline_before,
        search=search,
        source=source,
        offset=offset,
        limit=limit,
    )


@brief_router.post("", response_model=BriefDetail, status_code=201)
async def create_brief(
    payload: BriefCreate,
    svc: BriefService = Depends(_svc),
) -> BriefDetail:
    return await svc.create(payload)


@brief_router.get("/{brief_id}", response_model=BriefDetail)
async def get_brief(
    brief_id: uuid.UUID,
    svc: BriefService = Depends(_svc),
) -> BriefDetail:
    return await svc.get_detail(brief_id)


@brief_router.patch("/{brief_id}", response_model=BriefDetail)
async def update_brief(
    brief_id: uuid.UUID,
    payload: BriefUpdate,
    svc: BriefService = Depends(_svc),
) -> BriefDetail:
    return await svc.update(brief_id, payload)


@brief_router.patch("/{brief_id}/status", response_model=BriefDetail)
async def change_brief_status(
    brief_id: uuid.UUID,
    payload: BriefStatusUpdate,
    svc: BriefService = Depends(_svc),
) -> BriefDetail:
    return await svc.change_status(brief_id, payload)


@brief_router.delete("/{brief_id}", response_model=None)
async def archive_brief(
    brief_id: uuid.UUID,
    svc: BriefService = Depends(_svc),
) -> Response:
    await svc.archive(brief_id)
    return Response(status_code=HTTP_204_NO_CONTENT)


@brief_router.put("/{brief_id}/field-values", response_model=BriefDetail)
async def update_field_values(
    brief_id: uuid.UUID,
    payload: BriefFieldValuesUpdate,
    svc: BriefService = Depends(_svc),
) -> BriefDetail:
    return await svc.update_field_values(brief_id, payload)


@brief_router.post("/{brief_id}/assignees", response_model=AssigneeRead, status_code=201)
async def assign_user(
    brief_id: uuid.UUID,
    payload: AssigneeAdd,
    svc: BriefService = Depends(_svc),
) -> AssigneeRead:
    return await svc.assign_user(brief_id, payload)


@brief_router.delete("/{brief_id}/assignees/{user_id}", response_model=None)
async def unassign_user(
    brief_id: uuid.UUID,
    user_id: uuid.UUID,
    svc: BriefService = Depends(_svc),
) -> Response:
    await svc.unassign_user(brief_id, user_id)
    return Response(status_code=HTTP_204_NO_CONTENT)


async def _get_participant(
    brief_id: uuid.UUID,
    participant_id: uuid.UUID,
    db: AsyncSession,
    agency_id: uuid.UUID,
) -> BriefAssignee:
    from app.models.brief import Brief

    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief bulunamadı")

    p_result = await db.execute(
        select(BriefAssignee).where(
            BriefAssignee.id == participant_id,
            BriefAssignee.brief_id == brief_id,
        )
    )
    participant = p_result.scalar_one_or_none()
    if participant is None:
        raise HTTPException(status_code=404, detail="Katılımcı bulunamadı")
    return participant


async def _build_participant_read(
    assignee: BriefAssignee, db: AsyncSession
) -> BriefParticipantRead:
    user_result = await db.execute(select(User).where(User.id == assignee.user_id))
    user = user_result.scalar_one_or_none()
    return BriefParticipantRead(
        id=assignee.id,
        brief_id=assignee.brief_id,
        user_id=assignee.user_id,
        user_name=user.full_name if user else None,
        user_email=user.email if user else None,
        participant_role=assignee.participant_role,
        role_label=assignee.role_label,
        can_comment=assignee.can_comment,
        can_upload=assignee.can_upload,
        can_edit=assignee.can_edit,
        can_approve=assignee.can_approve,
        can_request_revision=assignee.can_request_revision,
        created_at=assignee.created_at,
    )


@brief_router.get("/{brief_id}/participants", response_model=list[BriefParticipantRead])
async def list_participants(
    brief_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[BriefParticipantRead]:
    from app.models.brief import Brief

    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == workspace.agency.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief bulunamadı")

    p_result = await db.execute(select(BriefAssignee).where(BriefAssignee.brief_id == brief_id))
    participants = list(p_result.scalars().all())
    return [await _build_participant_read(p, db) for p in participants]


@brief_router.post("/{brief_id}/participants", response_model=BriefParticipantRead, status_code=201)
async def add_participant(
    brief_id: uuid.UUID,
    payload: BriefParticipantCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BriefParticipantRead:
    from app.models.brief import Brief
    from app.repositories.agency_member import AgencyMemberRepository

    result = await db.execute(
        select(Brief).where(
            Brief.id == brief_id,
            Brief.agency_id == workspace.agency.id,
            Brief.deleted_at.is_(None),
        )
    )
    brief = result.scalar_one_or_none()
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief bulunamadı")

    # Check user is an agency member
    member_repo = AgencyMemberRepository(db)
    member = await member_repo.get_membership(workspace.agency.id, payload.user_id)
    if member is None:
        raise HTTPException(status_code=400, detail="Kullanıcı bu agency'ye üye değil")

    # Check if already a participant
    existing = await db.execute(
        select(BriefAssignee).where(
            BriefAssignee.brief_id == brief_id,
            BriefAssignee.user_id == payload.user_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Kullanıcı zaten bu brief'e atanmış")

    assignee = BriefAssignee(
        brief_id=brief_id,
        user_id=payload.user_id,
        role_label=payload.role_label,
        participant_role=payload.participant_role,
        can_comment=payload.can_comment,
        can_upload=payload.can_upload,
        can_edit=payload.can_edit,
        can_approve=payload.can_approve,
        can_request_revision=payload.can_request_revision,
    )
    db.add(assignee)
    await db.flush()
    await db.refresh(assignee)
    await db.commit()

    try:
        from app.models.enums import NotificationEventType
        from app.services.notification_dispatcher import NotificationDispatcher

        await NotificationDispatcher(db).emit(
            NotificationEventType.BRIEF_ASSIGNED.value,
            payload={
                "brief_id": str(brief_id),
                "brief_title": brief.title,
                "assignee_id": str(payload.user_id),
                "summary": f"Bir brief'e atandınız: {brief.title}",
            },
            agency_id=workspace.agency.id,
            brand_id=brief.brand_id,
            actor_user_id=workspace.user.id,
            recipient_ids=[payload.user_id],
        )
    except Exception:
        pass

    return await _build_participant_read(assignee, db)


@brief_router.patch(
    "/{brief_id}/participants/{participant_id}", response_model=BriefParticipantRead
)
async def update_participant(
    brief_id: uuid.UUID,
    participant_id: uuid.UUID,
    payload: BriefParticipantUpdate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> BriefParticipantRead:
    assignee = await _get_participant(brief_id, participant_id, db, workspace.agency.id)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assignee, key, value)
    await db.flush()
    await db.refresh(assignee)
    await db.commit()
    return await _build_participant_read(assignee, db)


@brief_router.delete("/{brief_id}/participants/{participant_id}", response_model=None)
async def remove_participant(
    brief_id: uuid.UUID,
    participant_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    assignee = await _get_participant(brief_id, participant_id, db, workspace.agency.id)
    await db.delete(assignee)
    await db.commit()
    return Response(status_code=HTTP_204_NO_CONTENT)
