"""Owner-level dashboard endpoints for agency owners.

These endpoints are scoped to the current workspace (agency), and require
at minimum AGENCY_VIEW permission. Destructive actions require AGENCY_MANAGE_MEMBERS.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_dependencies import WorkspaceContext, get_workspace_context
from app.core.rbac import Permission
from app.db.session import get_db
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.brief import Brief
from app.models.calendar import CalendarItem
from app.models.enums import AgencyMemberStatus, BriefStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.platform import (
    OwnerDashboardStats,
    OwnerMemberRead,
    OwnerSubscriptionRead,
)

owner_router = APIRouter(prefix="/owner", tags=["owner"])


def _check_perm(workspace: WorkspaceContext, perm: Permission) -> None:
    if perm not in workspace.permissions:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")


@owner_router.get("/dashboard", response_model=OwnerDashboardStats)
async def owner_dashboard(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OwnerDashboardStats:
    _check_perm(workspace, Permission.AGENCY_VIEW)
    agency_id = workspace.agency.id

    # Active brands
    brands_count = await db.scalar(
        select(func.count())
        .select_from(Brand)
        .where(Brand.agency_id == agency_id, Brand.deleted_at.is_(None))
    )

    # Active members
    members_count = await db.scalar(
        select(func.count())
        .select_from(AgencyMember)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
        )
    )

    # Open briefs (draft or in_review)
    open_briefs = await db.scalar(
        select(func.count())
        .select_from(Brief)
        .where(
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.status.in_([BriefStatus.DRAFT.value, BriefStatus.IN_REVIEW.value]),
        )
    )

    # Total approved briefs
    approved_briefs = await db.scalar(
        select(func.count())
        .select_from(Brief)
        .where(
            Brief.agency_id == agency_id,
            Brief.deleted_at.is_(None),
            Brief.status == BriefStatus.APPROVED.value,
        )
    )

    # Calendar items this month
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    calendar_items = await db.scalar(
        select(func.count())
        .select_from(CalendarItem)
        .where(
            CalendarItem.agency_id == agency_id,
            CalendarItem.deleted_at.is_(None),
            CalendarItem.publish_at >= month_start,
            CalendarItem.publish_at < datetime(now.year, now.month % 12 + 1, 1, tzinfo=UTC)
            if now.month < 12
            else CalendarItem.publish_at < datetime(now.year + 1, 1, 1, tzinfo=UTC),
        )
    )

    return OwnerDashboardStats(
        active_brands=brands_count or 0,
        active_members=members_count or 0,
        open_briefs=open_briefs or 0,
        approved_briefs_total=approved_briefs or 0,
        calendar_items_this_month=calendar_items or 0,
    )


@owner_router.get("/members", response_model=list[OwnerMemberRead])
async def owner_members(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> list[OwnerMemberRead]:
    _check_perm(workspace, Permission.AGENCY_VIEW)
    agency_id = workspace.agency.id

    result = await db.execute(
        select(AgencyMember, User)
        .join(User, User.id == AgencyMember.user_id)
        .where(AgencyMember.agency_id == agency_id, AgencyMember.deleted_at.is_(None))
        .order_by(AgencyMember.created_at.asc())
    )
    rows = result.all()

    return [
        OwnerMemberRead(
            member_id=member.id,
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=member.role,
            status=member.status,
            last_login_at=user.last_login_at,
            joined_at=member.joined_at,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


@owner_router.post(
    "/members/{member_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def deactivate_member(
    member_id: uuid.UUID,
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> None:
    _check_perm(workspace, Permission.AGENCY_MANAGE_MEMBERS)
    agency_id = workspace.agency.id

    result = await db.execute(
        select(AgencyMember).where(
            AgencyMember.id == member_id,
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.user_id == workspace.user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    if member.status == AgencyMemberStatus.SUSPENDED.value:
        raise HTTPException(status_code=400, detail="Member already suspended")

    member.status = AgencyMemberStatus.SUSPENDED.value
    db.add(member)
    await db.commit()


@owner_router.get("/subscription", response_model=OwnerSubscriptionRead)
async def owner_subscription(
    workspace: WorkspaceContext = Depends(get_workspace_context),
    db: AsyncSession = Depends(get_db),
) -> OwnerSubscriptionRead:
    _check_perm(workspace, Permission.BILLING_VIEW)
    agency_id = workspace.agency.id

    result = await db.execute(
        select(Subscription, Plan)
        .join(Plan, Plan.id == Subscription.plan_id)
        .where(Subscription.agency_id == agency_id, Subscription.deleted_at.is_(None))
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="No active subscription")

    sub, plan = row

    # Actual usage
    active_brands = await db.scalar(
        select(func.count())
        .select_from(Brand)
        .where(Brand.agency_id == agency_id, Brand.deleted_at.is_(None))
    )
    active_members = await db.scalar(
        select(func.count())
        .select_from(AgencyMember)
        .where(
            AgencyMember.agency_id == agency_id,
            AgencyMember.deleted_at.is_(None),
            AgencyMember.status == AgencyMemberStatus.ACTIVE.value,
        )
    )

    return OwnerSubscriptionRead(
        plan_code=plan.code,
        plan_name=plan.name,
        plan_description=plan.description,
        status=sub.status,
        max_brands=plan.max_brands,
        max_users=plan.max_users,
        monthly_price_cents=plan.monthly_price_cents,
        current_period_end=sub.current_period_end,
        active_brands=active_brands or 0,
        active_members=active_members or 0,
    )
