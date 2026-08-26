from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context, require_verified
from app.core.brand_portal_auth import BrandPortalContext, get_brand_portal_context
from app.core.rate_limiter import rate_limit_partnership_invitation
from app.db.session import get_db
from app.models.enums import AgencyMemberRole, BrandMemberRole
from app.models.user import User
from app.schemas.partnership_invitation import (
    PartnershipAcceptResponse,
    PartnershipInvitationPreview,
    PartnershipInvitationRead,
    PartnershipInviteAccept,
    PartnershipInviteCreate,
)
from app.services.partnership_invitation_service import PartnershipInvitationService

partnership_invitation_router = APIRouter(
    prefix="/partnership-invitations",
    tags=["partnership-invitations"],
)


@partnership_invitation_router.post(
    "/agency",
    response_model=PartnershipInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_from_agency(
    data: PartnershipInviteCreate,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> PartnershipInvitationRead:
    await rate_limit_partnership_invitation(str(workspace.user.id))
    invitation = await PartnershipInvitationService(db).create_from_agency(
        workspace.agency,
        workspace.member,
        workspace.user,
        data,
    )
    return PartnershipInvitationRead.model_validate(invitation)


@partnership_invitation_router.post(
    "/brand",
    response_model=PartnershipInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_from_brand(
    data: PartnershipInviteCreate,
    context: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> PartnershipInvitationRead:
    await rate_limit_partnership_invitation(str(context.user.id))
    invitation = await PartnershipInvitationService(db).create_from_brand(
        context.brand,
        context.membership,
        context.user,
        data,
    )
    return PartnershipInvitationRead.model_validate(invitation)


@partnership_invitation_router.get(
    "/agency",
    response_model=list[PartnershipInvitationRead],
)
async def list_for_agency(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[PartnershipInvitationRead]:
    if workspace.member.role not in {
        AgencyMemberRole.OWNER.value,
        AgencyMemberRole.ADMIN.value,
    }:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "İş ortaklığı davetlerini görme yetkiniz yok",
        )
    items = await PartnershipInvitationService(db).list_for_agency(workspace.agency.id)
    return [PartnershipInvitationRead.model_validate(item) for item in items]


@partnership_invitation_router.get(
    "/brand",
    response_model=list[PartnershipInvitationRead],
)
async def list_for_brand(
    context: BrandPortalContext = Depends(get_brand_portal_context),
    db: AsyncSession = Depends(get_db),
) -> list[PartnershipInvitationRead]:
    if context.membership.role not in {
        BrandMemberRole.BRAND_OWNER.value,
        BrandMemberRole.BRAND_MANAGER.value,
    }:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "İş ortaklığı davetlerini görme yetkiniz yok",
        )
    items = await PartnershipInvitationService(db).list_for_brand(context.brand.id)
    return [PartnershipInvitationRead.model_validate(item) for item in items]


@partnership_invitation_router.get(
    "/incoming",
    response_model=list[PartnershipInvitationRead],
)
async def list_incoming(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> list[PartnershipInvitationRead]:
    items = await PartnershipInvitationService(db).list_incoming(current_user)
    return [PartnershipInvitationRead.model_validate(item) for item in items]


@partnership_invitation_router.get(
    "/preview/{token}",
    response_model=PartnershipInvitationPreview,
)
async def preview(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PartnershipInvitationPreview:
    return await PartnershipInvitationService(db).preview(token)


@partnership_invitation_router.post(
    "/accept/{token}",
    response_model=PartnershipAcceptResponse,
)
async def accept(
    token: str,
    data: PartnershipInviteAccept,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> PartnershipAcceptResponse:
    return await PartnershipInvitationService(db).accept(
        token,
        data.target_workspace_id,
        current_user,
        data.new_workspace_name,
    )


@partnership_invitation_router.post(
    "/{invitation_id}/revoke",
    status_code=204,
    response_model=None,
)
async def revoke(
    invitation_id: uuid.UUID,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await PartnershipInvitationService(db).revoke(invitation_id, current_user)
    return Response(status_code=204)
