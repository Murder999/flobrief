from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import set_refresh_cookie
from app.core.auth_dependencies import (
    WorkspaceContext,
    get_workspace_context,
    require_verified,
)
from app.core.rate_limiter import get_client_ip, rate_limit_invitation_signup
from app.db.session import get_db
from app.models.enums import UserType
from app.models.user import User
from app.repositories.agency import AgencyRepository
from app.repositories.brand import BrandRepository
from app.repositories.user import UserRepository
from app.schemas.invitation import (
    AgencyInviteRequest,
    BrandInviteRequest,
    InvitationExistingAccountRequest,
    InvitationPreview,
    InvitationRead,
    InvitationSignupRequest,
    InvitationSignupResponse,
)
from app.services.invitation_service import InvitationService
from app.services.token_service import get_access_token_expire_minutes

invitation_router = APIRouter(prefix="/invitations", tags=["invitations"])


@invitation_router.post(
    "/agency/{agency_id}",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_agency_member(
    agency_id: uuid.UUID,
    data: AgencyInviteRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    svc = InvitationService(db)
    invitation, _ = await svc.create_agency_invite(agency_id, data, workspace.user)
    return InvitationRead.model_validate(invitation)


@invitation_router.post(
    "/brand/{brand_id}",
    response_model=InvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_brand_member(
    brand_id: uuid.UUID,
    data: BrandInviteRequest,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    svc = InvitationService(db)
    invitation, _ = await svc.create_brand_invite(
        brand_id, workspace.agency.id, data, workspace.user
    )
    return InvitationRead.model_validate(invitation)


@invitation_router.get("/preview/{token}", response_model=InvitationPreview)
async def preview_invitation(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InvitationPreview:
    """Public endpoint — no auth required. Returns invitation details for the accept page."""
    svc = InvitationService(db)
    invitation = await svc.get_by_token(token)

    agency_repo = AgencyRepository(db)
    agency = (
        await agency_repo.get_by_id(invitation.agency_id)
        if invitation.agency_id is not None
        else None
    )
    agency_name = agency.name if agency else ""

    brand_name: str | None = None
    if invitation.brand_id:
        brand_repo = BrandRepository(db)
        brand = await brand_repo.get_by_id(invitation.brand_id)
        brand_name = brand.name if brand else None
        if not agency_name and brand_name:
            agency_name = brand_name

    existing_user = (
        await UserRepository(db).get_by_email(invitation.email) if invitation.is_pending else None
    )
    return InvitationPreview(
        agency_name=agency_name,
        brand_name=brand_name,
        invitation_type=invitation.invitation_type,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        state=svc.invitation_state(invitation),
        account_exists=existing_user is not None if invitation.is_pending else None,
        account_type_compatible=(
            existing_user.user_type != UserType.PLATFORM_ADMIN.value
            if existing_user is not None
            else None
        ),
    )


@invitation_router.post(
    "/signup/{token}",
    response_model=InvitationSignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup_and_accept_invitation(
    token: str,
    data: InvitationSignupRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_invitation_signup),
) -> InvitationSignupResponse:
    svc = InvitationService(db)
    user, access_token, refresh_token, redirect_to = await svc.signup_and_accept(
        token,
        data,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_refresh_cookie(response, refresh_token, user.user_type)
    return InvitationSignupResponse(
        access_token=access_token,
        expires_in=get_access_token_expire_minutes(user.user_type) * 60,
        redirect_to=redirect_to,
    )


@invitation_router.post(
    "/activate/{token}",
    response_model=InvitationSignupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def authenticate_and_accept_invitation(
    token: str,
    data: InvitationExistingAccountRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit: None = Depends(rate_limit_invitation_signup),
) -> InvitationSignupResponse:
    """Authenticate an existing recipient and activate the invited membership in one step."""
    svc = InvitationService(db)
    user, access_token, refresh_token, redirect_to = await svc.authenticate_and_accept(
        token,
        data,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    set_refresh_cookie(response, refresh_token, user.user_type)
    return InvitationSignupResponse(
        access_token=access_token,
        expires_in=get_access_token_expire_minutes(user.user_type) * 60,
        redirect_to=redirect_to,
    )


@invitation_router.post("/accept/{token}", response_model=None)
async def accept_invitation(
    token: str,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = InvitationService(db)
    await svc.accept_invitation(token, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.post("/{invitation_id}/revoke", response_model=None)
async def revoke_invitation_by_id(
    invitation_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = InvitationService(db)
    await svc.revoke_by_id(invitation_id, workspace.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.post("/{invitation_id}/resend", response_model=InvitationRead)
async def resend_invitation_by_id(
    invitation_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    svc = InvitationService(db)
    invitation, _ = await svc.resend_by_id(invitation_id, workspace.user)
    return InvitationRead.model_validate(invitation)


@invitation_router.post("/revoke/{token}", response_model=None)
async def revoke_invitation(
    token: str,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> Response:
    svc = InvitationService(db)
    await svc.revoke_invitation(token, workspace.user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.post("/resend/{token}", response_model=InvitationRead)
async def resend_invitation(
    token: str,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> InvitationRead:
    svc = InvitationService(db)
    invitation, _ = await svc.resend_invitation(token, workspace.user)
    return InvitationRead.model_validate(invitation)


@invitation_router.get("/my-pending", response_model=list[InvitationRead])
async def my_pending_invitations(
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationRead]:
    """Returns all pending invitations where email matches current user's email."""
    from app.repositories.invitation import InvitationRepository

    repo = InvitationRepository(db)
    invites = await repo.list_pending_for_email(current_user.email)
    return [InvitationRead.model_validate(i) for i in invites]


@invitation_router.post("/{invitation_id}/reject", response_model=None)
async def reject_invitation_by_id(
    invitation_id: uuid.UUID,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """User rejects their own invitation."""
    svc = InvitationService(db)
    await svc.reject_invitation(invitation_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.post("/{invitation_id}/accept", response_model=None)
async def accept_invitation_by_id(
    invitation_id: uuid.UUID,
    current_user: User = Depends(require_verified),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Accept an invitation by ID (logged-in user must match invitation email)."""
    svc = InvitationService(db)
    await svc.accept_by_id(invitation_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.get("/agency/{agency_id}", response_model=list[InvitationRead])
async def list_agency_invitations(
    agency_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationRead]:
    if workspace.agency.id != agency_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Agency ID eşleşmiyor")
    from app.repositories.invitation import InvitationRepository

    repo = InvitationRepository(db)
    invites = await repo.list_by_agency(agency_id)
    return [InvitationRead.model_validate(i) for i in invites]


@invitation_router.get("/brand/{brand_id}", response_model=list[InvitationRead])
async def list_brand_invitations(
    brand_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[InvitationRead]:
    from app.repositories.invitation import InvitationRepository

    repo = InvitationRepository(db)
    invites = await repo.list_by_brand(brand_id)
    return [InvitationRead.model_validate(i) for i in invites]
