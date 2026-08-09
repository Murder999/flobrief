"""Platform admin — subscription management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.agency import Agency
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.platform import PlatformSubscriptionRead, SubscriptionOverrideRequest

platform_subscriptions_router = APIRouter(prefix="/subscriptions", tags=["platform-subscriptions"])


@platform_subscriptions_router.get("", response_model=list[PlatformSubscriptionRead])
async def list_subscriptions(
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformSubscriptionRead]:
    stmt = (
        select(Subscription, Plan, Agency)
        .join(Plan, Plan.id == Subscription.plan_id)
        .outerjoin(Agency, Agency.id == Subscription.agency_id)
        .where(Subscription.deleted_at.is_(None))
        .order_by(Subscription.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    rows = result.all()

    out = []
    for sub, plan, agency in rows:
        out.append(
            PlatformSubscriptionRead(
                id=sub.id,
                agency_id=sub.agency_id,
                agency_name=agency.name if agency else None,
                brand_id=sub.brand_id,
                plan_id=sub.plan_id,
                plan_name=plan.name,
                plan_code=plan.code,
                status=sub.status,
                monthly_price_cents=plan.monthly_price_cents,
                current_period_start=sub.current_period_start,
                current_period_end=sub.current_period_end,
                created_at=sub.created_at,
            )
        )
    return out


@platform_subscriptions_router.post(
    "/{subscription_id}/override",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def override_subscription(
    subscription_id: uuid.UUID,
    body: SubscriptionOverrideRequest,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.deleted_at.is_(None)
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan_result = await db.execute(
        select(Plan).where(Plan.id == body.plan_id, Plan.deleted_at.is_(None))
    )
    new_plan = plan_result.scalar_one_or_none()
    if new_plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    old_plan_id = sub.plan_id
    sub.plan_id = body.plan_id
    db.add(sub)

    audit_repo = PlatformAuditLogRepository(db)
    await audit_repo.create(
        admin_user_id=admin.id,
        action="subscription.overridden",
        target_type="subscription",
        target_id=subscription_id,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        meta={
            "reason": body.reason,
            "old_plan_id": str(old_plan_id),
            "new_plan_id": str(body.plan_id),
            "new_plan_code": new_plan.code,
        },
    )
    await db.commit()
