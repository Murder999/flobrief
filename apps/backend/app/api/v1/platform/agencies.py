"""Platform admin — agency management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.activity import ActivityLog
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.comment import Comment, CommentThread
from app.models.enums import AgencyMemberRole, AgencyMemberStatus, AgencyStatus, SubscriptionStatus
from app.models.invitation import Invitation
from app.models.plan import Plan
from app.models.platform_audit_log import PlatformAuditLog
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform import (
    AgencySuspendRequest,
    PlatformAgencyBrandingRead,
    PlatformAgencyCreateRequest,
    PlatformAgencyCreateResponse,
    PlatformAgencyDetail,
    PlatformAgencyMemberRead,
    PlatformAgencyMemberUpdate,
    PlatformAgencyPlanUpdate,
    PlatformAgencyRead,
    PlatformAgencyUpdate,
    PlatformAgencyUsage,
    PlatformInvitationRead,
    PlatformMemberAttachRequest,
    PlatformMemberInviteRequest,
)
from app.services.branding_service import BrandingService
from app.services.invitation_service import InvitationService
from app.services.platform_provisioning_service import PlatformProvisioningService

platform_agencies_router = APIRouter(prefix="/agencies", tags=["platform-agencies"])


async def _get_agency_or_404(db: AsyncSession, agency_id: uuid.UUID) -> Agency:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    return ag


async def _count_members(db: AsyncSession, agency_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(AgencyMember)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def _count_brands(db: AsyncSession, agency_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Brand)
        .where(
            Brand.agency_id == agency_id,
            Brand.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def _get_subscription_info(
    db: AsyncSession, agency_id: uuid.UUID
) -> tuple[str | None, str | None, str | None, int | None]:
    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.agency_id == agency_id, Subscription.deleted_at.is_(None))
    )
    row = result.first()
    if row is None:
        return None, None, None, None
    sub, plan = row
    return sub.status, plan.name, plan.code, plan.monthly_price_cents


def _platform_invitation_read(invitation: Invitation) -> PlatformInvitationRead:
    return PlatformInvitationRead(
        id=invitation.id,
        invitation_type=invitation.invitation_type,
        email=invitation.email,
        role=invitation.role,
        state=InvitationService.invitation_state(invitation),
        expires_at=invitation.expires_at,
        resent_count=invitation.resent_count,
        created_at=invitation.created_at,
    )


@platform_agencies_router.post(
    "",
    response_model=PlatformAgencyCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agency_by_platform(
    body: PlatformAgencyCreateRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyCreateResponse:
    result = await PlatformProvisioningService(db).create_agency(
        body,
        admin=admin,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    agency = result.agency
    return PlatformAgencyCreateResponse(
        agency=PlatformAgencyRead(
            id=agency.id,
            name=agency.name,
            slug=agency.slug,
            status=agency.status,
            owner_user_id=agency.owner_user_id,
            plan_id=agency.plan_id,
            member_count=await _count_members(db, agency.id),
            brand_count=0,
            created_at=agency.created_at,
            updated_at=agency.updated_at,
        ),
        owner_action=result.owner_action,
        owner_email=result.owner_email,
    )


@platform_agencies_router.get("", response_model=list[PlatformAgencyRead])
async def list_agencies(
    limit: int = 50,
    offset: int = 0,
    status_filter: str | None = None,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformAgencyRead]:
    stmt = (
        select(Agency)
        .where(Agency.deleted_at.is_(None), Agency.is_demo.is_(False))
        .order_by(Agency.created_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Agency.status == status_filter)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    agencies = result.scalars().all()

    out = []
    for ag in agencies:
        out.append(
            PlatformAgencyRead(
                id=ag.id,
                name=ag.name,
                slug=ag.slug,
                status=ag.status,
                owner_user_id=ag.owner_user_id,
                plan_id=ag.plan_id,
                member_count=await _count_members(db, ag.id),
                brand_count=await _count_brands(db, ag.id),
                created_at=ag.created_at,
                updated_at=ag.updated_at,
            )
        )
    return out


@platform_agencies_router.get("/{agency_id}", response_model=PlatformAgencyDetail)
async def get_agency_detail(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyDetail:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    sub_status, plan_name, plan_code, price = await _get_subscription_info(db, agency_id)
    return PlatformAgencyDetail(
        id=ag.id,
        name=ag.name,
        slug=ag.slug,
        status=ag.status,
        owner_user_id=ag.owner_user_id,
        plan_id=ag.plan_id,
        member_count=await _count_members(db, ag.id),
        brand_count=await _count_brands(db, ag.id),
        created_at=ag.created_at,
        updated_at=ag.updated_at,
        subscription_status=sub_status,
        plan_name=plan_name,
        plan_code=plan_code,
        monthly_price_cents=price,
    )


@platform_agencies_router.patch("/{agency_id}", response_model=PlatformAgencyDetail)
async def update_agency(
    agency_id: uuid.UUID,
    body: PlatformAgencyUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyDetail:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    changed: dict = {}
    if body.name is not None:
        changed["name"] = body.name
        ag.name = body.name
    if body.status is not None:
        changed["status"] = body.status
        ag.status = body.status

    db.add(ag)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="agency.updated",
        target_type="agency",
        target_id=agency_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"changed": changed},
    )
    await db.commit()
    await db.refresh(ag)

    sub_status, plan_name, plan_code, price = await _get_subscription_info(db, agency_id)
    return PlatformAgencyDetail(
        id=ag.id,
        name=ag.name,
        slug=ag.slug,
        status=ag.status,
        owner_user_id=ag.owner_user_id,
        plan_id=ag.plan_id,
        member_count=await _count_members(db, ag.id),
        brand_count=await _count_brands(db, ag.id),
        created_at=ag.created_at,
        updated_at=ag.updated_at,
        subscription_status=sub_status,
        plan_name=plan_name,
        plan_code=plan_code,
        monthly_price_cents=price,
    )


@platform_agencies_router.get("/{agency_id}/members", response_model=list[PlatformAgencyMemberRead])
async def list_agency_members(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformAgencyMemberRead]:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    members_result = await db.execute(
        select(AgencyMember, User)
        .join(User, User.id == AgencyMember.user_id)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
        )
        .order_by(AgencyMember.created_at.asc())
    )
    return [
        PlatformAgencyMemberRead(
            id=am.id,
            user_id=am.user_id,
            user_email=u.email,
            user_full_name=u.full_name,
            role=am.role,
            status=am.status,
            joined_at=am.joined_at,
            created_at=am.created_at,
        )
        for am, u in members_result.all()
    ]


@platform_agencies_router.get("/{agency_id}/brands", response_model=list[dict])
async def list_agency_brands(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    brands_result = await db.execute(
        select(Brand)
        .where(Brand.agency_id == agency_id, Brand.deleted_at.is_(None))
        .order_by(Brand.created_at.asc())
    )
    brands = brands_result.scalars().all()
    return [
        {
            "id": str(br.id),
            "name": br.name,
            "slug": br.slug,
            "status": br.status,
            "created_at": br.created_at.isoformat(),
            "updated_at": br.updated_at.isoformat(),
        }
        for br in brands
    ]


@platform_agencies_router.get("/{agency_id}/usage", response_model=PlatformAgencyUsage)
async def get_agency_usage(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyUsage:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Agency not found")

    # Total briefs
    brief_total_result = await db.execute(
        select(func.count())
        .select_from(Brief)
        .where(Brief.agency_id == agency_id, Brief.deleted_at.is_(None))
    )
    brief_total = brief_total_result.scalar_one()

    # Active briefs (not terminal statuses)
    brief_active_result = await db.execute(
        select(func.count())
        .select_from(Brief)
        .where(
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.status.not_in(["approved", "rejected", "archived"]),
        )
    )
    brief_active = brief_active_result.scalar_one()

    # Comment count via CommentThread -> Comment join
    comment_count_result = await db.execute(
        select(func.count())
        .select_from(Comment)
        .join(CommentThread, CommentThread.id == Comment.thread_id)
        .where(
            CommentThread.agency_id == agency_id,
            Comment.deleted_at.is_(None),
        )
    )
    comment_count = comment_count_result.scalar_one()

    return PlatformAgencyUsage(
        brief_total=brief_total,
        brief_active=brief_active,
        comment_count=comment_count,
    )


@platform_agencies_router.post(
    "/{agency_id}/suspend", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def suspend_agency(
    agency_id: uuid.UUID,
    body: AgencySuspendRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    if ag.status == AgencyStatus.SUSPENDED.value:
        raise HTTPException(status_code=400, detail="Agency already suspended")

    prev_status = ag.status
    ag.status = AgencyStatus.SUSPENDED.value
    db.add(ag)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="agency.suspended",
        target_type="agency",
        target_id=agency_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"reason": body.reason, "previous_status": prev_status},
    )
    await db.commit()


@platform_agencies_router.post(
    "/{agency_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def reactivate_agency(
    agency_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Agency).where(Agency.id == agency_id, Agency.deleted_at.is_(None))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        raise HTTPException(status_code=404, detail="Agency not found")
    if ag.status not in (AgencyStatus.SUSPENDED.value,):
        raise HTTPException(status_code=400, detail="Agency is not suspended")

    ag.status = AgencyStatus.ACTIVE.value
    db.add(ag)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="agency.reactivated",
        target_type="agency",
        target_id=agency_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await db.commit()


@platform_agencies_router.patch(
    "/{agency_id}/members/{member_id}", response_model=PlatformAgencyMemberRead
)
async def update_agency_member(
    agency_id: uuid.UUID,
    member_id: uuid.UUID,
    body: PlatformAgencyMemberUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyMemberRead:
    """Change an agency member's role/status. Fail-closed: cannot strip the last active owner."""
    await _get_agency_or_404(db, agency_id)

    result = await db.execute(
        select(AgencyMember, User)
        .join(User, User.id == AgencyMember.user_id)
        .where(
            AgencyMember.id == member_id,
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Agency member not found")
    member, member_user = row

    valid_roles = {r.value for r in AgencyMemberRole}
    valid_statuses = {s.value for s in AgencyMemberStatus}
    if body.role is not None and body.role not in valid_roles:
        raise HTTPException(status_code=422, detail="Invalid role")
    if body.status is not None and body.status not in valid_statuses:
        raise HTTPException(status_code=422, detail="Invalid status")

    next_role = body.role if body.role is not None else member.role
    next_status = body.status if body.status is not None else member.status

    is_demoting_owner = member.role == AgencyMemberRole.OWNER.value and (
        next_role != AgencyMemberRole.OWNER.value or next_status != AgencyMemberStatus.ACTIVE.value
    )
    if is_demoting_owner:
        other_owners_result = await db.execute(
            select(func.count())
            .select_from(AgencyMember)
            .where(
                AgencyMember.agency_id == agency_id,
                AgencyMember.id != member_id,
                AgencyMember.role == AgencyMemberRole.OWNER.value,
                AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
                AgencyMember.deleted_at.is_(None),
            )
        )
        if other_owners_result.scalar_one() == 0:
            raise HTTPException(
                status_code=400,
                detail="Ajansın en az bir aktif sahibi (owner) olmalıdır.",
            )

    changed: dict = {}
    if body.role is not None and body.role != member.role:
        changed["role"] = {"from": member.role, "to": body.role}
        member.role = body.role
    if body.status is not None and body.status != member.status:
        changed["status"] = {"from": member.status, "to": body.status}
        member.status = body.status

    if changed:
        db.add(member)
        audit_repo = PlatformAuditLogRepository(db)
        await audit_repo.create(
            admin_user_id=admin.id,
            action="agency_member.updated",
            target_type="agency_member",
            target_id=member_id,
            target_tenant_type="agency",
            target_tenant_id=agency_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            meta={"changed": changed, "user_email": member_user.email},
        )
        await db.commit()
        await db.refresh(member)

    return PlatformAgencyMemberRead(
        id=member.id,
        user_id=member.user_id,
        user_email=member_user.email,
        user_full_name=member_user.full_name,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        created_at=member.created_at,
    )


@platform_agencies_router.patch("/{agency_id}/plan", response_model=PlatformAgencyDetail)
async def update_agency_plan(
    agency_id: uuid.UUID,
    body: PlatformAgencyPlanUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyDetail:
    ag = await _get_agency_or_404(db, agency_id)

    plan_result = await db.execute(
        select(Plan).where(Plan.id == body.plan_id, Plan.deleted_at.is_(None))
    )
    plan = plan_result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    sub_result = await db.execute(
        select(Subscription).where(
            Subscription.agency_id == agency_id, Subscription.deleted_at.is_(None)
        )
    )
    sub = sub_result.scalar_one_or_none()
    previous_plan_id = sub.plan_id if sub else None

    if sub is None:
        sub = Subscription(
            agency_id=agency_id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE.value,
        )
    else:
        sub.plan_id = plan.id
    db.add(sub)

    ag.plan_id = plan.id
    db.add(ag)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="agency.plan_changed",
        target_type="agency",
        target_id=agency_id,
        target_tenant_type="agency",
        target_tenant_id=agency_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={
            "previous_plan_id": str(previous_plan_id) if previous_plan_id else None,
            "new_plan_id": str(plan.id),
            "new_plan_code": plan.code,
            "reason": body.reason,
        },
    )
    await db.commit()
    await db.refresh(ag)

    sub_status, plan_name, plan_code, price = await _get_subscription_info(db, agency_id)
    return PlatformAgencyDetail(
        id=ag.id,
        name=ag.name,
        slug=ag.slug,
        status=ag.status,
        owner_user_id=ag.owner_user_id,
        plan_id=ag.plan_id,
        member_count=await _count_members(db, ag.id),
        brand_count=await _count_brands(db, ag.id),
        created_at=ag.created_at,
        updated_at=ag.updated_at,
        subscription_status=sub_status,
        plan_name=plan_name,
        plan_code=plan_code,
        monthly_price_cents=price,
    )


@platform_agencies_router.get("/{agency_id}/branding", response_model=PlatformAgencyBrandingRead)
async def get_agency_branding_admin(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyBrandingRead:
    """Read-only visibility into an agency's white-label settings and custom domain."""
    await _get_agency_or_404(db, agency_id)

    svc = BrandingService(db)
    branding = await svc.get_settings(agency_id)
    try:
        domain = await svc.get_custom_domain(agency_id)
        domain_dict = domain.model_dump(mode="json")
    except HTTPException:
        domain_dict = None

    return PlatformAgencyBrandingRead(
        branding=branding.model_dump(mode="json"),
        domain=domain_dict,
    )


@platform_agencies_router.get("/{agency_id}/audit", response_model=list[dict])
async def get_agency_audit_feed(
    agency_id: uuid.UUID,
    limit: int = 50,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Merged platform-admin actions + tenant activity log for one agency, newest first."""
    await _get_agency_or_404(db, agency_id)

    platform_logs_result = await db.execute(
        select(PlatformAuditLog)
        .where(
            or_(
                and_(
                    PlatformAuditLog.target_type == "agency",
                    PlatformAuditLog.target_id == agency_id,
                ),
                PlatformAuditLog.target_tenant_id == agency_id,
            )
        )
        .order_by(PlatformAuditLog.created_at.desc())
        .limit(limit)
    )
    activity_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.agency_id == agency_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )

    entries = [
        {
            "source": "platform_admin",
            "id": str(log.id),
            "action": log.action,
            "meta": log.meta,
            "created_at": log.created_at.isoformat(),
        }
        for log in platform_logs_result.scalars().all()
    ] + [
        {
            "source": "tenant",
            "id": str(log.id),
            "action": log.action,
            "entity_type": log.entity_type,
            "meta": log.meta,
            "created_at": log.created_at.isoformat(),
        }
        for log in activity_result.scalars().all()
    ]
    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries[:limit]


@platform_agencies_router.get(
    "/{agency_id}/invitations", response_model=list[PlatformInvitationRead]
)
async def list_platform_agency_invitations(
    agency_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformInvitationRead]:
    await _get_agency_or_404(db, agency_id)
    invitations = await db.scalars(
        select(Invitation)
        .where(
            Invitation.agency_id == agency_id,
            Invitation.invitation_type == "agency",
            Invitation.deleted_at.is_(None),
        )
        .order_by(Invitation.created_at.desc())
        .limit(100)
    )
    return [_platform_invitation_read(invitation) for invitation in invitations.all()]


@platform_agencies_router.post(
    "/{agency_id}/invitations",
    response_model=PlatformInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_agency_user_by_platform(
    agency_id: uuid.UUID,
    body: PlatformMemberInviteRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformInvitationRead:
    invitation = await PlatformProvisioningService(db).invite_agency_member(
        agency_id,
        body,
        admin=admin,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return _platform_invitation_read(invitation)


@platform_agencies_router.post(
    "/{agency_id}/members/attach",
    response_model=PlatformAgencyMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def attach_agency_user_by_platform(
    agency_id: uuid.UUID,
    body: PlatformMemberAttachRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAgencyMemberRead:
    member = await PlatformProvisioningService(db).attach_agency_member(
        agency_id,
        body,
        admin=admin,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    user = await db.get(User, member.user_id)
    return PlatformAgencyMemberRead(
        id=member.id,
        user_id=member.user_id,
        user_email=user.email if user else None,
        user_full_name=user.full_name if user else None,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        created_at=member.created_at,
    )


@platform_agencies_router.post(
    "/{agency_id}/invitations/{invitation_id}/resend",
    response_model=PlatformInvitationRead,
)
async def resend_agency_invitation_by_platform(
    agency_id: uuid.UUID,
    invitation_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformInvitationRead:
    service = PlatformProvisioningService(db)
    invitation = await service.scoped_invitation(invitation_id, agency_id=agency_id, lock=True)
    invitation = await service.resend_invitation(
        invitation,
        admin=admin,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    return _platform_invitation_read(invitation)


@platform_agencies_router.post(
    "/{agency_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def revoke_agency_invitation_by_platform(
    agency_id: uuid.UUID,
    invitation_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    service = PlatformProvisioningService(db)
    invitation = await service.scoped_invitation(invitation_id, agency_id=agency_id, lock=True)
    await service.revoke_invitation(
        invitation,
        admin=admin,
        ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
