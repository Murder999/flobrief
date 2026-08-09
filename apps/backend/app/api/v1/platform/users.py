"""Platform admin — user management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.activity import ActivityLog
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brand_member import BrandMember
from app.models.brief import Brief, BriefAssignee
from app.models.notification import NotificationPreference
from app.models.user import User
from app.models.user_token import UserToken
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform import (
    PlatformAgencyMembershipRead,
    PlatformBrandMembershipRead,
    PlatformUserDetail,
    PlatformUserRead,
    PlatformUserUpdate,
)

platform_users_router = APIRouter(prefix="/users", tags=["platform-users"])


@platform_users_router.get("", response_model=list[PlatformUserRead])
async def list_users(
    limit: int = 50,
    offset: int = 0,
    user_type: str | None = None,
    search: str | None = None,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformUserRead]:
    demo_membership = (
        select(AgencyMember.id)
        .join(Agency, Agency.id == AgencyMember.agency_id)
        .where(
            AgencyMember.user_id == User.id,
            AgencyMember.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
            Agency.is_demo.is_(True),
        )
    )
    stmt = (
        select(User)
        .where(User.deleted_at.is_(None), ~exists(demo_membership))
        .order_by(User.created_at.desc())
    )
    if user_type:
        stmt = stmt.where(User.user_type == user_type)
    if search:
        stmt = stmt.where(
            or_(
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        PlatformUserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            user_type=u.user_type,
            is_active=u.is_active,
            is_verified=u.is_verified,
            mfa_enabled=u.mfa_enabled,
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
        for u in users
    ]


@platform_users_router.get("/{user_id}", response_model=PlatformUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserDetail:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Agency memberships
    am_result = await db.execute(
        select(AgencyMember, Agency)
        .join(Agency, Agency.id == AgencyMember.agency_id)
        .where(
            AgencyMember.user_id == user_id,
            AgencyMember.deleted_at.is_(None),
            Agency.deleted_at.is_(None),
        )
    )
    agency_memberships = [
        PlatformAgencyMembershipRead(
            agency_id=am.agency_id,
            agency_name=ag.name,
            role=am.role,
            status=am.status,
            joined_at=am.joined_at,
        )
        for am, ag in am_result.all()
    ]

    # Brand memberships
    bm_result = await db.execute(
        select(BrandMember, Brand)
        .join(Brand, Brand.id == BrandMember.brand_id)
        .where(
            BrandMember.user_id == user_id,
            BrandMember.deleted_at.is_(None),
            Brand.deleted_at.is_(None),
        )
    )
    brand_memberships = [
        PlatformBrandMembershipRead(
            brand_id=bm.brand_id,
            brand_name=br.name,
            agency_id=br.agency_id,
            role=bm.role,
            status=bm.status,
            joined_at=bm.joined_at,
        )
        for bm, br in bm_result.all()
    ]

    # Brief counts
    brief_created_result = await db.execute(
        select(func.count())
        .select_from(Brief)
        .where(Brief.created_by_id == user_id, Brief.deleted_at.is_(None))
    )
    brief_created_count = brief_created_result.scalar_one()

    brief_assigned_result = await db.execute(
        select(func.count())
        .select_from(BriefAssignee)
        .where(BriefAssignee.user_id == user_id, BriefAssignee.deleted_at.is_(None))
    )
    brief_assigned_count = brief_assigned_result.scalar_one()

    # Notification preferences
    np_result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    np = np_result.scalar_one_or_none()

    return PlatformUserDetail(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        user_type=user.user_type,
        is_active=user.is_active,
        is_verified=user.is_verified,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        phone_number=user.phone_number,
        whatsapp_opt_in=user.whatsapp_opt_in,
        agency_memberships=agency_memberships,
        brand_memberships=brand_memberships,
        brief_created_count=brief_created_count,
        brief_assigned_count=brief_assigned_count,
        notification_email_enabled=np.email_enabled if np else None,
        notification_whatsapp_enabled=np.whatsapp_enabled if np else None,
        notification_in_app_enabled=np.in_app_enabled if np else None,
    )


@platform_users_router.patch("/{user_id}", response_model=PlatformUserRead)
async def update_user(
    user_id: uuid.UUID,
    body: PlatformUserUpdate,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserRead:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    changed: dict = {}
    if body.full_name is not None:
        changed["full_name"] = body.full_name
        user.full_name = body.full_name
    if body.phone_number is not None:
        changed["phone_number"] = body.phone_number
        user.phone_number = body.phone_number
    if body.is_active is not None:
        changed["is_active"] = body.is_active
        user.is_active = body.is_active

    db.add(user)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="user.updated",
        target_type="user",
        target_id=user_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"changed": changed, "email": user.email},
    )
    await db.commit()
    await db.refresh(user)

    return PlatformUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        user_type=user.user_type,
        is_active=user.is_active,
        is_verified=user.is_verified,
        mfa_enabled=user.mfa_enabled,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@platform_users_router.post(
    "/{user_id}/terminate-sessions",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def terminate_user_sessions(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(delete(UserToken).where(UserToken.user_id == user_id))

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="user.sessions_terminated",
        target_type="user",
        target_id=user_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"email": user.email},
    )
    await db.commit()


@platform_users_router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: uuid.UUID,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="User not found")

    logs_result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.actor_user_id == user_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(30)
    )
    logs = logs_result.scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": str(log.entity_id) if log.entity_id else None,
            "meta": log.meta,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@platform_users_router.post(
    "/{user_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="User already inactive")

    user.is_active = False
    db.add(user)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="user.deactivated",
        target_type="user",
        target_id=user_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"email": user.email, "user_type": user.user_type},
    )
    await db.commit()


@platform_users_router.post(
    "/{user_id}/reactivate", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def reactivate_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User already active")

    user.is_active = True
    db.add(user)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="user.reactivated",
        target_type="user",
        target_id=user_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={"email": user.email},
    )
    await db.commit()
