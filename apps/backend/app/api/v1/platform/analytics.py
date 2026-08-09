"""Platform admin — analytics and dashboard endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.core.dependencies import get_platform_admin_user
from app.db.session import get_db
from app.models.agency import Agency
from app.models.agency_member import AgencyMember
from app.models.brand import Brand
from app.models.enums import AgencyStatus
from app.models.plan import Plan
from app.models.platform_audit_log import PlatformAuditLog
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.platform import (
    PlatformAnalytics,
    PlatformAuditLogRead,
    PlatformDashboardStats,
)

platform_analytics_router = APIRouter(tags=["platform-analytics"])


def _is_commercial_user() -> object:
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
    return ~exists(demo_membership)


def _commercial_subscription_query() -> Select[tuple[Subscription]]:
    brand_agency = aliased(Agency)
    commercial_tenant = or_(
        and_(
            Subscription.agency_id.is_not(None),
            Agency.is_demo.is_(False),
        ),
        and_(
            Subscription.brand_id.is_not(None),
            or_(Brand.agency_id.is_(None), brand_agency.is_demo.is_(False)),
        ),
    )
    return (
        select(Subscription)
        .outerjoin(Agency, Agency.id == Subscription.agency_id)
        .outerjoin(Brand, Brand.id == Subscription.brand_id)
        .outerjoin(brand_agency, brand_agency.id == Brand.agency_id)
        .where(
            Subscription.deleted_at.is_(None),
            commercial_tenant,
        )
    )


@platform_analytics_router.get("/dashboard", response_model=PlatformDashboardStats)
async def platform_dashboard(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformDashboardStats:
    # Total and active agencies
    total_ag = await db.scalar(
        select(func.count())
        .select_from(Agency)
        .where(Agency.deleted_at.is_(None), Agency.is_demo.is_(False))
    )
    active_ag = await db.scalar(
        select(func.count())
        .select_from(Agency)
        .where(
            Agency.deleted_at.is_(None),
            Agency.is_demo.is_(False),
            Agency.status == AgencyStatus.ACTIVE.value,
        )
    )
    suspended_ag = await db.scalar(
        select(func.count())
        .select_from(Agency)
        .where(
            Agency.deleted_at.is_(None),
            Agency.is_demo.is_(False),
            Agency.status == AgencyStatus.SUSPENDED.value,
        )
    )

    # Total users
    total_users = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.deleted_at.is_(None), _is_commercial_user())
    )

    # Monthly active users (last 30 days)
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    mau = await db.scalar(
        select(func.count())
        .select_from(User)
        .where(
            User.deleted_at.is_(None),
            User.last_login_at >= thirty_days_ago,
            _is_commercial_user(),
        )
    )

    # Subscriptions and MRR
    commercial_subscriptions = _commercial_subscription_query().subquery()
    total_subs = await db.scalar(select(func.count()).select_from(commercial_subscriptions))
    mrr_result = await db.execute(
        select(func.sum(Plan.monthly_price_cents)).join(
            commercial_subscriptions, commercial_subscriptions.c.plan_id == Plan.id
        )
    )
    mrr = mrr_result.scalar_one_or_none() or 0

    return PlatformDashboardStats(
        total_agencies=total_ag or 0,
        active_agencies=active_ag or 0,
        suspended_agencies=suspended_ag or 0,
        total_users=total_users or 0,
        active_users_30d=mau or 0,
        total_subscriptions=total_subs or 0,
        mrr_cents=int(mrr),
    )


@platform_analytics_router.get("/analytics", response_model=PlatformAnalytics)
async def platform_analytics(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlatformAnalytics:
    # Agencies by status
    ag_status_result = await db.execute(
        select(Agency.status, func.count())
        .where(Agency.deleted_at.is_(None), Agency.is_demo.is_(False))
        .group_by(Agency.status)
    )
    agencies_by_status = {row[0]: row[1] for row in ag_status_result.all()}

    # Users by type
    user_type_result = await db.execute(
        select(User.user_type, func.count())
        .where(User.deleted_at.is_(None), _is_commercial_user())
        .group_by(User.user_type)
    )
    users_by_type = {row[0]: row[1] for row in user_type_result.all()}

    # Plan distribution
    commercial_subscriptions = _commercial_subscription_query().subquery()
    plan_dist_result = await db.execute(
        select(Plan.code, func.count())
        .join(commercial_subscriptions, commercial_subscriptions.c.plan_id == Plan.id)
        .group_by(Plan.code)
    )
    plan_distribution = {row[0]: row[1] for row in plan_dist_result.all()}

    return PlatformAnalytics(
        agencies_by_status=agencies_by_status,
        users_by_type=users_by_type,
        plan_distribution=plan_distribution,
    )


@platform_analytics_router.get("/audit-logs", response_model=list[PlatformAuditLogRead])
async def list_audit_logs(
    limit: int = 50,
    offset: int = 0,
    action_filter: str | None = None,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformAuditLogRead]:
    stmt = (
        select(PlatformAuditLog)
        .order_by(PlatformAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if action_filter:
        stmt = stmt.where(PlatformAuditLog.action.ilike(f"%{action_filter}%"))
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return [
        PlatformAuditLogRead(
            id=log.id,
            admin_user_id=log.admin_user_id,
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            target_tenant_type=log.target_tenant_type,
            target_tenant_id=log.target_tenant_id,
            meta=log.meta,
            ip_address=str(log.ip_address) if log.ip_address else None,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log in logs
    ]
