"""Platform admin — plan management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_platform_admin_user
from app.core.rate_limiter import get_client_ip
from app.db.session import get_db
from app.models.user import User
from app.repositories.plan import PlanRepository
from app.repositories.platform_audit_log import PlatformAuditLogRepository
from app.schemas.billing import PlanRead

platform_plans_router = APIRouter(prefix="/plans", tags=["platform-plans"])


class PlanCreateRequest(PlanRead):
    id: uuid.UUID | None = None  # type: ignore[assignment]

    model_config = {"from_attributes": True}


@platform_plans_router.get("", response_model=list[PlanRead])
async def list_plans(
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlanRead]:
    repo = PlanRepository(db)
    plans = await repo.list_active()
    return [PlanRead.model_validate(p) for p in plans]


@platform_plans_router.patch("/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: uuid.UUID,
    body: dict,
    request: Request,
    admin: User = Depends(get_platform_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PlanRead:
    repo = PlanRepository(db)
    plan = await repo.get_by_id(plan_id)
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan bulunamadı")

    allowed_fields = {
        "name",
        "description",
        "monthly_price_cents",
        "yearly_price_cents",
        "max_brands",
        "max_users",
        "max_brand_users",
        "max_brief_templates",
        "max_storage_gb",
        "max_pending_agency_invites",
        "max_pending_brand_invites",
        "white_label_enabled",
        "advanced_reporting_enabled",
        "pdf_export_enabled",
        "public_report_link_enabled",
        "whatsapp_infrastructure_enabled",
        "platform_admin_visible",
        "is_active",
    }
    changes: dict = {}
    for field, value in body.items():
        if field in allowed_fields:
            changes[field] = value
            setattr(plan, field, value)

    if changes:
        db.add(plan)
        audit_repo = PlatformAuditLogRepository(db)
        await audit_repo.create(
            admin_user_id=admin.id,
            action="plan.updated",
            target_type="plan",
            target_id=plan_id,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            meta={"changes": changes},
        )
        await db.commit()
        await db.refresh(plan)

    return PlanRead.model_validate(plan)
